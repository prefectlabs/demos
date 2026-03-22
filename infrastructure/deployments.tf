# Get all top-level folders in demos directory
locals {
  # Get all items in demos directory
  demo_items = fileset("${path.module}/../demos", "*")
  
  # Filter to only directories that contain prefect.yaml
  demo_folders = [
    for item in local.demo_items :
    item
    if fileexists("${path.module}/../demos/${item}/prefect.yaml")
    && !anytrue([for pattern in var.demo_exclude_patterns : can(regex(pattern, item))])
  ]
  
  # Read and decode each prefect.yaml file
  prefect_configs = {
    for folder in local.demo_folders :
    folder => yamldecode(file("${path.module}/../demos/${folder}/prefect.yaml"))
  }

  # Extract all unique flow names from configs
  flows = distinct(
    compact(
      flatten(
        [
          for file, config in local.prefect_configs : [
          for deployment in try(config.deployments, []) :
          split(":", deployment.entrypoint)[1]
        ]
        ]
      )
    )
  )

  # Process deployments and resolve YAML anchor references
  # Note: yamldecode may not resolve YAML anchors, so we handle fallbacks
  resolve_anchor = {
    for folder, config in local.prefect_configs :
    folder => {
      for deployment in try(config.deployments, []) :
      "${folder}-${deployment.name}" => {
        folder_name = folder
        deployment  = deployment
        config      = config

        # Resolve work_pool (handle objects, strings, and fallback to definitions)
        work_pool_name = try(
          # First try: object with name field
          deployment.work_pool.name,
          # Second try: direct string value
          deployment.work_pool,
          # Third try: fallback to definitions if work_pool is not set
          try(config.definitions.work_pools.work_pool.name, null),
          # Final fallback
          "default"
        )

        work_queue_name = try(
          deployment.work_pool.work_queue_name,
          null
        )

        # Resolve tags (handle list, fallback to definitions)
        tags = try(
          # If tags exists and is a list, use it
          can(deployment.tags) && type(deployment.tags) == "list" ? deployment.tags : (
            # Try to get from definitions if tags uses anchor reference
            try(config.definitions.tags, [])
          ),
          # Final fallback
          []
        )
      }
    }
  }

  # Flatten the deployments
  deployments_flat = merge([
    for folder, deployments in local.resolve_anchor :
    deployments
  ]...)

  # Flatten schedules from all deployments.
  # Handles both `schedules:` (list, current) and `schedule:` (singular, legacy).
  # Each entry is keyed as "<deployment_key>-<index>" for uniqueness.
  schedules_flat = merge([
    for deploy_key, deploy in local.deployments_flat : {
      for idx, sched in try(deploy.deployment.schedules, try([deploy.deployment.schedule], [])) :
      "${deploy_key}-${idx}" => {
        deployment_key = deploy_key
        cron           = try(sched.cron, null)
        interval       = try(sched.interval, null)
        anchor_date    = try(sched.anchor_date, null)
        rrule          = try(sched.rrule, null)
        timezone       = try(sched.timezone, null)
        active         = try(sched.active, true)
        day_or         = try(sched.day_or, null)
      }
      if sched != null
    }
  ]...)
}

resource "prefect_flow" "flows" {
  for_each = toset(local.flows)
  name = each.key
}

# ─── Parameter schema generation ────────────────────────────────────────────
# Calls the schema_generator.py script for each deployment.
# The script uses Prefect's parameter_schema_from_entrypoint to parse the
# flow function's signature from source (no runtime imports needed) and
# returns the OpenAPI schema as a JSON string.
data "external" "schema" {
  for_each = local.deployments_flat

  program = ["uv", "run", "scripts/schema_generator.py"]

  query = {
    entrypoint = each.value.deployment.entrypoint
    folder     = each.value.folder_name
  }
}

# ─── Deployment resources ───────────────────────────────────────────────────
resource "prefect_deployment" "demo" {
  for_each = local.deployments_flat

  name = each.value.deployment.name
  flow_id = prefect_flow.flows[split(":", each.value.entrypoint)[1]].id

  # Entrypoint from the deployment config (format: path/to/file.py:function_name)
  entrypoint = each.value.deployment.entrypoint

  # Work pool configuration
  work_pool_name  = each.value.work_pool_name
  work_queue_name = each.value.work_queue_name

  # Tags
  tags = each.value.tags

  # Parameters - keep as map/object, Terraform provider should handle conversion
  parameters = try(each.value.deployment.parameters, null)

  # OpenAPI parameter schema — generated from the flow source by the external data source
  parameter_openapi_schema = data.external.schema[each.key].result.schema

  # Description
  description = try(each.value.deployment.description, null)

  # Version
  version = try(each.value.deployment.version, null)
}

# ─── Deployment schedules ───────────────────────────────────────────────────
# One resource per schedule entry. A single deployment can have multiple
# schedules (cron, interval, rrule) — all extracted from prefect.yaml.
resource "prefect_deployment_schedule" "demo" {
  for_each = local.schedules_flat

  deployment_id = prefect_deployment.demo[each.value.deployment_key].id

  active   = each.value.active
  timezone = each.value.timezone

  # Cron
  cron   = each.value.cron
  day_or = each.value.day_or

  # Interval (seconds)
  interval    = each.value.interval
  anchor_date = each.value.anchor_date

  # RRule
  rrule = each.value.rrule
}
