#!/usr/bin/env python3
r"""
Analisis Statistik — ZTA Predictive Authorization Caching
==========================================================

Script ini mengimplementasikan seluruh prosedur uji statistik yang digunakan
dalam penelitian "Algoritma Predictive Authorization Caching Berbasis Graph
Topology untuk Micro-Segmentation: Reduksi Overhead Latensi pada Zero Trust
Service Mesh".

Formalisasi Persamaan Matematika
---------------------------------

Persamaan (3): Uji Normalitas Shapiro-Wilk
    W = (Σ aᵢ x₍ᵢ₎)² / Σ (xᵢ - x̄)²

    di mana:
    - x₍ᵢ₎  : statistik urut ke-i dari sampel
    - aᵢ     : koefisien Shapiro-Wilk yang diturunkan dari mean, varians,
               dan kovarians statistik urut distribusi normal
    - x̄      : rata-rata sampel
    - n      : ukuran sampel

    Keputusan: H₀ (data berdistribusi normal) ditolak jika p < α (α = 0,05).

Persamaan (4): Uji Mann-Whitney U
    U = n₁n₂ + n₁(n₁ + 1)/2 - R₁

    di mana:
    - n₁, n₂ : ukuran sampel kelompok 1 dan 2
    - R₁     : jumlah rank kelompok 1

    Hipotesis dua sisi: H₀: P(X > Y) = P(Y > X)
    Keputusan: H₀ ditolak jika p < α (α = 0,05).

Persamaan (5): Cliff's Delta (δ)
    δ = (#{xᵢ > yⱼ} - #{xᵢ < yⱼ}) / (n₁ × n₂)

    di mana:
    - #{xᵢ > yⱼ} : jumlah pasangan di mana xᵢ > yⱼ (dominance)
    - #{xᵢ < yⱼ} : jumlah pasangan di mana xᵢ < yⱼ
    - n₁, n₂     : ukuran sampel masing-masing kelompok

    Interpretasi effect size (Romano et al., 2006):
    - |δ| < 0,147  : negligible
    - 0,147 ≤ |δ| < 0,330 : small
    - 0,330 ≤ |δ| < 0,474 : medium
    - |δ| ≥ 0,474  : large

Persamaan (6): Uji Kruskal-Wallis H
    H = [12 / N(N+1)] × Σ (Rⱼ²/nⱼ) - 3(N+1)

    di mana:
    - N   : total ukuran sampel (Σ nⱼ)
    - k   : jumlah kelompok
    - nⱼ  : ukuran sampel kelompok ke-j
    - Rⱼ  : jumlah rank kelompok ke-j

    Hipotesis: H₀: semua distribusi kelompok identik.
    Keputusan: H₀ ditolak jika p < α (α = 0,05).
    Post-hoc: Mann-Whitney berpasangan dengan koreksi Bonferroni (α' = α/k').

Persamaan (11): Uji Kesetaraan TOST (Two One-Sided Tests)
    H₀₁: θ ≤ -Δ  vs  H₁₁: θ > -Δ   (uji batas bawah)
    H₀₂: θ ≥ +Δ  vs  H₁₂: θ < +Δ   (uji batas atas)

    di mana:
    - θ   : parameter lokasi perbedaan (location shift)
    - Δ   : margin kesetaraan (equivalence margin)
    - p_TOST = max(p₁, p₂)

    Keputusan: Kesetaraan diterima jika p_TOST < α.
    Margin Δ ditetapkan sebagai 5% dari median baseline:
        Δ = 0,05 × median_baseline

    Referensi: Schuirmann (1987); Lakens (2017).

Persamaan (12): Bootstrap Confidence Interval untuk Median
    CI(1-α) = [θ*_(α/2) , θ*_(1-α/2)]

    di mana:
    - θ*_(q) : kuantil ke-q dari distribusi bootstrap
    - B      : jumlah resampling (B = 10.000)

    Metode: percentile bootstrap (Efron & Tibshirani, 1993).

Referensi
----------
- Shapiro, S. S., & Wilk, M. B. (1965). An analysis of variance test for
  normality. Biometrika, 52(3/4), 591–611.
- Mann, H. B., & Whitney, D. R. (1947). On a test of whether one of two
  random variables is stochastically larger than the other. The Annals of
  Mathematical Statistics, 18(1), 50–60.
- Cliff, N. (1993). Dominance statistics: Ordinal analyses to answer ordinal
  questions. Psychological Bulletin, 114(3), 494–509.
- Romano, J., et al. (2006). Appropriate statistics for ordinal level data.
  Journal of Modern Applied Statistical Methods, 5(1), 231–236.
- Kruskal, W. H., & Wallis, W. A. (1952). Use of ranks in one-criterion
  variance analysis. JASA, 47(260), 583–621.
- Schuirmann, D. J. (1987). A comparison of the two one-sided tests procedure
  and the power approach for assessing the equivalence of average
  bioavailability. Journal of Pharmacokinetics and Biopharmaceutics, 15(6),
  657–680.
- Efron, B., & Tibshirani, R. J. (1993). An Introduction to the Bootstrap.
  Chapman & Hall/CRC.
- Walpole, R. E., et al. (2020). Probability & Statistics for Engineers &
  Scientists (10th ed.). Pearson.

Output: data/reports/mann-whitney-results.csv, data/reports/kruskal-wallis-results.csv,
        data/reports/tost-equivalence-results.csv
"""

