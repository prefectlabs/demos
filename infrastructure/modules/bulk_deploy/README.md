# bulk_deploy

Terraform module for bulk registration of Prefect deployments from folders that contain `prefect.yaml` files.

The module scans a base directory for `prefect.yaml` files, reads deployment metadata, and creates Prefect flows, deployments, schedules, and trigger-based automations.

## Example usage

Configure the [Prefect Terraform provider](https://registry.terraform.io/providers/prefecthq/prefect/latest/docs) (API URL and credentials) in your root module.

Set `deploy_base_path` to a directory whose subfolders contain `prefect.yaml` files.

Parameter schemas are generated via `uv run scripts/schema_generator.py`; disable that with `enable_parameter_schema_generation` if you do not need OpenAPI schemas on deployments.

```hcl
terraform {
  required_providers {
    prefect = {
      source  = "prefecthq/prefect"
      version = ">= 3, < 4"
    }
    external = {
      source  = "hashicorp/external"
      version = ">= 2, < 3"
    }
  }
}

provider "prefect" {
  # endpoint = "https://api.prefect.cloud/api/accounts/<id>/workspaces/<id>"
  # api_key  = var.prefect_api_key
}

module "demo_deployments" {
  source = "../modules/bulk_deploy"

  deploy_base_path = "${path.root}/../demos"

  # Optional
  demo_exclude_patterns              = ["\\.venv", "\\.git"]
  enable_parameter_schema_generation = true
}

output "deployment_ids" {
  value = module.demo_deployments.deployment_ids
}
```

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.0 |
| <a name="requirement_external"></a> [external](#requirement\_external) | >=2, <3 |
| <a name="requirement_prefect"></a> [prefect](#requirement\_prefect) | >=3, <4 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_external"></a> [external](#provider\_external) | >=2, <3 |
| <a name="provider_prefect"></a> [prefect](#provider\_prefect) | >=3, <4 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [prefect_automation.this](https://registry.terraform.io/providers/prefecthq/prefect/latest/docs/resources/automation) | resource |
| [prefect_deployment.this](https://registry.terraform.io/providers/prefecthq/prefect/latest/docs/resources/deployment) | resource |
| [prefect_deployment_schedule.this](https://registry.terraform.io/providers/prefecthq/prefect/latest/docs/resources/deployment_schedule) | resource |
| [prefect_flow.this](https://registry.terraform.io/providers/prefecthq/prefect/latest/docs/resources/flow) | resource |
| [external_external.schema](https://registry.terraform.io/providers/hashicorp/external/latest/docs/data-sources/external) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_deploy_base_path"></a> [deploy\_base\_path](#input\_deploy\_base\_path) | Base path containing folders with prefect.yaml definitions to be deployed. | `string` | n/a | yes |
| <a name="input_demo_exclude_patterns"></a> [demo\_exclude\_patterns](#input\_demo\_exclude\_patterns) | Regex patterns used to exclude subdirectories from deployment discovery. | `list(string)` | <pre>[<br/>  "\\.venv"<br/>]</pre> | no |
| <a name="input_enable_parameter_schema_generation"></a> [enable\_parameter\_schema\_generation](#input\_enable\_parameter\_schema\_generation) | Whether to dynamically generate deployment parameter OpenAPI schemas from flow entrypoints. | `bool` | `true` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_automation_ids"></a> [automation\_ids](#output\_automation\_ids) | Prefect automation IDs keyed by automation key. |
| <a name="output_demo_folders"></a> [demo\_folders](#output\_demo\_folders) | Discovered demo folders containing prefect.yaml files. |
| <a name="output_deployment_ids"></a> [deployment\_ids](#output\_deployment\_ids) | Prefect deployment IDs keyed by deployment key. |
| <a name="output_deployment_keys"></a> [deployment\_keys](#output\_deployment\_keys) | Stable deployment keys generated from folder and deployment name. |
| <a name="output_deployment_schedule_ids"></a> [deployment\_schedule\_ids](#output\_deployment\_schedule\_ids) | Prefect deployment schedule IDs keyed by schedule key. |
| <a name="output_deployments"></a> [deployments](#output\_deployments) | Sanitized deployment metadata keyed by deployment key. |
| <a name="output_flow_ids"></a> [flow\_ids](#output\_flow\_ids) | Prefect flow IDs keyed by flow name. |
<!-- END_TF_DOCS -->
