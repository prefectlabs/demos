terraform {
  required_version = ">= 1.0"

  required_providers {
    prefect = {
      source  = "prefecthq/prefect"
      version = ">=3, <4"
    }

    external = {
      source  = "hashicorp/external"
      version = ">=2, <3"
    }
  }
}
