variable "deploy_base_path" {
  type = string
}

variable "demo_exclude_patterns" {
  type = list(string)
  default = ["\\.venv"]
}

variable "enable_parameter_schema_generation" {
  type = bool
  default = true
}