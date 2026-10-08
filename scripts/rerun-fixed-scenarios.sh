#!/bin/bash
# scripts/rerun-fixed-scenarios.sh
# Re-run S07, S08, S10 yang sudah diperbaiki konfigurasi RPS-nya.
# S10 menggunakan static TTL (graph-analyzer di-scale ke 0 sementara)
# Usage: bash scripts/rerun-fixed-scenarios.sh [repetitions]

set -euo pipefail

REPETITIONS=${1:-30}
RUN_ID=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="load-testing/results/rerun_${RUN_ID}"
PROM_URL="http://10.43.182.20:9090"
mkdir -p "$RESULTS_DIR"

run_scenario() {
    local scenario=$1
    local rep=$2

    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    OUTFILE="${RESULTS_DIR}/${scenario}-rep${rep}-${TIMESTAMP}.json"

    echo "=============================="
    echo "Running: $scenario (rep $rep)"
    echo "=============================="

    # 1. Reset testbed
    echo "  Resetting testbed..."
    bash scripts/reset-light.sh 2>/dev/null || true

    # 2. Warmup
    echo "  Warming up (2 min)..."
    k6 run --quiet load-testing/warmup.js 2>/dev/null || true

    # 3. Cooldown
    echo "  Cooling down (30s)..."
    sleep 30

    # 4. Record start time
    START_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    # 5. Jalankan skenario
    echo "  Executing k6 scenario..."
    k6 run \
      --summary-export="$OUTFILE" \
      "load-testing/scenarios/${scenario}.js" || true

    # 6. Record end time
    END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    # 7. Export Prometheus metrics
    echo "  Exporting Prometheus metrics..."
    python3 scripts/export-metrics.py \
      --prometheus-url "$PROM_URL" \
      --scenario "$scenario" \
      --start "$START_TIME" \
      --end "$END_TIME" \
      --output "$RESULTS_DIR" \
      --repetition "$rep" 2>/dev/null || echo "  WARNING: metric export failed"

    echo "  Done: $scenario (rep $rep) → $OUTFILE"

    # 8. Cooldown antar skenario (2 menit)
    echo "  Cooldown (120s)..."
    sleep 120
}

echo "=========================================="
echo "ZTA Predictive Cache — Re-run Fixed Scenarios"
echo "Scenarios: S07 (graph-aware), S08 (mesh), S10 (static TTL)"
echo "Repetitions: $REPETITIONS"
echo "Results: $RESULTS_DIR"
echo "=========================================="

# ─────────────────────────────────────────────────────
# PHASE 1: S07 — Graph-aware TTL, Fan-out, 2000 RPS
# (graph-analyzer harus RUNNING untuk TTL dinamis)
# ─────────────────────────────────────────────────────
echo ""
echo "========== PHASE 1: S07 (Graph-aware TTL) =========="
echo "Ensuring graph-analyzer is running..."
kubectl scale deploy graph-analyzer -n zta-research --replicas=1
sleep 10
kubectl wait --for=condition=ready pod -l app=graph-analyzer -n zta-research --timeout=120s 2>/dev/null || true

for rep in $(seq 1 $REPETITIONS); do
    echo ""
    echo ">>> S07 REPETITION $rep / $REPETITIONS"
    run_scenario "s07-zta-cache-fanout" "$rep"
done

# ─────────────────────────────────────────────────────
# PHASE 2: S08 — Graph-aware TTL, Mesh, 2000 RPS
# (graph-analyzer tetap RUNNING)
# ─────────────────────────────────────────────────────
echo ""
echo "========== PHASE 2: S08 (Mesh Topology) =========="

for rep in $(seq 1 $REPETITIONS); do
    echo ""
    echo ">>> S08 REPETITION $rep / $REPETITIONS"
    run_scenario "s08-zta-cache-mesh" "$rep"
done

# ─────────────────────────────────────────────────────
# PHASE 3: S10 — Static TTL, Fan-out, 2000 RPS
# Scale graph-analyzer ke 0 → cache-distributor tidak dapat
# kandidat baru → TTL efektif = BaseTTL konstan (30s)
# ─────────────────────────────────────────────────────
echo ""
echo "========== PHASE 3: S10 (Static TTL) =========="
echo "Scaling down graph-analyzer for static TTL mode..."
kubectl scale deploy graph-analyzer -n zta-research --replicas=0
sleep 15
echo "Graph-analyzer scaled to 0. Cache will use static BaseTTL (30s)."

for rep in $(seq 1 $REPETITIONS); do
    echo ""
    echo ">>> S10 REPETITION $rep / $REPETITIONS"
    run_scenario "s10-ttl-comparison" "$rep"
done

# ─────────────────────────────────────────────────────
# RESTORE: Scale graph-analyzer kembali
# ─────────────────────────────────────────────────────
echo ""
echo "Restoring graph-analyzer..."
kubectl scale deploy graph-analyzer -n zta-research --replicas=1
sleep 10

echo ""
echo "=========================================="
echo "All 3 scenarios × $REPETITIONS repetitions complete."
echo "Results in: $RESULTS_DIR/"
echo ""
echo "S07: Graph-aware TTL, fan-out, 2000 RPS"
echo "S08: Graph-aware TTL, mesh, 2000 RPS"
echo "S10: Static TTL, fan-out, 2000 RPS"
echo "=========================================="