import csv
import os
import sys
import numpy as np
import pandas as pd
from scipy import stats

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


def load_data(filepath: str) -> pd.DataFrame:
    """Memuat dataset CSV ke pandas DataFrame."""
    return pd.read_csv(filepath)


def shapiro_wilk(data: np.ndarray, label: str) -> dict:
    r"""
    Uji normalitas Shapiro-Wilk — Persamaan (3).

    Menguji hipotesis nol H₀: data berasal dari distribusi normal.

    Statistik uji:

        W = (Σᵢ₌₁ⁿ aᵢ x₍ᵢ₎)² / Σᵢ₌₁ⁿ (xᵢ - x̄)²

    Parameters
    ----------
    data : np.ndarray
        Array observasi (minimal n ≥ 3).
    label : str
        Label identifikasi kelompok untuk pelaporan.

    Returns
    -------
    dict
        Berisi kunci: label, W, p_value, normal (bool), n.
    """
    if len(data) < 3:
        print(f"  Shapiro-Wilk [{label}]: SKIP (n={len(data)} < 3)")
        return {"label": label, "W": None, "p_value": None, "normal": None, "n": len(data)}

    w_stat, p_value = stats.shapiro(data)
    is_normal = p_value > 0.05

    print(f"  Shapiro-Wilk [{label}]: W={w_stat:.4f}, p={p_value:.6f} "
          f"→ {'Normal (H₀ diterima)' if is_normal else 'Non-normal (H₀ ditolak)'}")

    return {
        "label": label,
        "W": round(w_stat, 4),
        "p_value": round(p_value, 6),
        "normal": is_normal,
        "n": len(data),
    }


def cliffs_delta(group_a: np.ndarray, group_b: np.ndarray) -> tuple:
    r"""
    Menghitung Cliff's Delta (δ) — Persamaan (5).

    Effect size non-parametrik untuk dua kelompok independen.

        δ = (#{xᵢ > yⱼ} - #{xᵢ < yⱼ}) / (n₁ × n₂)

    Interpretasi (Romano et al., 2006):
        |δ| < 0,147  → negligible
        0,147 ≤ |δ| < 0,330 → small
        0,330 ≤ |δ| < 0,474 → medium
        |δ| ≥ 0,474  → large

    Parameters
    ----------
    group_a, group_b : np.ndarray
        Data dua kelompok yang dibandingkan.

    Returns
    -------
    tuple(float, str)
        (nilai δ, interpretasi effect size)
    """
    n1, n2 = len(group_a), len(group_b)
    dominance = sum(
        1 if a > b else (-1 if a < b else 0)
        for a in group_a for b in group_b
    )
    delta = dominance / (n1 * n2)

    abs_d = abs(delta)
    if abs_d < 0.147:
        effect = "negligible"
    elif abs_d < 0.330:
        effect = "small"
    elif abs_d < 0.474:
        effect = "medium"
    else:
        effect = "large"

    return round(delta, 4), effect


