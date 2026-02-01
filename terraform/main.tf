terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  
  # Usa credenciais do ~/.aws ou variáveis de ambiente
  # Não precisa especificar explicitamente se já configurado
}

# Tabela DynamoDB para histórico e cache do DyraSQL
resource "aws_dynamodb_table" "dyrasql_history" {
  name           = var.dynamodb_table_name
  billing_mode   = "PAY_PER_REQUEST" # On-demand billing
  hash_key       = "fingerprint"

  attribute {
    name = "fingerprint"
    type = "S"
  }

  # Habilita TTL para expiração automática de cache
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  # Tags para organização
  tags = merge(
    var.common_tags,
    {
      Name        = var.dynamodb_table_name
      Project     = "DyraSQL"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  )

  # Point-in-time recovery (opcional, mas recomendado)
  point_in_time_recovery {
    enabled = var.enable_point_in_time_recovery
  }

  # Server-side encryption
  server_side_encryption {
    enabled = true
  }
}

