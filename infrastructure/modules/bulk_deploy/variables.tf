variable "deploy_base_path" {
  description = "Base path containing folders with prefect.yaml definitions to be deployed."
  type        = string
}

variable "demo_exclude_patterns" {
  description = "Regex patterns used to exclude subdirectories from deployment discovery."
  type        = list(string)
  default     = ["\\.venv"]
}

variable "enable_parameter_schema_generation" {
  description = "Whether to dynamically generate deployment parameter OpenAPI schemas from flow entrypoints."
  type        = bool
  default     = true
}