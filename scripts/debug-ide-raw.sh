#!/bin/bash
# Script para ver logs brutos do que a IDE envia para a porta 5001

echo "Monitoring Raw Logs - IDE → DyraSQL Core (port 5001)"
echo "=============================================================="
echo ""
echo "Execute a query in DataSpell NOW!"
echo "Press Ctrl+C to stop"
echo ""

docker compose logs -f dyrasql-core 2>&1 | while read line; do
    # Mostra todas as linhas que contêm informações sobre requisições
    if echo "$line" | grep -qE "(REQUEST RECEIVED|ROUTING|EXECUTING|RESPONSE|Query received|ANALYSIS|CACHE|Score|Factors|Cluster selected)"; then
        # Remove prefixo do container
        clean_line=$(echo "$line" | sed 's/.*dyrasql-core[^|]*| //')
        echo "$clean_line"
    fi
done

