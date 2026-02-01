#!/bin/bash
# Script para monitorar roteamento de queries em tempo real

echo "Monitoring query routing from DyraSQL Core..."
echo "Press Ctrl+C to stop"
echo ""

docker compose logs -f dyrasql-core 2>&1 | grep --line-buffered -E "(ROUTING|PROXY|Decision|cluster)" | while read line; do
    # Extrai informações relevantes
    if echo "$line" | grep -q "ROUTING"; then
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "$line" | sed 's/.*ROUTING: //'
    elif echo "$line" | grep -q "PROXY"; then
        echo "  → $line" | sed 's/.*PROXY: //'
    elif echo "$line" | grep -q "Decision:"; then
        echo "  [DECISION] $line" | sed 's/.*Decision: //'
    elif echo "$line" | grep -q "Query:"; then
        echo "  [QUERY] $line" | sed 's/.*Query: //'
    fi
done

