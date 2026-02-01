#!/bin/bash
# Script para configurar variáveis de ambiente nos arquivos de propriedades do Trino
# As credenciais AWS são lidas automaticamente do ~/.aws/credentials (montado como volume)
# Este script apenas configura AWS_REGION, S3_BUCKET e S3_PREFIX nos arquivos de propriedades

CONFIG_DIR="/etc/trino/catalog"

# Valores fixos - substitua pelos seus valores reais se necessário
# Ou leia do arquivo .env se preferir
region="us-east-1"
bucket="prod-cafdatalakehouse--ref"
prefix="dbt/prod_db_transient_ref/"

# Se quiser ler do arquivo .env, descomente as linhas abaixo:
# env_file="/root/.env"
# if [ -f "$env_file" ]; then
#     region=$(grep "^AWS_REGION=" "$env_file" | cut -d'=' -f2 | tr -d ' ' | tr -d '"' | tr -d "'" || echo "$region")
#     bucket=$(grep "^S3_BUCKET=" "$env_file" | cut -d'=' -f2 | tr -d ' ' | tr -d '"' | tr -d "'" || echo "$bucket")
#     prefix=$(grep "^S3_PREFIX=" "$env_file" | cut -d'=' -f2 | tr -d ' ' | tr -d '"' | tr -d "'" || echo "$prefix")
# fi

# Função para atualizar arquivos de propriedades do Trino
update_trino_config() {
    local config_file="$1"
    
    if [ -f "$config_file" ]; then
        # Reescreve o arquivo completamente com valores fixos
        # Detecta se é arquivo hive.properties ou iceberg.properties
        if echo "$config_file" | grep -q "hive.properties"; then
            cat > "$config_file" <<EOF
# Catálogo Hive - Necessário para fornecer filesystem S3 ao Iceberg connector
# O Iceberg connector precisa de um filesystem S3, que é fornecido pelo Hive connector
connector.name=hive
hive.metastore=glue
hive.metastore.glue.region=$region
hive.metastore.glue.default-warehouse-dir=s3://$bucket/$prefix

# Habilita filesystem S3 nativo (necessário para acessar S3)
fs.native-s3.enabled=true

# As credenciais AWS serão obtidas automaticamente do ~/.aws/credentials (montado como volume)
EOF
        elif echo "$config_file" | grep -q "iceberg.properties"; then
            cat > "$config_file" <<EOF
# Configuração do Iceberg connector com AWS Glue Catalog
connector.name=iceberg
iceberg.catalog.type=glue
iceberg.file-format=PARQUET

# Habilita filesystem S3 nativo (necessário para acessar S3)
fs.native-s3.enabled=true

# Configuração do Glue Catalog
# O warehouse padrão será usado do Glue Catalog
# As credenciais AWS serão obtidas automaticamente do ~/.aws/credentials (montado como volume)
EOF
        fi
        
        echo "  - Configurado arquivo: $config_file"
        echo "    AWS_REGION: $region"
        echo "    S3_BUCKET: $bucket"
        echo "    S3_PREFIX: $prefix"
    fi
}

# Atualiza todos os arquivos de configuração do catálogo (Iceberg e Hive)
for config_file in "$CONFIG_DIR"/*/*.properties; do
    if [ -f "$config_file" ]; then
        echo "Configurando arquivo: $config_file"
        update_trino_config "$config_file"
    fi
done

echo "Configuração concluída com sucesso!"
echo "Nota: As credenciais AWS são lidas automaticamente do ~/.aws/credentials (montado como volume)"

