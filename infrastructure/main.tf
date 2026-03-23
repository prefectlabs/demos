module "demos" {
  source = "./modules/bulk_deploy"

  deploy_base_path = "${path.module}/../demos"
}
