variable "aws_region" {
  description = "Região AWS onde os recursos serão criados"
  type        = string
  default     = "us-east-1"
}

variable "dynamodb_table_name" {
  description = "Nome da tabela DynamoDB para histórico do DyraSQL"
  type        = string
  default     = "dyrasql-history"
}

variable "environment" {
  description = "Ambiente de deploy (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "enable_point_in_time_recovery" {
  description = "Habilita Point-in-Time Recovery para a tabela DynamoDB"
  type        = bool
  default     = false
}

variable "common_tags" {
  description = "Tags comuns aplicadas a todos os recursos"
  type        = map(string)
  default = {
    Project = "DyraSQL"
    ManagedBy = "Terraform"
  }
}

