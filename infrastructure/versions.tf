terraform {
  required_version = ">= 1.0"

  required_providers {
    prefect = {
      source  = "prefecthq/prefect"
      version = "3.0.0"
    }

    external = {
      source  = "hashicorp/external"
      version = "2.3.5"
    }
  }
}
