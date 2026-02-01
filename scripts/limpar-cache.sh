#!/bin/bash
# Script para limpar o cache do DynamoDB (decisões de roteamento)

echo "Clearing DyraSQL Core cache..."
echo ""

# Verifica se o DynamoDB está rodando
if ! docker compose ps | grep -q dynamodb; then
    echo "ERROR: DynamoDB is not running!"
    exit 1
fi

# Executa script Python dentro do container dyrasql-core para limpar cache
docker compose exec -T dyrasql-core python3 << 'EOF'
from history_manager import HistoryManager
import boto3
from botocore.exceptions import ClientError

try:
    hm = HistoryManager()
    
    # Lista todas as entradas
    print("Listing cache entries...")
    response = hm.dynamodb.scan(TableName=hm.table_name)
    items = response.get('Items', [])
    
    if not items:
        print("SUCCESS: Cache is already empty!")
    else:
        print(f"   Found {len(items)} entries in cache")
        
        # Deleta todas as entradas
        print("Deleting entries...")
        deleted = 0
        for item in items:
            fingerprint = item['fingerprint']['S']
            try:
                hm.dynamodb.delete_item(
                    TableName=hm.table_name,
                    Key={'fingerprint': {'S': fingerprint}}
                )
                deleted += 1
            except ClientError as e:
                print(f"   WARNING: Error deleting {fingerprint[:16]}...: {e}")
        
        print(f"SUCCESS: {deleted} entries deleted from cache!")
        print("")
        print("INFO: Now execute new queries in DataSpell to see dynamic routing!")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
EOF

echo ""
echo "SUCCESS: Cache cleared!"

