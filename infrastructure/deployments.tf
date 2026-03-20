# Get all top-level folders in demos directory
locals {
  # Get all items in demos directory
  demo_items = fileset("${path.module}/../demos", "*")
  
  # Filter to only directories that contain prefect.yaml
  demo_folders = [
    for item in local.demo_items :
    item
    if fileexists("${path.module}/../demos/${item}/prefect.yaml")
  ]
  
  # Read and decode each prefect.yaml file
  prefect_configs = {
    for folder in local.demo_folders :
    folder => yamldecode(file("${path.module}/../demos/${folder}/prefect.yaml"))
  }
  
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
}

# Create a prefect_deployment resource for each deployment
# Note: You may need to add flow_id or flow_name if required by the provider
# The flow must be registered in Prefect before the deployment can reference it
resource "prefect_deployment" "demo" {
  for_each = local.deployments_flat

  name = each.value.deployment.name

  # Entrypoint from the deployment config (format: path/to/file.py:function_name)
  entrypoint = each.value.deployment.entrypoint

  # Work pool configuration
  work_pool_name  = each.value.work_pool_name
  work_queue_name = each.value.work_queue_name

  # Tags
  tags = each.value.tags

  # Parameters - keep as map/object, Terraform provider should handle conversion
  parameters = try(each.value.deployment.parameters, null)

  # Schedule configuration - convert to the format expected by the provider
  # The provider may expect a specific format, adjust based on provider documentation
  schedule = try(each.value.deployment.schedule, null) != null ? (
    try(each.value.deployment.schedule.cron, null) != null ? {
      cron     = each.value.deployment.schedule.cron
      timezone = try(each.value.deployment.schedule.timezone, "UTC")
    } : null
  ) : null

  # Description
  description = try(each.value.deployment.description, null)

  # Version
  version = try(each.value.deployment.version, null)
}
