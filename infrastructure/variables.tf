variable "aws_region" {
  description = "AWS region for regional resources. Each availability zone is built as `region` + suffix (e.g. `us-east-1` + `a` → `us-east-1a`)."
  type        = string
}

variable "aws_vpc_cidr" {
  description = "IPv4 CIDR block for the VPC (e.g. `10.0.0.0/16`). Public subnets are derived from this with `cidrsubnet`."
  type        = string
}

variable "aws_vpc_azs" {
  description = "Suffixes for availability zones in this region (e.g. `a`, `b`, `c`). One public subnet is created per suffix."
  type        = set(string)
}

variable "aws_vpc_subnet_cidr_size" {
  description = "Additional host bits when splitting `aws_vpc_cidr` into public subnets (`cidrsubnet` newbits). Larger values yield smaller subnets."
  type        = number
  default     = 3
}

variable "aws_vpc_subnet_cidr_offset" {
  description = "Added to each subnet index before passing to `cidrsubnet`, shifting which slice of the VPC CIDR each AZ uses."
  type        = number
  default     = 1
}
