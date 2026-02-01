output "dynamodb_table_name" {
  description = "Nome da tabela DynamoDB criada"
  value       = aws_dynamodb_table.dyrasql_history.name
}

output "dynamodb_table_arn" {
  description = "ARN da tabela DynamoDB criada"
  value       = aws_dynamodb_table.dyrasql_history.arn
}

output "dynamodb_table_id" {
  description = "ID da tabela DynamoDB criada"
  value       = aws_dynamodb_table.dyrasql_history.id
}

output "dynamodb_table_stream_arn" {
  description = "ARN do stream da tabela DynamoDB (se habilitado)"
  value       = aws_dynamodb_table.dyrasql_history.stream_arn
}