def mann_whitney_u(group_a: np.ndarray, group_b: np.ndarray,
                   label_a: str, label_b: str) -> dict:
    r"""
    Uji Mann-Whitney U dua sisi — Persamaan (4) + Effect Size Persamaan (5).

    Menguji hipotesis nol H₀: P(X > Y) = P(Y > X), yaitu kedua kelompok
    berasal dari distribusi yang identik.

    Statistik uji:

        U = n₁n₂ + n₁(n₁+1)/2 - R₁

    Dilengkapi dengan Cliff's Delta (δ) sebagai ukuran effect size
    non-parametrik.

    Parameters
    ----------
    group_a, group_b : np.ndarray
        Data dua kelompok independen.
    label_a, label_b : str
        Label identifikasi masing-masing kelompok.

    Returns
    -------
    dict
        Berisi: comparison, n_a, n_b, median_a, median_b, mean_a, mean_b,
        u_statistic, p_value, significant, cliffs_delta, effect_size,
        reduction_pct.
    """
    u_stat, p_value = stats.mannwhitneyu(group_a, group_b, alternative="two-sided")
    delta, effect = cliffs_delta(group_a, group_b)

    median_a = np.median(group_a)
    median_b = np.median(group_b)

    return {
        "comparison":    f"{label_a} vs {label_b}",
        "n_a":           len(group_a),
        "n_b":           len(group_b),
        "median_a":      round(median_a, 4),
        "median_b":      round(median_b, 4),
        "mean_a":        round(np.mean(group_a), 4),
        "mean_b":        round(np.mean(group_b), 4),
        "u_statistic":   round(u_stat, 2),
        "p_value":       round(p_value, 6),
        "significant":   p_value < 0.05,
        "cliffs_delta":  delta,
        "effect_size":   effect,
        "reduction_pct": round((1 - median_b / median_a) * 100, 2) if median_a != 0 else None,
    }


def kruskal_wallis_h(*groups, labels: list) -> dict:
    r"""
    Uji Kruskal-Wallis H — Persamaan (6).

    Menguji hipotesis nol H₀: semua k distribusi kelompok identik.

    Statistik uji:

        H = [12 / N(N+1)] × Σⱼ₌₁ᵏ (Rⱼ²/nⱼ) - 3(N+1)

    Parameters
    ----------
    *groups : np.ndarray
        Data masing-masing kelompok (minimal 3 kelompok).
    labels : list of str
        Label identifikasi masing-masing kelompok.

    Returns
    -------
    dict
        Berisi: groups, h_statistic, p_value, significant.
    """
    h_stat, p_value = stats.kruskal(*groups)
    return {
        "groups":      " | ".join(labels),
        "h_statistic": round(h_stat, 2),
        "p_value":     round(p_value, 6),
        "significant": p_value < 0.05,
    }


def tost_equivalence(group_a: np.ndarray, group_b: np.ndarray,
                     margin: float, label_a: str, label_b: str,
                     alpha: float = 0.05) -> dict:
    r"""
    Uji kesetaraan TOST (Two One-Sided Tests) — Persamaan (11).

    Menguji apakah dua kelompok setara secara praktis dalam batas
    margin kesetaraan Δ (equivalence margin).

    Prosedur:
        1. Uji batas bawah: H₀₁: θ ≤ -Δ  (MWU one-sided, shift +Δ)
        2. Uji batas atas:  H₀₂: θ ≥ +Δ  (MWU one-sided, shift -Δ)
        3. p_TOST = max(p₁, p₂)
        4. Kesetaraan diterima jika p_TOST < α

    Parameters
    ----------
    group_a, group_b : np.ndarray
        Data dua kelompok independen.
    margin : float
        Margin kesetaraan Δ (dalam satuan yang sama dengan data, misal ms).
    label_a, label_b : str
        Label identifikasi masing-masing kelompok.
    alpha : float
        Taraf signifikansi (default 0,05).

    Returns
    -------
    dict
        Berisi: comparison, margin, p_lower, p_upper, p_tost,
        equivalent, hodges_lehmann, ci_lower, ci_upper.

    Referensi
    ---------
    Schuirmann, D. J. (1987). Journal of Pharmacokinetics and
    Biopharmaceutics, 15(6), 657–680.
    """
    # Hodges-Lehmann estimate of location shift
    diffs = np.array([a - b for a in group_a for b in group_b])
    hodges_lehmann = np.median(diffs)

    # TOST via shifted Mann-Whitney U
    # Test 1 (lower): H₀: θ ≤ -Δ → shift group_b up by Δ, test A > B+Δ
    _, p_lower = stats.mannwhitneyu(group_a, group_b - margin,
                                     alternative="greater")
    # Test 2 (upper): H₀: θ ≥ +Δ → shift group_b down by Δ, test A < B-Δ
    _, p_upper = stats.mannwhitneyu(group_a, group_b + margin,
                                     alternative="less")

    p_tost = max(p_lower, p_upper)
    is_equivalent = p_tost < alpha

    return {
        "comparison":      f"{label_a} vs {label_b}",
        "margin_ms":       round(margin, 4),
        "hodges_lehmann":  round(hodges_lehmann, 4),
        "p_lower":         round(p_lower, 6),
        "p_upper":         round(p_upper, 6),
        "p_tost":          round(p_tost, 6),
        "equivalent":      is_equivalent,
        "alpha":           alpha,
    }


