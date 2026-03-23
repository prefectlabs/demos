output "demo_folders" {
  description = "Discovered demo folders containing prefect.yaml files."
  value       = local.demo_folders
}

output "deployment_keys" {
  description = "Stable deployment keys generated from folder and deployment name."
  value       = sort(keys(local.deployments))
}

output "deployments" {
  description = "Sanitized deployment metadata keyed by deployment key."
  value = {
    for key, deployment in local.deployments : key => {
      folder_name     = deployment.folder_name
      name            = deployment.deployment.name
      flow_name       = deployment.flow_name
      entrypoint      = deployment.deployment.entrypoint
      work_pool_name  = deployment.work_pool_name
      work_queue_name = deployment.work_queue_name
      tags            = deployment.tags
    }
  }
}

output "flow_ids" {
  description = "Prefect flow IDs keyed by flow name."
  value       = { for key, flow in prefect_flow.this : key => flow.id }
}

output "deployment_ids" {
  description = "Prefect deployment IDs keyed by deployment key."
  value       = { for key, deployment in prefect_deployment.this : key => deployment.id }
}

output "deployment_schedule_ids" {
  description = "Prefect deployment schedule IDs keyed by schedule key."
  value       = { for key, schedule in prefect_deployment_schedule.this : key => schedule.id }
}

output "automation_ids" {
  description = "Prefect automation IDs keyed by automation key."
  value       = { for key, automation in prefect_automation.this : key => automation.id }
}
