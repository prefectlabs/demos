locals {
  demo_folders = [
    for item in fileset(var.deploy_base_path, "**/prefect.yaml") :
    dirname(item)
    if !anytrue([for pattern in var.demo_exclude_patterns : can(regex(pattern, dirname(item)))])
  ]

  raw_configs = {
    for folder in local.demo_folders :
    folder => yamldecode(file("${var.deploy_base_path}/${folder}/prefect.yaml"))
  }

  deployments = merge([
    for folder, config in local.raw_configs : {
      for deployment in try(config.deployments, []) :
      "${folder}-${deployment.name}" => {
        folder_name     = folder
        deployment      = deployment
        flow_name       = split(":", deployment.entrypoint)[1]
        work_pool_name  = try(deployment.work_pool.name, deployment.work_pool, try(config.definitions.work_pools.work_pool.name, null), "default")
        work_queue_name = try(deployment.work_pool.work_queue_name, null)
        tags            = try(deployment.tags, try(config.definitions.tags, []))
        schedules       = try(deployment.schedules, try([deployment.schedule], []))
        triggers        = try(deployment.triggers, [])
      }
    }
  ]...)
}

resource "prefect_flow" "this" {
  for_each = toset([for d in local.deployments : d.flow_name])
  name     = each.key
}

# ─── Parameter schema generation ────────────────────────────────────────────
data "external" "schema" {
  for_each = {
    for k, v in local.deployments : k => v
    if var.enable_parameter_schema_generation
  }

  program = ["uv", "run", "${path.module}/scripts/schema_generator.py"]

  query = {
    entrypoint                          = each.value.deployment.entrypoint
    folder                              = join("/", [var.deploy_base_path, each.value.folder_name])
  }
}

# ─── Deployment resources ───────────────────────────────────────────────────
resource "prefect_deployment" "this" {
  for_each = local.deployments

  name       = each.value.deployment.name
  flow_id    = prefect_flow.this[each.value.flow_name].id
  entrypoint = each.value.deployment.entrypoint

  work_pool_name  = each.value.work_pool_name
  work_queue_name = each.value.work_queue_name
  tags            = each.value.tags

  parameters               = jsonencode(try(each.value.deployment.parameters, {}))
  parameter_openapi_schema = var.enable_parameter_schema_generation ? data.external.schema[each.key].result.schema : null

  description = try(each.value.deployment.description, null)
  version     = try(each.value.deployment.version, null)
}

# ─── Deployment schedules ───────────────────────────────────────────────────
resource "prefect_deployment_schedule" "this" {
  for_each = merge([
    for key, d in local.deployments : {
      for idx, sched in d.schedules :
      "${key}-${idx}" => merge(sched, { deployment_key = key })
      if sched != null
    }
  ]...)

  deployment_id = prefect_deployment.this[each.value.deployment_key].id

  active   = try(each.value.active, true)
  timezone = try(each.value.timezone, null)

  cron   = try(each.value.cron, null)
  day_or = try(each.value.day_or, null)

  interval    = try(each.value.interval, null)
  anchor_date = try(each.value.anchor_date, null)

  rrule = try(each.value.rrule, null)
}

# ─── Deployment triggers (automations) ──────────────────────────────────────
# In prefect.yaml, `triggers` are syntactic sugar for automations whose
# action is always "run-deployment" targeting the parent deployment.
resource "prefect_automation" "this" {
  for_each = merge([
    for key, d in local.deployments : {
      for idx, trig in d.triggers :
      "${key}-${idx}" => merge(trig, { deployment_key = key })
    }
  ]...)

  name        = try(each.value.name, each.key)
  description = try(each.value.description, null)
  enabled     = try(each.value.enabled, true)

  trigger = merge(
    try(each.value.type, "event") == "event" ? {
      event = {
        posture       = try(each.value.posture, "Reactive")
        match         = try(jsonencode(each.value.match), null)
        match_related = try(jsonencode(each.value.match_related), null)
        after         = try(each.value.after, null)
        expect        = try(each.value.expect, null)
        for_each      = try(each.value.for_each, null)
        threshold     = try(each.value.threshold, 1)
        within        = try(each.value.within, 0)
      }
    } : {},

    try(each.value.type, "") == "compound" ? {
      compound = {
        require  = try(each.value.require, null)
        within   = try(each.value.within, null)
        triggers = each.value.triggers
      }
    } : {},

    try(each.value.type, "") == "sequence" ? {
      sequence = {
        within   = try(each.value.within, null)
        triggers = each.value.triggers
      }
    } : {},

    try(each.value.type, "") == "metric" ? {
      metric = {
        match     = try(jsonencode(each.value.match), null)
        metric    = try(jsonencode(each.value.metric), null)
        operator  = try(each.value.operator, null)
        threshold = try(each.value.threshold, null)
      }
    } : {},
  )

  actions = [
    {
      type          = "run-deployment"
      source        = "selected"
      deployment_id = prefect_deployment.this[each.value.deployment_key].id
      parameters    = try(jsonencode(each.value.parameters), null)
    }
  ]
}
