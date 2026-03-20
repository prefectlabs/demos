# Prefect Demo Environment

This repository contains example code, configuration files, and tooling that powers the Prefect sales engineering demo environment. 

Its primary purpose is to provide transparency and simplicity, ensuring that everything demonstrated to customers can be easily replicated and explored independently.

## Why Are we Sharing This?

* **Transparency**: Everything shown during demos is publicly available here.
* **Ease of Use**: Quickly replicate the demo environment locally or in your own cloud infrastructure.
* **Learning**: Use this as a learning resource to understand how Prefect works in practice.
* **Dogfooding**: We want to demonstrate the capabilities of Prefect by using our own tooling.

## Getting Started

To get started, simply clone this repository with its submodules:

```bash
git clone --recurse-submodules https://github.com/prefectlabs/demos.git
```

To deploy a demo, navigate to the relevant directory in the [`demos`](demos/) folder and run `prefect deploy` and follow the on-screen prompts.

## How this Repository is Organized

- `demos/`: Contains individual demo scenarios, each in its own subdirectory.
- `infrastructure/`: Contains Terraform and other infrastructure-as-code configurations for setting up the demo environment.

### Why `prefect.yaml` and `prefect_deployment`?

This repository uses `prefect.yaml` files as the authoring interface for defining Prefect deployments and automations. Our Terraform state management consumes these files at plan time using `fileset()` for discovery and `yamldecode()` for parsing, then maps the resulting configuration onto the appropriate Terraform-managed `prefect_deployment` resource.

This approach was chosen for three reasons:

First, it preserves the native Prefect authoring experience. Contributors define resources using the same YAML format that Prefect's own CLI and documentation support. No knowledge of HCL or Terraform internals is required to add or modify a demo here — the interface is a standard `prefect.yaml` file and a pull request.

Second, it keeps each demo scenario self-contained. Every demo lives in its own subfolder with its own `prefect.yaml`, making it easy to add, remove, or modify demos independently without affecting the rest of the repository. Terraform discovers these files automatically, so authors can focus on building content not managing infrastructure.

Finally, it ensures that all demo resources are managed through Terraform's plan/apply lifecycle. This provides state tracking, drift detection, dependency ordering, and a full audit trail for every change. No resources are created or modified out of band.

## Contributing

Please see our contributing guide: https://docs.prefect.io/contribute