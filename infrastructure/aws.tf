# AWS ECS Push Work Pool
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.6"

  name = "prefect-demo-vpc"
  cidr = var.aws_vpc_cidr
  azs  = [for az in var.aws_vpc_azs : "${var.aws_region}${az}"]
  public_subnets = [
    for i in range(length(var.aws_vpc_azs)) :
    cidrsubnet(var.aws_vpc_cidr, var.aws_vpc_subnet_cidr_size, i + var.aws_vpc_subnet_cidr_offset)
  ]
}

module "ecs" {
  source  = "terraform-aws-modules/ecs/aws"
  version = "~> 7.5"

  region                                 = "us-east-1"
  cluster_name                           = "prefect-demo-push-pool"
  create_task_exec_iam_role              = true
  cloudwatch_log_group_retention_in_days = 7
  default_capacity_provider_strategy = {
    FARGATE_SPOT = {
      weight = 100
    }
  }
}

# ECS Push Work Pool Policy
module "iam_policy" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-policy"
  version = "~> 6.4"

  name = "prefect-ecs-push-worker-policy"

  policy = <<-EOF
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "ECSTaskDefinitionManagement",
          "Effect": "Allow",
          "Action": [
            "ecs:RegisterTaskDefinition",
            "ecs:DescribeTaskDefinition",
            "ecs:DeregisterTaskDefinition"
          ]
          "Resource": "*"
        },
        {
          "Sid": "ECSRunAndManageTasksOnCluster",
          "Effect": "Allow",
          "Action": [
            "ecs:RunTask",
            "ecs:DescribeTasks",
            "ecs:StopTask",
            "ecs:TagResource"
          ],
          "Resource": "*",
          "Condition": {
            "StringEquals": {
              "ecs:cluster": "${module.ecs.cluster_arn}",
            }
          }
        },
        {
          "Sid": "EC2NetworkDiscovery",
          "Effect": "Allow",
          "Action": [
            "ec2:DescribeVpcs",
            "ec2:DescribeSubnets"
          ],
          "Resource": "*"
        },
        {
          "Sid": "PassRoleToECS",
          "Effect": "Allow",
          "Action": "iam:PassRole",
          "Resource": [
            "${module.ecs.task_exec_iam_role_arn}",
            "${module.ecs_task_role.arn}"
          ],
          "Condition": {
            "StringEquals": {
              "iam:PassedToService": "ecs-tasks.amazonaws.com"
            }
          }
        }
      ]
    }
  EOF
}

# Note: You would need this module if you don't already have the 
# Prefect Cloud OIDC Provider registered in your AWS Account (once per account)
# module "iam_oidc_provider" {
#   source = "terraform-aws-modules/iam/aws//modules/iam-oidc-provider"
#   url = "https://api.prefect.cloud/oidc-provider"
# }

module "execution_iam_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role"
  version = "~> 6.4"

  enable_oidc        = true
  oidc_provider_urls = ["https://api.prefect.cloud/oidc-provider"]
  oidc_audiences     = ["prefect-cloud"]
  oidc_subjects      = ["prefect:account:${data.prefect_account.this.id}"]

  policies = {
    ECSPushPool = module.iam_policy.arn
  }
}

module "ecs_task_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role"
  version = "~> 6.4"

  trust_policy_permissions = {
    TrustRoleAndServiceToAssume = {
      actions = [
        "sts:AssumeRole",
        "sts:TagSession"
      ]
      principals = [
        {
          type        = "Service"
          identifiers = ["ecs-tasks.amazonaws.com"]
        }
      ]
    }
  }

  policies = {
    ECSTaskRole = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
  }
}

resource "prefect_work_pool" "ecs_push_pool" {
  name = "ecs-push-tf"
  type = "ecs:push"

  # prefect work-pool get-default-base-job-template --type ecs:push
  base_job_template = jsonencode({
    variables = {
      launch_type = "FARGATE" # this will be spot by default

      federated_identity = {
        kind            = "aws"
        aws_role_arn    = module.ecs_task_role.arn
        aws_region_name = var.aws_region
      }

      cluster = module.ecs.cluster_name

      vpc_id = module.vpc.vpc_id # required for FARGATE launch type

      network_configuration = {
        "Subnets" = module.vpc.public_subnets
      }

      configure_cloudwatch_logs = true

      execution_role_arn = module.ecs.task_exec_iam_role_arn # while starting
      task_role_arn      = module.ecs_task_role.arn          # while running
    }
  })
}
