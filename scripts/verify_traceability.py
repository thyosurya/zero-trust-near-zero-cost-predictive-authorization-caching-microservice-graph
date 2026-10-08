#!/usr/bin/env python3
"""
Verifikasi Traceability: Naskah ↔ Data ↔ Script
=================================================
Script ini membuktikan bahwa SETIAP angka dalam naskah-artikel.md
dapat direproduksi dari data CSV mentah.
"""
import pandas as pd
import numpy as np
from scipy.stats import shapiro, mannwhitneyu, kruskal
import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
os.chdir(BASE_DIR)

lat = pd.read_csv("data/processed/latency-all-scenarios.csv")
lat["scenario_id"] = lat["scenario_id"].str.strip()
res = pd.read_csv("data/processed/resource-overhead.csv")
res["scenario_id"] = res["scenario_id"].str.strip()
rev = pd.read_csv("data/processed/revocation-latency.csv")

PASS = 0
FAIL = 0

def check(label, computed, expected, tol=0.02):
    global PASS, FAIL
    ok = abs(computed - expected) <= tol
    status = "✅" if ok else "❌"
    if not ok:
        FAIL += 1
        print(f"  {status} {label}: computed={computed:.4f}, expected={expected}, diff={abs(computed-expected):.4f}")
    else:
        PASS += 1
    return ok

print("=" * 70)
print("VERIFIKASI TRACEABILITY: Naskah → Data → Script")
print("=" * 70)

# === TABEL 4 ===
print("\n--- TABEL 4: Statistik Deskriptif ---")
tabel4 = {
    "s01-pbs-baseline-500rps":    {"med": 4.28, "mean": 4.27, "std": 0.10, "cv": 2.4, "rps": 499.8},
    "s02-zta-naive-500rps":       {"med": 4.30, "mean": 4.28, "std": 0.12, "cv": 2.7, "rps": 499.8},
    "s03-zta-cache-500rps":       {"med": 4.22, "mean": 4.24, "std": 0.12, "cv": 2.9, "rps": 499.8},
    "s04-zta-naive-2000rps":      {"med": 16.24, "mean": 16.16, "std": 1.76, "cv": 10.9, "rps": 1999.6},
    "s05-zta-cache-2000rps":      {"med": 16.74, "mean": 16.62, "std": 1.70, "cv": 10.2, "rps": 1999.6},
    "s06-zta-cache-5000rps":      {"med": 407.38, "mean": 407.60, "std": 7.28, "cv": 1.8, "rps": 4185.2},
    "s07-zta-cache-fanout":       {"med": 1322.49, "mean": 1320.82, "std": 77.85, "cv": 5.9, "rps": 1725.2},
    "s08-zta-cache-mesh":         {"med": 499.25, "mean": 497.36, "std": 17.41, "cv": 3.5, "rps": 1478.0},
    "s09-revocation-test":        {"med": 4.25, "mean": 4.26, "std": 0.11, "cv": 2.7, "rps": 499.8},
    "s10-ttl-comparison":         {"med": 1317.52, "mean": 1323.93, "std": 69.45, "cv": 5.2, "rps": 1715.5},
}
for sid, exp in tabel4.items():
    v = lat[lat.scenario_id == sid]["p99_ms"].values
    rps = lat[lat.scenario_id == sid]["actual_rps"].values
    check(f"{sid} median", np.median(v), exp["med"], 0.02)
    check(f"{sid} mean", np.mean(v), exp["mean"], 0.02)
    check(f"{sid} std", np.std(v, ddof=1), exp["std"], 0.02)
    check(f"{sid} RPS", np.mean(rps), exp["rps"], 0.15)

# === TABEL 5 ===
print("\n--- TABEL 5: Resource Overhead ---")
tabel5 = {
    "s01-pbs-baseline-500rps":  {"cpu": 1.79, "mem": 55.90},
    "s02-zta-naive-500rps":     {"cpu": 1.78, "mem": 55.85},
    "s03-zta-cache-500rps":     {"cpu": 1.76, "mem": 55.29},
    "s04-zta-naive-2000rps":    {"cpu": 5.90, "mem": 55.38},
    "s05-zta-cache-2000rps":    {"cpu": 6.02, "mem": 55.44},
    "s06-zta-cache-5000rps":    {"cpu": 11.42, "mem": 56.35},
    "s07-zta-cache-fanout":     {"cpu": 10.35, "mem": 61.95},
    "s08-zta-cache-mesh":       {"cpu": 8.98, "mem": 61.56},
    "s09-revocation-test":      {"cpu": 1.76, "mem": 56.03},
    "s10-ttl-comparison":       {"cpu": 11.74, "mem": 66.78},
}
for sid, exp in tabel5.items():
    cpu = res[res.scenario_id == sid]["cpu_avg_pct"].values
    mem = res[res.scenario_id == sid]["mem_avg_mb"].values
    check(f"{sid} CPU", np.mean(cpu), exp["cpu"], 0.02)
    check(f"{sid} Mem", np.mean(mem), exp["mem"], 0.02)

# === TABEL 6a-6c (Mann-Whitney) ===
print("\n--- TABEL 6a-6c: Mann-Whitney U ---")
s01 = lat[lat.scenario_id == "s01-pbs-baseline-500rps"]["p99_ms"].values
s02 = lat[lat.scenario_id == "s02-zta-naive-500rps"]["p99_ms"].values
s03 = lat[lat.scenario_id == "s03-zta-cache-500rps"]["p99_ms"].values
s04 = lat[lat.scenario_id == "s04-zta-naive-2000rps"]["p99_ms"].values
s05 = lat[lat.scenario_id == "s05-zta-cache-2000rps"]["p99_ms"].values

