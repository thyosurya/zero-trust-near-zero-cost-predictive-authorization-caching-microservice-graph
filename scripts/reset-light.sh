#!/bin/bash
# scripts/reset-light.sh

echo "[RESET RINGAN] Flushing cache dan counter..."

# Flush local cache semua sidecar via restart Cache Distributor
kubectl rollout restart deployment/cache-distributor -n zta-research
kubectl wait --for=condition=ready pod -l app=cache-distributor -n zta-research --timeout=60s

# Reset graph topologi
curl -s -X DELETE http://graph-analyzer.zta-research:8080/graph/reset \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" | jq .

echo "[RESET RINGAN] Selesai. Cooldown 30 detik..."
sleep 30
