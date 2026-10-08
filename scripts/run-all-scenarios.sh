#!/bin/bash
# scripts/run-all-scenarios.sh
# Menjalankan semua 10 skenario eksperimen dengan repetisi
# Usage: bash scripts/run-all-scenarios.sh [repetitions]

set -euo pipefail

REPETITIONS=${1:-30}
RUN_ID=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="load-testing/results/run_${RUN_ID}"
mkdir -p "$RESULTS_DIR"

SCENARIOS=(
    "s01-pbs-baseline-500rps"
    "s02-zta-naive-500rps"
    "s03-zta-cache-500rps"
    "s04-zta-naive-2000rps"
    "s05-zta-cache-2000rps"
    "s06-zta-cache-5000rps"
    "s07-zta-cache-fanout"
    "s08-zta-cache-mesh"
    "s09-revocation-test"
    "s10-ttl-comparison"
)

echo "=========================================="
echo "ZTA Predictive Cache — Experiment Runner"
echo "Scenarios: ${#SCENARIOS[@]}"
echo "Repetitions: $REPETITIONS"
echo "=========================================="

for rep in $(seq 1 $REPETITIONS); do
    echo ""
    echo ">>> REPETITION $rep / $REPETITIONS"
    echo ""

    for scenario in "${SCENARIOS[@]}"; do
        TIMESTAMP=$(date +%Y%m%d-%H%M%S)
        OUTFILE="${RESULTS_DIR}/${scenario}-rep${rep}-${TIMESTAMP}.json"

        echo "=============================="
        echo "Running: $scenario (rep $rep)"
        echo "=============================="

        # 1. Reset testbed — clear cache dan state
        echo "  Resetting testbed..."
        bash scripts/reset-light.sh 2>/dev/null || true

        # 2. Warmup (5 menit, low rate)
        echo "  Warming up..."
        k6 run --quiet load-testing/warmup.js 2>/dev/null || true

        # 3. Cooldown sebelum test (30 detik)
        echo "  Cooling down (30s)..."
        sleep 30

        # 4. Record start time untuk metric export
        START_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

        # 4b. Jika skenario adalah s10, pastikan graph-analyzer di-scale ke 0 untuk mode Static TTL
        if [[ "$scenario" == "s10-ttl-comparison" ]]; then
            echo "  [S10 detected] Scaling down graph-analyzer to 0 for Static TTL mode..."
            kubectl scale deploy graph-analyzer -n zta-research --replicas=0
            sleep 15
        else
            # Untuk skenario lain, pastikan graph-analyzer aktif (1 replica)
            # Terutama setelah S10 selesai atau untuk skenario awal
            CURRENT_REPLICAS=$(kubectl get deploy graph-analyzer -n zta-research -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
            if [[ "$CURRENT_REPLICAS" -eq 0 ]]; then
                echo "  Scaling graph-analyzer back up to 1 replica..."
                kubectl scale deploy graph-analyzer -n zta-research --replicas=1
                sleep 10
                kubectl wait --for=condition=ready pod -l app=graph-analyzer -n zta-research --timeout=120s 2>/dev/null || true
            fi
        fi

        # 5. Jalankan skenario
        echo "  Executing k6 scenario..."
        k6 run \
          --summary-export="$OUTFILE" \
          "load-testing/scenarios/${scenario}.js" || true

        # 6. Record end time
        END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

        # 6b. Kembalikan replica jika baru selesai menjalankan S10
        if [[ "$scenario" == "s10-ttl-comparison" ]]; then
            echo "  Restoring graph-analyzer deployment to 1 replica..."
            kubectl scale deploy graph-analyzer -n zta-research --replicas=1
            sleep 10
        fi

        # 7. Export Prometheus metrics
        echo "  Exporting Prometheus metrics..."
        python3 scripts/export-metrics.py \
          --prometheus-url http://10.43.182.20:9090 \
          --scenario "$scenario" \
          --start "$START_TIME" \
          --end "$END_TIME" \
          --output "$RESULTS_DIR" \
          --repetition "$rep" 2>/dev/null || echo "  WARNING: metric export failed"

        echo "  Done: $scenario (rep $rep) → $OUTFILE"

        # 8. Cooldown antar skenario (2 menit)
        echo "  Cooldown (120s)..."
        sleep 120
    done
done

echo ""
echo "=========================================="
echo "All ${#SCENARIOS[@]} scenarios × $REPETITIONS repetitions complete."
echo "Results in: $RESULTS_DIR/"
echo ""
echo "Next steps:"
echo "  1. Merge k6 results: python3 scripts/merge-k6-results.py"
echo "  2. Statistical analysis: python3 scripts/statistical-analysis.py"
echo "=========================================="