def bootstrap_median_ci(data: np.ndarray, n_boot: int = 10000,
                        confidence: float = 0.95,
                        seed: int = 42) -> tuple:
    r"""
    Bootstrap 95% CI untuk median — Persamaan (12).

    Menghasilkan confidence interval menggunakan metode percentile
    bootstrap (Efron & Tibshirani, 1993).

        CI(1-α) = [θ*_(α/2) , θ*_(1-α/2)]

    Parameters
    ----------
    data : np.ndarray
        Data observasi.
    n_boot : int
        Jumlah resampling bootstrap (default 10.000).
    confidence : float
        Tingkat kepercayaan (default 0,95).
    seed : int
        Random seed untuk reprodusibilitas.

    Returns
    -------
    tuple(float, float, float)
        (median, ci_lower, ci_upper)
    """
    rng = np.random.default_rng(seed)
    n = len(data)
    boot_medians = np.array([
        np.median(rng.choice(data, size=n, replace=True))
        for _ in range(n_boot)
    ])
    alpha = 1 - confidence
    ci_lower = np.percentile(boot_medians, 100 * alpha / 2)
    ci_upper = np.percentile(boot_medians, 100 * (1 - alpha / 2))
    return round(np.median(data), 4), round(ci_lower, 4), round(ci_upper, 4)