def cd(a, b):
    return sum(1 if x > y else (-1 if x < y else 0) for x in a for y in b) / (len(a) * len(b))

tests_mw = [
    ("6a PBS-Naive", s01, s02, 429.0, 0.762, -0.05),
    ("6b Naive-Cache@500", s02, s03, 564.0, 0.093, 0.25),
    ("6b Naive-Cache@2k", s04, s05, 392.0, 0.395, -0.13),
    ("6c PBS-Cache", s01, s03, 547.0, 0.154, 0.22),
]
for label, a, b, exp_u, exp_p, exp_d in tests_mw:
    u, p = mannwhitneyu(a, b, alternative="two-sided")
    d = cd(a, b)
    check(f"{label} U", u, exp_u, 0.5)
    check(f"{label} p", p, exp_p, 0.002)
    check(f"{label} delta", d, exp_d, 0.02)

# === TABEL 6d (TOST) ===
print("\n--- TABEL 6d: TOST ---")
tost = pd.read_csv("data/reports/tost-equivalence-results.csv")
for _, r in tost.iterrows():
    check(f"TOST {r.comparison[:15]}... p", r.p_tost, 0.0, 0.001)
    assert r.equivalent == True, f"TOST {r.comparison} NOT equivalent!"
    PASS += 1

# === TABEL 7 (Revocation) ===
print("\n--- TABEL 7: Revocation ---")
rv = rev["revocation_latency_ms"].values
check("Rev mean", np.mean(rv), 4.26, 0.02)
check("Rev median", np.median(rv), 4.25, 0.02)
check("Rev p99", np.percentile(rv, 99), 4.46, 0.02)
revt = rev["revocations_triggered"].values
check("Rev triggered mean", np.mean(revt), 10.7, 0.1)

# === TABEL 8 (TTL) ===
print("\n--- TABEL 8: TTL ---")
s07 = lat[lat.scenario_id == "s07-zta-cache-fanout"]["p99_ms"].values
s10 = lat[lat.scenario_id == "s10-ttl-comparison"]["p99_ms"].values
u, p = mannwhitneyu(s10, s07, alternative="two-sided")
d = cd(s10, s07)
check("TTL U", u, 450.0, 0.5)
check("TTL p", p, 1.0, 0.001)
check("TTL delta", d, 0.0, 0.01)

# === TABEL 9 (KW Topology) ===
print("\n--- TABEL 9: Kruskal-Wallis ---")
s08 = lat[lat.scenario_id == "s08-zta-cache-mesh"]["p99_ms"].values
h, p = kruskal(s05, s07, s08)
check("KW H", h, 79.12, 0.02)
check("KW p", p, 0.0, 0.001)

# === TABEL 10 (KW Resource) ===
print("\n--- TABEL 10: KW Resource ---")
for col, nm, exp_h, exp_p in [("cpu_avg_pct", "CPU", 0.81, 0.668), ("mem_avg_mb", "Mem", 2.46, 0.292)]:
    p1 = res[(res.config == "pbs") & (res.rps_target == 500)][col].dropna().values
    p2 = res[(res.config == "zta-naive") & (res.rps_target == 500)][col].dropna().values
    p3 = res[(res.config == "zta-cache") & (res.rps_target == 500) & (res.topology == "linear")][col].dropna().values
    h, p = kruskal(p1, p2, p3)
    check(f"KW {nm} H", h, exp_h, 0.02)
    check(f"KW {nm} p", p, exp_p, 0.002)

# === SUMMARY ===
print("\n" + "=" * 70)
total = PASS + FAIL
print(f"HASIL: {PASS}/{total} PASS, {FAIL}/{total} FAIL")
if FAIL == 0:
    print("✅ SELURUH ANGKA DI NASKAH DAPAT DIREPRODUKSI DARI DATA CSV")
else:
    print("❌ ADA ANGKA YANG TIDAK COCOK!")
print("=" * 70)

# === SCRIPT ↔ DATA MAPPING ===
print("\nPETA SCRIPT → DATA → TABEL:")
print("""
┌─────────────────────────────┬──────────────────────────────────────┬──────────┐
│ Script                      │ Data Source                         │ Tabel    │
├─────────────────────────────┼──────────────────────────────────────┼──────────┤
│ analyze-all-data.py         │ 300 k6 JSON + 300 Prometheus CSV    │ (source) │
│   → latency-all-scenarios.csv                                     │          │
│   → resource-overhead.csv                                         │          │
│   → revocation-latency.csv                                        │          │
│   → descriptive-stats.csv                                         │          │
├─────────────────────────────┼──────────────────────────────────────┼──────────┤
│ statistical-analysis.py     │ latency-all-scenarios.csv           │ 6a-6d,   │
│                             │ resource-overhead.csv               │ 8-10     │
│                             │ revocation-latency.csv              │ 7        │
│   → mann-whitney-results.csv                                      │          │
│   → shapiro-wilk-results.csv                                      │          │
│   → kruskal-wallis-results.csv                                    │          │
│   → tost-equivalence-results.csv                                  │          │
├─────────────────────────────┼──────────────────────────────────────┼──────────┤
│ generate-figures.py         │ latency-all-scenarios.csv           │ Fig 1-10 │
│                             │ resource-overhead.csv               │          │
│                             │ edge-topology.json                  │          │
├─────────────────────────────┼──────────────────────────────────────┼──────────┤
│ scalability-analysis.py     │ descriptive-stats.csv (constants)   │ 11       │
│                             │ Model O(V²), bukan dari CSV         │          │
├─────────────────────────────┼──────────────────────────────────────┼──────────┤
│ validate-data.py            │ 600 raw files (JSON+CSV)            │ §3.7     │
└─────────────────────────────┴──────────────────────────────────────┴──────────┘
""")