def run_analysis():
    """
    Prosedur utama analisis statistik.

    Alur analisis mengikuti hipotesis penelitian:
      H1: Mekanisme predictive caching menghasilkan latensi p99 yang berbeda
          secara signifikan dibandingkan konfigurasi ZTA naif.
      H2: Latensi revokasi sertifikat memenuhi batas 100 ms NIST SP 800-207.
      H3: TTL adaptif (graph-aware) menghasilkan latensi p99 yang berbeda
          secara signifikan dibandingkan TTL statis.

    Setiap hipotesis diuji menggunakan:
      - Shapiro-Wilk [Persamaan (3)] untuk normalitas
      - Mann-Whitney U [Persamaan (4)] untuk perbandingan dua kelompok
      - Cliff's Delta [Persamaan (5)] untuk effect size
      - Kruskal-Wallis H [Persamaan (6)] untuk perbandingan multi-grup
    """
    print("=" * 70)
    print("ANALISIS STATISTIK — ZTA Predictive Authorization Caching")
    print("Persamaan (3): Shapiro-Wilk  |  (4): Mann-Whitney U")
    print("Persamaan (5): Cliff's Delta |  (6): Kruskal-Wallis H")
    print("Persamaan (11): TOST         |  (12): Bootstrap CI")
    print("=" * 70)

    df = load_data("data/processed/latency-all-scenarios.csv")

    results_sw = []
    results_mw = []
    results_kw = []

    # ── Premis H0: PBS Baseline vs ZTA-Naif ───────────────────────
    print("\n" + "─" * 70)
    print("[Premis] PBS Baseline vs ZTA-Naif @ 500 RPS")
    print("  Tujuan: Verifikasi apakah otorisasi ZTA naif menimbulkan overhead")
    print("─" * 70)

    pbs_data = df[(df.config == "pbs") & (df.rps_target == 500)]["p99_ms"].dropna().values
    naive_data_h0 = df[(df.config == "zta-naive") & (df.rps_target == 500)]["p99_ms"].dropna().values

    if len(pbs_data) > 0 and len(naive_data_h0) > 0:
        sw_pbs = shapiro_wilk(pbs_data, "PBS 500 RPS")
        sw_naive_h0 = shapiro_wilk(naive_data_h0, "ZTA-Naif 500 RPS")
        results_sw.extend([sw_pbs, sw_naive_h0])

        result = mann_whitney_u(pbs_data, naive_data_h0, "PBS@500RPS", "ZTA-Naif@500RPS")
        result["rps"] = 500
        result["metric"] = "p99_latency_pbs_vs_naive"
        results_mw.append(result)

        print(f"\n  Mann-Whitney U [Pers. (4)]: U = {result['u_statistic']}, "
              f"p = {result['p_value']:.6f}")
        print(f"  Cliff's δ     [Pers. (5)]: δ = {result['cliffs_delta']} "
              f"({result['effect_size']})")
        print(f"  Median: {result['median_a']:.4f} → {result['median_b']:.4f} ms "
              f"(Δ = {result['reduction_pct']}%)")
        print(f"  Keputusan: {'H₀ ditolak ✅ Signifikan' if result['significant'] else 'H₀ diterima — Tidak signifikan'} (α=0,05)")

    # ── H1: ZTA-Naif vs ZTA-Cache ─────────────────────────────────
    print("\n" + "─" * 70)
    print("[H1] ZTA-Naif vs ZTA-Cache (Efektivitas Predictive Caching)")
    print("  H₀: Tidak ada perbedaan latensi p99 antara ZTA-Naif dan ZTA-Cache")
    print("  H₁: Terdapat perbedaan latensi p99 (uji dua sisi)")
    print("─" * 70)

    for rps in [500, 2000]:
        naive_data = df[(df.config == "zta-naive") & (df.rps_target == rps)]["p99_ms"].dropna().values
        cache_data = df[(df.config == "zta-cache") & (df.rps_target == rps) &
                        (df.topology == "linear") &
                        (df.scenario_id != "s09-revocation-test")]["p99_ms"].dropna().values

        if len(naive_data) == 0 or len(cache_data) == 0:
            print(f"\n  SKIP {rps} RPS — data tidak tersedia")
            continue

        print(f"\n  @ {rps} RPS (n₁={len(naive_data)}, n₂={len(cache_data)}):")

        # Persamaan (3): Shapiro-Wilk
        sw_naive = shapiro_wilk(naive_data, f"ZTA-Naif {rps} RPS")
        sw_cache = shapiro_wilk(cache_data, f"ZTA-Cache {rps} RPS")
        results_sw.extend([sw_naive, sw_cache])

        # Persamaan (4) + (5): Mann-Whitney U + Cliff's Delta
        result = mann_whitney_u(naive_data, cache_data,
                                f"ZTA-Naif@{rps}RPS", f"ZTA-Cache@{rps}RPS")
        result["rps"] = rps
        result["metric"] = "p99_latency_ms"
        results_mw.append(result)

        print(f"\n  Mann-Whitney U [Pers. (4)]: U = {result['u_statistic']}, "
              f"p = {result['p_value']:.6f}")
        print(f"  Cliff's δ     [Pers. (5)]: δ = {result['cliffs_delta']} "
              f"({result['effect_size']})")
        print(f"  Median: {result['median_a']:.4f} → {result['median_b']:.4f} ms "
              f"(Δ = {result['reduction_pct']}%)")
        print(f"  Keputusan: {'H₀ ditolak ✅' if result['significant'] else 'H₀ diterima — Tidak signifikan'} (α=0,05)")

    # ── PBS vs ZTA-Cache (perbandingan langsung) ──────────────────
    print("\n  Perbandingan langsung PBS Baseline vs ZTA-Cache @ 500 RPS:")
    pbs_500 = df[(df.config == "pbs") & (df.rps_target == 500)]["p99_ms"].dropna().values
    cache_500 = df[(df.scenario_id == "s03-zta-cache-500rps")]["p99_ms"].dropna().values

    if len(pbs_500) > 0 and len(cache_500) > 0:
        result = mann_whitney_u(pbs_500, cache_500, "PBS@500RPS", "ZTA-Cache@500RPS")
        result["rps"] = 500
        result["metric"] = "p99_latency_pbs_vs_cache"
        results_mw.append(result)

        print(f"  Mann-Whitney U [Pers. (4)]: U = {result['u_statistic']}, "
              f"p = {result['p_value']:.6f}")
        print(f"  Cliff's δ     [Pers. (5)]: δ = {result['cliffs_delta']} "
              f"({result['effect_size']})")

    # ── TOST Equivalence Testing ──────────────────────────────────
    results_tost = []
    print("\n" + "─" * 70)
    print("[Kesetaraan] TOST — Persamaan (11)")
    print("  Klaim: near-zero overhead → memerlukan bukti positif kesetaraan")
    print("  Margin Δ = 5% dari median baseline (konvensi benchmarking)")
    print("─" * 70)

    baseline_median = np.median(pbs_data)
    margin = 0.05 * baseline_median  # 5% of baseline
    print(f"\n  Median baseline (PBS): {baseline_median:.4f} ms")
    print(f"  Margin kesetaraan Δ:  {margin:.4f} ms (5% dari baseline)")

    tost_pairs = [
        (pbs_data, naive_data_h0, "PBS@500RPS", "ZTA-Naif@500RPS"),
        (naive_data_h0, cache_500, "ZTA-Naif@500RPS", "ZTA-Cache@500RPS"),
        (pbs_data, cache_500, "PBS@500RPS", "ZTA-Cache@500RPS"),
    ]
    for ga, gb, la, lb in tost_pairs:
        tost = tost_equivalence(ga, gb, margin, la, lb)
        results_tost.append(tost)
        status = "✅ SETARA" if tost["equivalent"] else "❌ Tidak terbukti setara"
        print(f"\n  {la} vs {lb}:")
        print(f"    Hodges-Lehmann Δ̂: {tost['hodges_lehmann']:.4f} ms")
        print(f"    TOST p_lower={tost['p_lower']:.6f}, p_upper={tost['p_upper']:.6f}")
        print(f"    p_TOST = {tost['p_tost']:.6f} → {status}")

    # ── Bootstrap 95% CI ─────────────────────────────────────────
    print("\n" + "─" * 70)
    print("[CI] Bootstrap 95% Confidence Interval — Persamaan (12)")
    print("  Metode: Percentile bootstrap (B = 10.000, seed = 42)")
    print("─" * 70)

    ci_scenarios = [
        (pbs_data, "PBS Baseline 500"),
        (naive_data_h0, "ZTA Naif 500"),
        (cache_500, "ZTA Cache 500"),
    ]
    print(f"\n  {'Konfigurasi':<25} {'Median (ms)':>12} {'95% CI':>20}")
    print(f"  {'-'*25} {'-'*12} {'-'*20}")
    ci_results = []
    for data_arr, label in ci_scenarios:
        med, ci_lo, ci_hi = bootstrap_median_ci(data_arr)
        ci_results.append({"label": label, "median": med,
                           "ci_lower": ci_lo, "ci_upper": ci_hi})
        print(f"  {label:<25} {med:>12.4f} [{ci_lo:.4f}, {ci_hi:.4f}]")

    # CI for median difference (PBS - Cache)
    print("\n  Bootstrap CI untuk perbedaan median (PBS − Cache):")
    rng = np.random.default_rng(42)
    n_boot = 10000
    boot_diffs = []
    for _ in range(n_boot):
        ba = np.median(rng.choice(pbs_data, size=len(pbs_data), replace=True))
        bb = np.median(rng.choice(cache_500, size=len(cache_500), replace=True))
        boot_diffs.append(ba - bb)
    boot_diffs = np.array(boot_diffs)
    diff_med = np.median(boot_diffs)
    diff_lo = np.percentile(boot_diffs, 2.5)
    diff_hi = np.percentile(boot_diffs, 97.5)
    print(f"    Δ(PBS − Cache) = {diff_med:.4f} ms, 95% CI [{diff_lo:.4f}, {diff_hi:.4f}]")
    within_margin = abs(diff_lo) < margin and abs(diff_hi) < margin
    print(f"    CI ⊂ [-{margin:.4f}, +{margin:.4f}]? {'✅ Ya → praktis setara' if within_margin else '❌ Tidak'}")

    # ── H2: Revocation latency ────────────────────────────────────
    print("\n" + "─" * 70)
    print("[H2] Latensi Revokasi vs Ambang Batas NIST SP 800-207")
    print("  H₀: Latensi revokasi p99 ≤ 100 ms")
    print("  Metode: Uji deskriptif terhadap threshold tetap")
    print("─" * 70)

    rev_df = load_data("data/processed/revocation-latency.csv")
    rev_data = rev_df["revocation_latency_ms"].dropna().values

    if len(rev_data) > 0:
        rev_p99 = np.percentile(rev_data, 99)
        rev_mean = np.mean(rev_data)
        rev_median = np.median(rev_data)
        threshold_met = rev_p99 <= 100

        print(f"\n  n              : {len(rev_data)}")
        print(f"  Mean p99       : {rev_mean:.4f} ms")
        print(f"  Median p99     : {rev_median:.4f} ms")
        print(f"  p99 of p99s    : {rev_p99:.4f} ms")
        print(f"  Threshold NIST : 100 ms")
        print(f"  Margin         : {100 - rev_p99:.2f} ms ({(100 - rev_p99)/100*100:.1f}%)")
        print(f"  Keputusan      : {'✅ Terpenuhi' if threshold_met else '❌ Tidak terpenuhi'}")

        results_mw.append({
            "comparison":   "RevocationLatency vs 100ms threshold",
            "metric":       "revocation_p99_ms",
            "median_a":     round(rev_median, 4),
            "mean_a":       round(rev_mean, 4),
            "p99_of_p99s":  round(rev_p99, 4),
            "threshold_met": threshold_met,
            "n_a":          len(rev_data),
        })

    # ── H3: Graph-aware TTL vs Static TTL ─────────────────────────
    print("\n" + "─" * 70)
    print("[H3] TTL Adaptif (Graph-aware) vs TTL Statis")
    print("  H₀: Tidak ada perbedaan latensi p99 antara TTL adaptif dan statis")
    print("  H₁: Terdapat perbedaan latensi p99 (uji dua sisi)")
    print("─" * 70)

    s07 = df[df.scenario_id == "s07-zta-cache-fanout"]["p99_ms"].dropna().values
    s10 = df[df.scenario_id == "s10-ttl-comparison"]["p99_ms"].dropna().values

    if len(s07) > 0 and len(s10) > 0:
        print(f"\n  Graph-aware (S07): n={len(s07)}, median p99={np.median(s07):.4f} ms")
        print(f"  Static TTL  (S10): n={len(s10)}, median p99={np.median(s10):.4f} ms")

        sw_s07 = shapiro_wilk(s07, "Graph-aware TTL (S07)")
        sw_s10 = shapiro_wilk(s10, "Static TTL (S10)")
        results_sw.extend([sw_s07, sw_s10])

        result = mann_whitney_u(s10, s07, "Static TTL", "Graph-aware TTL")
        result["metric"] = "p99_latency_ttl"
        results_mw.append(result)

        print(f"\n  Mann-Whitney U [Pers. (4)]: U = {result['u_statistic']}, "
              f"p = {result['p_value']:.6f}")
        print(f"  Cliff's δ     [Pers. (5)]: δ = {result['cliffs_delta']} "
              f"({result['effect_size']})")
        print(f"  Keputusan: {'H₀ ditolak ✅' if result['significant'] else 'H₀ diterima — Tidak signifikan'} (α=0,05)")

    # ── Topologi: Kruskal-Wallis ──────────────────────────────────
    print("\n" + "─" * 70)
    print("[Topologi] Kruskal-Wallis H — Persamaan (6)")
    print("  H₀: Distribusi latensi p99 identik di ketiga topologi")
    print("─" * 70)

    s05_lin = df[df.scenario_id == "s05-zta-cache-2000rps"]["p99_ms"].dropna().values
    s07_fan = df[df.scenario_id == "s07-zta-cache-fanout"]["p99_ms"].dropna().values
    s08_mesh = df[df.scenario_id == "s08-zta-cache-mesh"]["p99_ms"].dropna().values

    if len(s05_lin) > 0 and len(s07_fan) > 0 and len(s08_mesh) > 0:
        print(f"\n  Linear  (S05): n={len(s05_lin)}, median={np.median(s05_lin):.4f} ms")
        print(f"  Fan-out (S07): n={len(s07_fan)}, median={np.median(s07_fan):.4f} ms")
        print(f"  Mesh    (S08): n={len(s08_mesh)}, median={np.median(s08_mesh):.4f} ms")

        kw = kruskal_wallis_h(s05_lin, s07_fan, s08_mesh,
                              labels=["Linear", "Fan-out", "Mesh"])
        kw["comparison"] = "Topology @ 2000 RPS"
        kw["metric"] = "p99_latency_ms"
        results_kw.append(kw)

        print(f"\n  Kruskal-Wallis H [Pers. (6)]: H = {kw['h_statistic']}, "
              f"p = {kw['p_value']:.6f}")
        print(f"  Keputusan: {'H₀ ditolak ✅ Signifikan' if kw['significant'] else 'H₀ diterima'} (α=0,05)")

        # Post-hoc Mann-Whitney dengan koreksi Bonferroni
        if kw["significant"]:
            k_pairs = 3  # C(3,2) = 3 pasangan
            alpha_bonferroni = 0.05 / k_pairs
            print(f"\n  Post-hoc (koreksi Bonferroni, α' = {alpha_bonferroni:.4f}):")

            pairs = [
                (s05_lin, s07_fan, "Linear", "Fan-out"),
                (s05_lin, s08_mesh, "Linear", "Mesh"),
                (s07_fan, s08_mesh, "Fan-out", "Mesh"),
            ]
            for ga, gb, la, lb in pairs:
                r = mann_whitney_u(ga, gb, la, lb)
                r["metric"] = "topology_posthoc"
                bonferroni_sig = r["p_value"] < alpha_bonferroni
                r["bonferroni_significant"] = bonferroni_sig
                results_mw.append(r)

                print(f"    {la} vs {lb}: p={r['p_value']:.6f}, "
                      f"δ={r['cliffs_delta']} ({r['effect_size']}) "
                      f"{'✅' if bonferroni_sig else '❌'}")

    # ── Multi-grup: PBS vs ZTA-Naif vs ZTA-Cache ──────────────────
    print("\n" + "─" * 70)
    print("[Multi-grup] Kruskal-Wallis: PBS vs ZTA-Naif vs ZTA-Cache @ 500 RPS")
    print("─" * 70)

    pbs_500_kw = df[(df.config == "pbs") & (df.rps_target == 500)]["p99_ms"].dropna().values
    naive_500 = df[(df.config == "zta-naive") & (df.rps_target == 500)]["p99_ms"].dropna().values
    cache_500_kw = df[(df.scenario_id == "s03-zta-cache-500rps")]["p99_ms"].dropna().values

    if len(pbs_500_kw) > 0 and len(naive_500) > 0 and len(cache_500_kw) > 0:
        kw = kruskal_wallis_h(pbs_500_kw, naive_500, cache_500_kw,
                              labels=["PBS", "ZTA-Naif", "ZTA-Cache"])
        kw["comparison"] = "Config @ 500 RPS"
        kw["rps"] = 500
        kw["metric"] = "p99_latency_ms"
        results_kw.append(kw)

        print(f"\n  Kruskal-Wallis H [Pers. (6)]: H = {kw['h_statistic']}, "
              f"p = {kw['p_value']:.6f}")
        print(f"  Keputusan: {'H₀ ditolak ✅' if kw['significant'] else 'H₀ diterima — Tidak signifikan'}")

    # ── Resource Overhead: CPU & Memory ───────────────────────────
    print("\n" + "─" * 70)
    print("[Resource] Kruskal-Wallis: CPU & Memory Overhead @ 500 RPS")
    print("─" * 70)

    try:
        res_df = load_data("data/processed/resource-overhead.csv")

        for metric_col, metric_name in [("cpu_avg_pct", "CPU (%)"), ("mem_avg_mb", "Memory (MB)")]:
            pbs_res = res_df[(res_df.config == "pbs") & (res_df.rps_target == 500)][metric_col].dropna().values
            naive_res = res_df[(res_df.config == "zta-naive") & (res_df.rps_target == 500)][metric_col].dropna().values
            cache_res = res_df[(res_df.config == "zta-cache") & (res_df.rps_target == 500) &
                               (res_df.topology == "linear")][metric_col].dropna().values

            if len(pbs_res) > 0 and len(naive_res) > 0 and len(cache_res) > 0:
                kw = kruskal_wallis_h(pbs_res, naive_res, cache_res,
                                      labels=["PBS", "ZTA-Naif", "ZTA-Cache"])
                kw["comparison"] = f"{metric_name} Overhead @ 500 RPS"
                kw["metric"] = metric_col
                results_kw.append(kw)

                print(f"\n  {metric_name}:")
                print(f"    PBS={np.mean(pbs_res):.4f}, ZTA-Naif={np.mean(naive_res):.4f}, "
                      f"ZTA-Cache={np.mean(cache_res):.4f}")
                print(f"    Kruskal-Wallis H [Pers. (6)]: H={kw['h_statistic']}, "
                      f"p={kw['p_value']:.6f}")
    except FileNotFoundError:
        print("  SKIP — resource-overhead.csv tidak ditemukan")

    # ── Simpan hasil ──────────────────────────────────────────────
    os.makedirs("data/reports", exist_ok=True)

    # Shapiro-Wilk results
    pd.DataFrame(results_sw).to_csv(
        "data/reports/shapiro-wilk-results.csv", index=False)

    # Mann-Whitney results (hanya yang memiliki u_statistic)
    mw_exportable = [r for r in results_mw if "u_statistic" in r]
    pd.DataFrame(mw_exportable).to_csv(
        "data/reports/mann-whitney-results.csv", index=False)

    # Kruskal-Wallis results
    pd.DataFrame(results_kw).to_csv(
        "data/reports/kruskal-wallis-results.csv", index=False)

    # TOST equivalence results
    pd.DataFrame(results_tost).to_csv(
        "data/reports/tost-equivalence-results.csv", index=False)

    print("\n" + "=" * 70)
    print("✅ Hasil tersimpan di data/reports/")
    print("   - shapiro-wilk-results.csv")
    print("   - mann-whitney-results.csv")
    print("   - kruskal-wallis-results.csv")
    print("   - tost-equivalence-results.csv")
    print("=" * 70)


if __name__ == "__main__":
    run_analysis()
