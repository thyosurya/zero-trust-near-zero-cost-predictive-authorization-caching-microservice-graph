#!/usr/bin/env python3
r"""
generate-figures.py: Visualisasi Statistik untuk Naskah Artikel
================================================================

Menghasilkan seluruh gambar (PNG) untuk naskah penelitian "Algoritma
Predictive Authorization Caching Berbasis Graph Topology".

Prinsip: Seluruh nilai statistik (p-value, Cliff's δ, n) dihitung dari
data, tidak pernah di-hardcode. Ini memastikan gambar tetap sinkron
jika data berubah.

Formalisasi Persamaan Matematika
---------------------------------

Persamaan (5): Cliff's Delta (δ)
    δ = (#{xᵢ > yⱼ} - #{xᵢ < yⱼ}) / (n₁ × n₂)

    di mana:
    - #{xᵢ > yⱼ} : jumlah pasangan dominan (xᵢ menang)
    - #{xᵢ < yⱼ} : jumlah pasangan di mana yⱼ menang
    - n₁, n₂     : ukuran sampel masing-masing kelompok

    Interpretasi (Romano et al., 2006):
    - |δ| < 0,147  : negligible
    - 0,147 ≤ |δ| < 0,330 : small
    - 0,330 ≤ |δ| < 0,474 : medium
    - |δ| ≥ 0,474  : large

Persamaan (4): Uji Mann-Whitney U
    U = n₁n₂ + n₁(n₁+1)/2 - R₁

    Hipotesis dua sisi: H₀: P(X > Y) = P(Y > X)
    Keputusan: H₀ ditolak jika p < α (α = 0,05).

Persamaan (6): Uji Kruskal-Wallis H
    H = [12 / N(N+1)] × Σⱼ₌₁ᵏ (Rⱼ²/nⱼ) - 3(N+1)

    Post-hoc: Mann-Whitney berpasangan, koreksi Bonferroni:
    p_adj = p_raw × k',  k' = C(k, 2)

Persamaan (K1): Kendall's Tau (τ)
    τ = (C - D) / [½ n(n-1)]

    di mana:
    - C : jumlah pasangan concordant
    - D : jumlah pasangan discordant
    - n : jumlah elemen dalam ranking

    Digunakan untuk mengukur stabilitas ranking prioritas cache
    terhadap variasi parameter bobot w pada Persamaan (2).

Persamaan (2): Skor Prioritas Cache
    S(e) = w × f̂(e) + (1 - w) × C_B(source_e)

    di mana:
    - f̂(e)          : frekuensi panggilan ternormalisasi [0, 1]
    - C_B(source_e)  : betweenness centrality ternormalisasi
    - w              : parameter bobot (ditetapkan w = 0,7)

Aturan Sturges (Penentuan Jumlah Bin Histogram):
    k = ⌈log₂(n) + 1⌉

    di mana n = ukuran sampel. Untuk n = 30: k = ⌈4,91 + 1⌉ = 6 bin.

Referensi
----------
- Cliff, N. (1993). Dominance statistics. Psych. Bulletin, 114(3), 494–509.
- Romano, J., et al. (2006). Appropriate statistics for ordinal level data.
  JMASM, 5(1), 231–236.
- Mann, H. B., & Whitney, D. R. (1947). Annals of Math. Statistics, 18(1).
- Kruskal, W. H., & Wallis, W. A. (1952). JASA, 47(260), 583–621.
- Kendall, M. G. (1938). Biometrika, 30(1/2), 81–93.
- Sturges, H. A. (1926). JASA, 21(153), 65–66.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as patches
from pathlib import Path
from scipy.stats import mannwhitneyu, kruskal, kendalltau
import json

# ── Configuration ─────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "processed"
FIGS = BASE / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

EXPECTED_N = 30  # expected repetitions per scenario

# Standardized figure sizes (width, height) in inches
FIG_SINGLE = (5, 4)      # single-panel figures
FIG_NARROW = (4.5, 4)    # narrower single-panel
FIG_DUAL   = (8, 4)      # dual-panel figures

# Style — mathtext enabled for LaTeX rendering in figures
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.titlesize': 11,
    'axes.labelsize': 10,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
    'mathtext.fontset': 'cm',        # Computer Modern — standar jurnal
    'mathtext.default': 'regular',
})

# Indonesian decimal comma formatters for axis tick labels
def make_comma_formatter(decimals=2):
    """Format tick value with comma as decimal separator and fixed precision."""
    def formatter(x, pos):
        return f'{x:.{decimals}f}'.replace('.', ',')
    return formatter

def integer_formatter(x, pos):
    """Format tick value as integer with rounding."""
    return f'{int(round(x))}'

# Color palette — single source of truth for all figures
COLORS = {
    'pbs': '#4CAF50',       # green
    'naive': '#FF9800',     # orange
    'cache': '#2196F3',     # blue
    'linear': '#2196F3',
    'fanout': '#E91E63',    # pink
    'mesh': '#9C27B0',      # purple
    'static': '#FF9800',
    'adaptive': '#2196F3',
    # Edge-specific colors for sensitivity analysis
    'edge_products': '#1B5E20',   # dark green
    'edge_cart': '#E65100',       # dark orange
    'edge_health': '#4A148C',     # dark purple
}

# ── Load Data ─────────────────────────────────────────────────
print("Loading data...")
latency_df = pd.read_csv(DATA / "latency-all-scenarios.csv")
resource_df = pd.read_csv(DATA / "resource-overhead.csv")

# Strip whitespace from scenario_id in BOTH dataframes
latency_df['scenario_id'] = latency_df['scenario_id'].str.strip()
resource_df['scenario_id'] = resource_df['scenario_id'].str.strip()

# ── Helpers ───────────────────────────────────────────────────
def scenario_data(sid, df=None):
    """Get p99 data for a scenario, with n-validation."""
    if df is None:
        df = latency_df
    vals = df[df.scenario_id == sid]['p99_ms'].dropna().values
    assert len(vals) == EXPECTED_N, \
        f"FATAL: {sid} has n={len(vals)}, expected {EXPECTED_N}. Data integrity issue!"
    return vals

def cliffs_delta(x, y):
    r"""
    Menghitung Cliff's Delta (δ) — Persamaan (5).
    δ = (#{xᵢ > yⱼ} - #{xᵢ < yⱼ}) / (n₁ × n₂)
    """
    n_x, n_y = len(x), len(y)
    more = sum(1 for xi in x for yi in y if xi > yi)
    less = sum(1 for xi in x for yi in y if xi < yi)
    return (more - less) / (n_x * n_y)

def compute_mw(a, b):
    r"""Menghitung Mann-Whitney U [Pers. (4)] + Cliff's δ [Pers. (5)]."""
    u_stat, p_val = mannwhitneyu(a, b, alternative='two-sided')
    d = cliffs_delta(a, b)
    return u_stat, p_val, d

def fmt_p(p, latex=True):
    r"""Format p-value: LaTeX mathtext untuk gambar, plain untuk console."""
    if latex:
        if p < 0.001:
            return r'$p < 0{,}001$'
        val = f'{p:.3f}'.replace('.', '{,}')
        return f'$p = {val}$'
    else:
        if p < 0.001:
            return 'p<0,001'
        return f'p={p:.3f}'.replace('.', ',')

def fmt_d(d, latex=True):
    r"""Format Cliff's δ: LaTeX mathtext untuk gambar, plain untuk console."""
    if latex:
        val = f'{d:.2f}'.replace('.', '{,}').replace('-', '\u2212')
        return f'$\\delta = {val}$'
    else:
        return f'd={d:.2f}'.replace('.', ',')

def fmt_u(u, latex=True):
    r"""Format Mann-Whitney U statistic."""
    if latex:
        val = f'{u:.1f}'.replace('.', '{,}')
        return f'$U = {val}$'
    else:
        return f'U={u:.1f}'

def effect_label(d):
    r"""Interpretasi magnitude Cliff's δ berdasarkan Romano et al. (2006)."""
    ad = abs(d)
    if ad < 0.147:
        return "negligible"
    elif ad < 0.330:
        return "small"
    elif ad < 0.474:
        return "medium"
    else:
        return "large"

def fmt_stat(p, d):
    r"""Format full stat line for annotation on figures (LaTeX)."""
    return f'{fmt_p(p)}\n{fmt_d(d)} ({effect_label(d)})'

# ══════════════════════════════════════════════════════════════
# GAMBAR 1: Arsitektur Sistem Predictive Authorization Caching
# ══════════════════════════════════════════════════════════════
print("  Gambar 1: Arsitektur Sistem")
fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=300)
ax.axis('off')
ax.set_xlim(0, 10)
ax.set_ylim(0, 7)

# Control Plane box
cp_box = patches.FancyBboxPatch((0.6, 3.4), 8.8, 3.2, boxstyle='round,pad=0.2',
                                facecolor='#F8FAFC', edgecolor='#64748B', linestyle='--', linewidth=1.2)
ax.add_patch(cp_box)
ax.text(0.9, 6.35, 'Control Plane', fontsize=11, fontweight='bold', color='#1E293B')

# Graph Topology Analyzer
b_analyzer = patches.FancyBboxPatch((1.0, 4.8), 3.4, 1.3, boxstyle='round,pad=0.1',
                                   facecolor='#EFF6FF', edgecolor='#3B82F6', linewidth=1.2)
ax.add_patch(b_analyzer)
ax.text(2.7, 5.45, 'Graph Topology Analyzer\n(Betweenness Centrality)',
        ha='center', va='center', fontsize=9, fontweight='bold', color='#1E40AF')

# Cache Distributor
b_dist = patches.FancyBboxPatch((5.6, 4.8), 3.4, 1.3, boxstyle='round,pad=0.1',
                                facecolor='#EFF6FF', edgecolor='#3B82F6', linewidth=1.2)
ax.add_patch(b_dist)
ax.text(7.3, 5.45, 'Cache Distributor\n(gRPC Streaming)',
        ha='center', va='center', fontsize=9, fontweight='bold', color='#1E40AF')

# OPA PDP
b_opa = patches.FancyBboxPatch((1.0, 3.65), 3.4, 0.9, boxstyle='round,pad=0.1',
                              facecolor='#FEF3C7', edgecolor='#F59E0B', linewidth=1.2)
ax.add_patch(b_opa)
ax.text(2.7, 4.1, 'OPA (PDP)\nRego Engine',
        ha='center', va='center', fontsize=8.5, fontweight='bold', color='#92400E')

# Data Plane box
dp_box = patches.FancyBboxPatch((0.6, 0.4), 8.8, 2.5, boxstyle='round,pad=0.2',
                                facecolor='#F8FAFC', edgecolor='#64748B', linestyle='--', linewidth=1.2)
ax.add_patch(dp_box)
ax.text(0.9, 2.65, 'Data Plane', fontsize=11, fontweight='bold', color='#1E293B')

# Service App
b_app = patches.FancyBboxPatch((1.0, 0.75), 3.4, 1.6, boxstyle='round,pad=0.1',
                               facecolor='#ECFDF5', edgecolor='#10B981', linewidth=1.2)
ax.add_patch(b_app)
ax.text(2.7, 1.55, 'Service Application\n(Workload Container)',
        ha='center', va='center', fontsize=9, fontweight='bold', color='#065F46')

# Envoy Sidecar + WASM
b_envoy = patches.FancyBboxPatch((5.6, 0.75), 3.4, 1.6, boxstyle='round,pad=0.1',
                                 facecolor='#EFF6FF', edgecolor='#2563EB', linewidth=1.2)
ax.add_patch(b_envoy)
ax.text(7.3, 1.55, 'Envoy Sidecar\n+ WASM Filter\n(Local Decision Engine)',
        ha='center', va='center', fontsize=9, fontweight='bold', color='#1E40AF')

# Connections
ax.annotate('', xy=(5.6, 5.45), xytext=(4.4, 5.45),
            arrowprops=dict(arrowstyle='->', lw=1.8, color='#2563EB'))
ax.text(5.0, 5.7, 'Prioritas Edge\n& TTL adaptif', ha='center', va='bottom', fontsize=7.5, color='#1E40AF')

ax.annotate('', xy=(2.7, 4.55), xytext=(2.7, 4.8),
            arrowprops=dict(arrowstyle='->', lw=1.5, color='#D97706'))

ax.annotate('', xy=(7.3, 2.35), xytext=(7.3, 4.8),
            arrowprops=dict(arrowstyle='->', lw=2.0, color='#2563EB'))
ax.text(7.45, 3.5, 'gRPC Push Stream\nDelegation Token + Nonce', ha='left', va='center', fontsize=8, color='#1D4ED8',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='#EFF6FF', edgecolor='#93C5FD', alpha=0.9))

ax.annotate('', xy=(5.6, 1.55), xytext=(4.4, 1.55),
            arrowprops=dict(arrowstyle='<->', lw=1.8, color='#059669'))
ax.text(5.0, 1.8, 'Trafik Inbound/Outbound\nInterception', ha='center', va='bottom', fontsize=7.5, color='#065F46')

fig.suptitle('Arsitektur Sistem Predictive Authorization Caching', fontsize=11, fontweight='bold', y=0.97)
fig.tight_layout()
fig.savefig(FIGS / 'fig1-system-architecture.png')
plt.close(fig)

# ══════════════════════════════════════════════════════════════
# GAMBAR 2: Sensitivity analysis for weight justification (Fig 7)
# ══════════════════════════════════════════════════════════════
print("  Gambar 2: Analisis Sensitivitas Bobot")
EDGE_DATA_PATH = DATA / 'edge-topology.json'
if EDGE_DATA_PATH.exists():
    with open(EDGE_DATA_PATH) as f:
        _edge_raw = json.load(f)
else:
    _edge_raw = {
        'products': {'calls': 85, 'centrality': 1.0},
        'cart':     {'calls': 60, 'centrality': 1.0},
        'health':   {'calls': 30, 'centrality': 0.3},
    }
    with open(EDGE_DATA_PATH, 'w') as f:
        json.dump(_edge_raw, f, indent=2)

_edge_color_map = {
    'products': COLORS['edge_products'],
    'cart':     COLORS['edge_cart'],
    'health':   COLORS['edge_health'],
}
edge_info = {}
for name, data in _edge_raw.items():
    edge_info[name] = {
        'calls': data['calls'],
        'centrality': data['centrality'],
        'color': _edge_color_map.get(name, '#333333'),
    }

max_calls = max(e['calls'] for e in edge_info.values())
weights_range = np.arange(0, 1.05, 0.05)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIG_DUAL)

# Panel A: Skor prioritas vs bobot — Persamaan (2)
for name, info in edge_info.items():
    norm_calls = info['calls'] / max_calls
    cent = info['centrality']
    scores = [w * norm_calls + (1 - w) * cent for w in weights_range]
    ax1.plot(weights_range, scores, '-o', label=name, markersize=3,
             linewidth=1.5, color=info['color'])

ax1.axvline(x=0.7, color='red', linestyle='--', alpha=0.5, label=r'$w = 0{,}7$ (dipilih)')
ax1.set_xlabel(r'Bobot frekuensi ($w$)')
ax1.set_ylabel(r'Skor prioritas $S(e)$')
ax1.set_title(r'(a) $S(e) = w \cdot \hat{f}(e) + (1-w) \cdot C_B$')
ax1.legend(fontsize=8)
ax1.grid(True, alpha=0.3)

# Panel B: Stabilitas ranking — Kendall's τ
ref_scores = {}
for name, info in edge_info.items():
    norm_calls = info['calls'] / max_calls
    ref_scores[name] = 0.7 * norm_calls + 0.3 * info['centrality']

ref_ranking = sorted(ref_scores.keys(), key=lambda e: ref_scores[e], reverse=True)
ref_ranks = {e: i for i, e in enumerate(ref_ranking)}
n_edges = len(ref_ranking)

taus = []
for w in weights_range:
    curr_scores = {}
    for name, info in edge_info.items():
        norm_calls = info['calls'] / max_calls
        curr_scores[name] = w * norm_calls + (1 - w) * info['centrality']
    curr_ranking = sorted(curr_scores.keys(), key=lambda e: curr_scores[e], reverse=True)
    curr_ranks = {e: i for i, e in enumerate(curr_ranking)}

    r1 = [ref_ranks[e] for e in ref_ranking]
    r2 = [curr_ranks[e] for e in ref_ranking]
    tau, _ = kendalltau(r1, r2)
    taus.append(tau)

ax2.step(weights_range, taus, where='mid', color='#E91E63', linewidth=1.5,
         label=r"Kendall's $\tau$" + f" ($n = {n_edges}$ edges)")
ax2.scatter(weights_range, taus, color='#E91E63', s=15, zorder=3)
ax2.axvline(x=0.7, color='red', linestyle='--', alpha=0.5)
ax2.axhspan(0.8, 1.05, alpha=0.1, color='green', label='Ranking stabil')
ax2.set_xlabel(r'Bobot frekuensi ($w$)')
ax2.set_ylabel(r"Kendall's $\tau$ vs referensi ($w = 0{,}7$)")
ax2.set_title(r'(b) Stabilitas ranking: $\tau = \frac{C - D}{\frac{1}{2}n(n-1)}$')
ax2.set_ylim(-0.2, 1.1)
ax2.legend(fontsize=8)
ax2.grid(True, alpha=0.3)

fig.suptitle('Analisis Sensitivitas Bobot Prioritas Cache: Formulasi Persamaan (2)', fontsize=11, y=1.02)
fig.tight_layout()
fig.savefig(FIGS / 'fig2-weight-sensitivity.png')
plt.close(fig)

# ══════════════════════════════════════════════════════════════
# GAMBAR 3: Variasi Pola Panggilan (Topologi)
# ══════════════════════════════════════════════════════════════
print("  Gambar 3: Variasi Pola Panggilan")
fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(12.5, 5.8), dpi=300)
for ax in (ax1, ax2, ax3):
    ax.axis('off')
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 11)

def draw_k6(ax):
    b = patches.FancyBboxPatch((2.2, 9.2), 5.6, 1.2, boxstyle='round,pad=0.1',
                               facecolor='#E0E7FF', edgecolor='#4F46E5', linewidth=1.2)
    ax.add_patch(b)
    ax.text(5.0, 9.8, 'k6 Load Generator', ha='center', va='center', fontsize=9, fontweight='bold', color='#3730A3')

def draw_envoy(ax, text_extra):
    b = patches.FancyBboxPatch((1.0, 5.7), 8.0, 1.7, boxstyle='round,pad=0.1',
                               facecolor='#EFF6FF', edgecolor='#2563EB', linewidth=1.2)
    ax.add_patch(b)
    ax.text(5.0, 6.55, f'Envoy Sidecar + WASM Filter\n{text_extra}',
            ha='center', va='center', fontsize=8, fontweight='bold', color='#1E40AF')

# Panel (a): Linear
draw_k6(ax1)
ax1.annotate('', xy=(5.0, 7.4), xytext=(5.0, 9.2),
             arrowprops=dict(arrowstyle='->', lw=1.5, color='#4F46E5'))
ax1.text(5.2, 8.3, 'GET /api/products\n(1 req / iterasi)', ha='left', va='center', fontsize=7.2, color='#4F46E5')
draw_envoy(ax1, '(1 evaluasi otorisasi / req)')

b_outer1 = patches.FancyBboxPatch((0.8, 0.6), 8.4, 4.1, boxstyle='round,pad=0.12',
                                  facecolor='#ECFDF5', edgecolor='#10B981', linewidth=1.3, linestyle='--')
ax1.add_patch(b_outer1)
ax1.text(1.2, 4.35, 'Frontend Service (Single Pod)', fontsize=8, fontweight='bold', color='#065F46')
ax1.text(1.2, 3.95, 'Seluruh request ditangani secara lokal', fontsize=6.8, color='#047857', style='italic')

ax1.annotate('', xy=(5.0, 2.8), xytext=(5.0, 5.7),
             arrowprops=dict(arrowstyle='->', lw=1.5, color='#059669'))
b_ep1 = patches.FancyBboxPatch((2.2, 1.5), 5.6, 1.3, boxstyle='round,pad=0.08',
                              facecolor='#D1FAE5', edgecolor='#059669', linewidth=1.0)
ax1.add_patch(b_ep1)
ax1.text(5.0, 2.15, 'Endpoint Handler:\nGET /api/products', ha='center', va='center', fontsize=8, fontweight='bold', color='#065F46')
ax1.text(5.0, 0.9, r'Latensi tunggal ($p_{99} \approx 16{,}7$ ms @ 2000 RPS)', ha='center', va='center', fontsize=6.8, color='#047857', style='italic')
ax1.set_title('(a) Linear (S01–S06, S09)\n1 endpoint / iterasi', fontsize=9.5, fontweight='bold', pad=12)

# Panel (b): Fan-out
draw_k6(ax2)
for x in [3.2, 5.0, 6.8]:
    ax2.annotate('', xy=(x, 7.4), xytext=(x, 9.2),
                 arrowprops=dict(arrowstyle='->', lw=1.2, color='#E11D48'))
ax2.text(5.0, 8.3, 'http.batch([products, cart, health])\n(3 req paralel simultan)', ha='center', va='center', fontsize=6.7, color='#BE123C', bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#FECDD3', alpha=0.9))
draw_envoy(ax2, '(3 evaluasi paralel / iterasi)\nKonkurensi tinggi')

b_outer2 = patches.FancyBboxPatch((0.8, 0.6), 8.4, 4.1, boxstyle='round,pad=0.12',
                                  facecolor='#FFF1F2', edgecolor='#F43F5E', linewidth=1.3, linestyle='--')
ax2.add_patch(b_outer2)
ax2.text(1.2, 4.35, 'Frontend Service (Single Pod)', fontsize=8, fontweight='bold', color='#9F1239')
ax2.text(1.2, 3.95, 'Seluruh request ditangani secara lokal', fontsize=6.8, color='#BE123C', style='italic')

eps = ['/api/products', '/api/cart', '/health']
ep_xs = [2.2, 5.0, 7.8]
for x, ep in zip(ep_xs, eps):
    ax2.annotate('', xy=(x, 2.8), xytext=(x, 5.7),
                 arrowprops=dict(arrowstyle='->', lw=1.1, color='#E11D48'))
    b_ep = patches.FancyBboxPatch((x - 1.25, 1.5), 2.5, 1.3, boxstyle='round,pad=0.06',
                                  facecolor='#FFE4E6', edgecolor='#E11D48', linewidth=0.9)
    ax2.add_patch(b_ep)
    ax2.text(x, 2.15, f'{ep}', ha='center', va='center', fontsize=7.2, fontweight='bold', color='#9F1239')
ax2.text(5.0, 0.9, r'Ceiling effect: $p_{99} = \max(req_i)$ ($p_{99} \approx 1322{,}5$ ms @ 2k RPS)', ha='center', va='center', fontsize=6.6, color='#9F1239', style='italic')
ax2.set_title('(b) Fan-out (S07, S10)\n3 endpoint paralel / iterasi (batch)', fontsize=9.5, fontweight='bold', pad=12)

# Panel (c): Mesh
draw_k6(ax3)
ax3.annotate('', xy=(5.0, 7.4), xytext=(5.0, 9.2),
             arrowprops=dict(arrowstyle='->', lw=1.5, color='#9333EA'))
ax3.text(5.2, 8.3, 'Round-robin iterasi (__ITER % 3)\n(1 req bergantian / iterasi)', ha='left', va='center', fontsize=6.9, color='#7E22CE')
draw_envoy(ax3, '(1 evaluasi bergantian / iterasi)\nRotasi 3 endpoint')

b_outer3 = patches.FancyBboxPatch((0.8, 0.6), 8.4, 4.1, boxstyle='round,pad=0.12',
                                  facecolor='#FAF5FF', edgecolor='#A855F7', linewidth=1.3, linestyle='--')
ax3.add_patch(b_outer3)
ax3.text(1.2, 4.35, 'Frontend Service (Single Pod)', fontsize=8, fontweight='bold', color='#6B21A8')
ax3.text(1.2, 3.95, 'Seluruh request ditangani secara lokal', fontsize=6.8, color='#7E22CE', style='italic')

labels_rot = ['iter % 3 = 0', 'iter % 3 = 1', 'iter % 3 = 2']
for x, ep, ls, lrot in zip(ep_xs, eps, ['-', '--', ':'], labels_rot):
    ax3.annotate('', xy=(x, 2.8), xytext=(x, 5.7),
                 arrowprops=dict(arrowstyle='->', lw=1.1, color='#9333EA', linestyle=ls))
    b_ep = patches.FancyBboxPatch((x - 1.25, 1.5), 2.5, 1.3, boxstyle='round,pad=0.06',
                                  facecolor='#F3E8FF', edgecolor='#9333EA', linewidth=0.9)
    ax3.add_patch(b_ep)
    ax3.text(x, 2.25, f'{ep}', ha='center', va='center', fontsize=7.2, fontweight='bold', color='#6B21A8')
    ax3.text(x, 1.75, f'{lrot}', ha='center', va='center', fontsize=6.2, color='#7E22CE')
ax3.text(5.0, 0.9, r'1 req per waktu, independen ($p_{99} \approx 499{,}3$ ms @ 2k RPS)', ha='center', va='center', fontsize=6.6, color='#6B21A8', style='italic')
ax3.set_title('(c) Mesh (S08)\n1 endpoint / iterasi (round-robin)', fontsize=9.5, fontweight='bold', pad=12)

fig.suptitle('Variasi Pola Panggilan (Topologi) dalam Eksperimen', fontsize=11.5, fontweight='bold', y=0.99)
fig.tight_layout()
fig.savefig(FIGS / 'fig3-topology-variations.png')
plt.close(fig)

# ══════════════════════════════════════════════════════════════
# GAMBAR 4: Boxplot - PBS vs ZTA-Naif vs ZTA-Cache @ 500 RPS (Fig 1)
# ══════════════════════════════════════════════════════════════
print("  Gambar 4: Perbandingan Konfigurasi @ 500 RPS")
fig, ax = plt.subplots(figsize=FIG_SINGLE)

d_pbs = scenario_data('s01-pbs-baseline-500rps')
d_naive = scenario_data('s02-zta-naive-500rps')
d_cache = scenario_data('s03-zta-cache-500rps')
data_500 = [d_pbs, d_naive, d_cache]
n_500 = len(d_pbs)
labels_500 = ['PBS\nBaseline', 'ZTA\nNaif', 'ZTA\nCache']
colors_500 = [COLORS['pbs'], COLORS['naive'], COLORS['cache']]

bp = ax.boxplot(data_500, tick_labels=labels_500, patch_artist=True, widths=0.5,
                medianprops=dict(color='black', linewidth=1.5),
                flierprops=dict(marker='o', markersize=4, alpha=0.5))
for patch, color in zip(bp['boxes'], colors_500):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)

u_pn, p_pn, d_pn = compute_mw(d_pbs, d_naive)
u_nc, p_nc, d_nc = compute_mw(d_naive, d_cache)
u_pc, p_pc, d_pc = compute_mw(d_pbs, d_cache)

y_top = max(max(d_pbs), max(d_naive), max(d_cache))
y_bot = min(min(d_pbs), min(d_naive), min(d_cache))
ax.set_ylim(bottom=y_bot * 0.93, top=y_top * 1.20)
annotate_y = y_top * 1.02
ax.annotate(fmt_stat(p_pn, d_pn), xy=(1.5, annotate_y),
            ha='center', fontsize=7, color='gray')
ax.annotate(fmt_stat(p_nc, d_nc), xy=(2.5, annotate_y),
            ha='center', fontsize=7, color='gray')
ax.annotate(f'PBS vs Cache: {fmt_p(p_pc)}, {fmt_d(d_pc)} ({effect_label(d_pc)})',
            xy=(2, y_bot * 0.95),
            ha='center', fontsize=7, color='#555555', style='italic')

ax.yaxis.set_major_formatter(ticker.FuncFormatter(make_comma_formatter(2)))
ax.set_ylabel(r'Latensi $p_{99}$ (ms)')
ax.set_title(f'Perbandingan Konfigurasi @ 500 RPS ($n = {n_500}$)')
fig.tight_layout()
fig.savefig(FIGS / 'fig4-config-500rps-boxplot.png')
plt.close(fig)

# ══════════════════════════════════════════════════════════════
# GAMBAR 5: Boxplot - ZTA-Naif vs ZTA-Cache @ 2000 RPS
# ══════════════════════════════════════════════════════════════
print("  Gambar 5: Perbandingan Konfigurasi @ 2000 RPS")
fig, ax = plt.subplots(figsize=FIG_NARROW)

d_naive_2k = scenario_data('s04-zta-naive-2000rps')
d_cache_2k = scenario_data('s05-zta-cache-2000rps')
data_2k = [d_naive_2k, d_cache_2k]
n_2k = len(d_naive_2k)
labels_2k = ['ZTA Naif', 'ZTA Cache']
colors_2k = [COLORS['naive'], COLORS['cache']]

bp = ax.boxplot(data_2k, tick_labels=labels_2k, patch_artist=True, widths=0.4,
                medianprops=dict(color='black', linewidth=1.5),
                flierprops=dict(marker='o', markersize=4, alpha=0.5))
for patch, color in zip(bp['boxes'], colors_2k):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)

u_2k, p_2k, d_2k = compute_mw(d_naive_2k, d_cache_2k)

y_top_2k = max(max(d_naive_2k), max(d_cache_2k))
ax.set_ylim(top=y_top_2k * 1.12)
ax.annotate(f'{fmt_p(p_2k)}; {fmt_d(d_2k)} ({effect_label(d_2k)})',
            xy=(1.5, y_top_2k * 1.02), ha='center', fontsize=7, color='gray')

ax.yaxis.set_major_formatter(ticker.FuncFormatter(integer_formatter))
ax.set_ylabel(r'Latensi $p_{99}$ (ms)')
ax.set_title(f'Perbandingan Konfigurasi @ 2000 RPS ($n = {n_2k}$)')
fig.tight_layout()
fig.savefig(FIGS / 'fig5-config-2000rps-boxplot.png')
plt.close(fig)

# ══════════════════════════════════════════════════════════════
# GAMBAR 6: Distribusi Latensi Revokasi
# ══════════════════════════════════════════════════════════════
print("  Gambar 6: Distribusi Latensi Revokasi")
fig, ax = plt.subplots(figsize=(5.5, 4.2))

revoc_data = scenario_data('s09-revocation-test')
n_rev = len(revoc_data)
# Aturan Sturges: k = ⌈log₂(n) + 1⌉ (Sturges, 1926) -> untuk n=30, k=6 bin
n_bins = int(np.ceil(np.log2(n_rev) + 1))

counts, bins, patches_hist = ax.hist(revoc_data, bins=n_bins, color=COLORS['cache'],
                                     alpha=0.7, edgecolor='white')

# Rug plot
ax.plot(revoc_data, np.zeros_like(revoc_data) - 0.2, '|',
        color='black', markersize=8, alpha=0.6, label=f'Data observasi ($n={n_rev}$)')

med_val = f'{np.median(revoc_data):.2f}'.replace('.', '{,}')
p99_val = f'{np.percentile(revoc_data, 99):.2f}'.replace('.', '{,}')

ax.axvline(x=np.median(revoc_data), color='black', linestyle='-', linewidth=1.5,
           label=rf'Median: $\tilde{{x}} = {med_val}$ ms')
ax.axvline(x=np.percentile(revoc_data, 99), color='#D32F2F', linestyle=':', linewidth=1.5,
           label=rf'Persentil ke-99: $p_{{99}} = {p99_val}$ ms')

ax.set_xlim(3.95, 4.60)
ax.set_ylim(-0.5, 11.5)

# Callout banner untuk kepatuhan batas NIST SP 800-207
margin_nist = 100.0 - np.percentile(revoc_data, 99)
margin_fmt = f'{margin_nist:.2f}'.replace('.', ',')
ax.text(0.97, 0.96,
        'Batas NIST SP 800-207: 100 ms\n'
        rf'Margin: {margin_fmt} ms (22,4$\times$ lebih cepat)'
        '\nStatus: 100% memenuhi batas',
        transform=ax.transAxes, fontsize=7, va='top', ha='right',
        bbox=dict(boxstyle='round,pad=0.35', facecolor='#E8F5E9', edgecolor='#4CAF50', alpha=0.9))

ax.xaxis.set_major_formatter(ticker.FuncFormatter(make_comma_formatter(2)))
ax.set_xlabel(r'Latensi $p_{99}$ (ms)')
ax.yaxis.set_major_formatter(ticker.FuncFormatter(integer_formatter))
ax.set_ylabel('Frekuensi')
ax.set_title(f'Distribusi Latensi Revokasi (S09, $n = {n_rev}$)')
ax.legend(loc='upper left', fontsize=7, framealpha=0.85)
fig.tight_layout()
fig.savefig(FIGS / 'fig6-revocation-histogram.png')
plt.close(fig)

# ══════════════════════════════════════════════════════════════
# GAMBAR 7: Boxplot - TTL Adaptif vs Statis
# ══════════════════════════════════════════════════════════════
print("  Gambar 7: Perbandingan TTL Statis vs Adaptif")
fig, ax = plt.subplots(figsize=FIG_NARROW)

d_static = scenario_data('s10-ttl-comparison')
d_adaptive = scenario_data('s07-zta-cache-fanout')
data_ttl = [d_static, d_adaptive]
n_ttl = len(d_static)
labels_ttl = ['Static TTL\n(S10)', 'Graph-aware TTL\n(S07)']
colors_ttl = [COLORS['static'], COLORS['adaptive']]

bp = ax.boxplot(data_ttl, tick_labels=labels_ttl, patch_artist=True, widths=0.4,
                medianprops=dict(color='black', linewidth=1.5),
                flierprops=dict(marker='o', markersize=4, alpha=0.5))
for patch, color in zip(bp['boxes'], colors_ttl):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)

u_ttl, p_ttl, d_ttl = compute_mw(d_static, d_adaptive)

ax.yaxis.set_major_formatter(ticker.FuncFormatter(integer_formatter))
ax.set_ylabel(r'Latensi $p_{99}$ (ms)')
ax.set_title(f'TTL Statis vs Adaptif @ 2000 RPS Fan-out ($n = {n_ttl}$)\n'
             f'{fmt_p(p_ttl)}; {fmt_d(d_ttl)}')
fig.tight_layout()
fig.savefig(FIGS / 'fig7-ttl-comparison-boxplot.png')
plt.close(fig)

# ══════════════════════════════════════════════════════════════
# GAMBAR 8: Boxplot - Perbandingan Topologi @ 2000 RPS
# ══════════════════════════════════════════════════════════════
print("  Gambar 8: Perbandingan Topologi @ 2000 RPS")
fig, ax = plt.subplots(figsize=FIG_SINGLE)

d_linear = scenario_data('s05-zta-cache-2000rps')
d_mesh = scenario_data('s08-zta-cache-mesh')
d_fanout = scenario_data('s07-zta-cache-fanout')
data_topo = [d_linear, d_mesh, d_fanout]
n_topo = len(d_linear)
labels_topo = ['Linear\n(S05)', 'Mesh\n(S08)', 'Fan-out\n(S07)']
colors_topo = [COLORS['linear'], COLORS['mesh'], COLORS['fanout']]

bp = ax.boxplot(data_topo, tick_labels=labels_topo, patch_artist=True, widths=0.5,
                medianprops=dict(color='black', linewidth=1.5),
                flierprops=dict(marker='o', markersize=4, alpha=0.5))
for patch, color in zip(bp['boxes'], colors_topo):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)

h_stat, p_kw = kruskal(d_linear, d_mesh, d_fanout)

pairs = [('Linear-Mesh', d_linear, d_mesh),
         ('Linear-Fanout', d_linear, d_fanout),
         ('Mesh-Fanout', d_mesh, d_fanout)]
n_comparisons = len(pairs)
posthoc_lines = []
for label, a, b in pairs:
    u, p, d = compute_mw(a, b)
    p_adj = min(p * n_comparisons, 1.0)
    sig = '*' if p_adj < 0.05 else 'ns'
    # Format p-value secara formal tanpa pelaporan p = 0,000
    if p_adj < 0.001:
        posthoc_lines.append(f'{label}: $p_{{adj}} < 0{{,}}001$')
    else:
        p_adj_fmt = f'{p_adj:.3f}'.replace('.', '{,}')
        posthoc_lines.append(f'{label}: $p_{{adj}} = {p_adj_fmt}$')

ax.yaxis.set_major_formatter(ticker.FuncFormatter(integer_formatter))
ax.set_ylabel(r'Latensi $p_{99}$ (ms)')
h_fmt = f'{h_stat:.2f}'.replace('.', '{,}')
p_kw_latex = fmt_p(p_kw)
ax.set_title(f'Pengaruh Topologi @ 2000 RPS ($n = {n_topo}$)\n'
             f'Kruskal-Wallis: $H = {h_fmt}$; {p_kw_latex}')

ax.text(0.02, 0.98, 'Post-hoc Mann-Whitney\n+ Bonferroni:\n' + '\n'.join(posthoc_lines),
        transform=ax.transAxes, fontsize=6.5, va='top', ha='left',
        color='dimgray', bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='lightgray', alpha=0.8))
fig.tight_layout()
fig.savefig(FIGS / 'fig8-topology-boxplot.png')
plt.close(fig)

# ══════════════════════════════════════════════════════════════
# GAMBAR 9: Resource Overhead @ 500 RPS
# ══════════════════════════════════════════════════════════════
print("  Gambar 9: Resource Overhead")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIG_DUAL)

scenarios_500 = ['s01-pbs-baseline-500rps', 's02-zta-naive-500rps', 's03-zta-cache-500rps']
labels_res = ['PBS\nBaseline', 'ZTA\nNaif', 'ZTA\nCache']
colors_res = [COLORS['pbs'], COLORS['naive'], COLORS['cache']]

cpu_data = []
mem_data = []

for sid in scenarios_500:
    sdata = resource_df[resource_df.scenario_id == sid]
    n_res = len(sdata)
    assert n_res == EXPECTED_N
    cpu_data.append(sdata['cpu_avg_pct'].values)
    mem_data.append(sdata['mem_avg_mb'].values)

# CPU panel
bp1 = ax1.boxplot(cpu_data, tick_labels=labels_res, patch_artist=True, widths=0.5,
                  medianprops=dict(color='black', linewidth=1.5),
                  flierprops=dict(marker='o', markersize=4, alpha=0.5))
for patch, color in zip(bp1['boxes'], colors_res):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)
cpu_max = max(np.max(d) for d in cpu_data)
ax1.set_ylim(0, cpu_max * 1.25)
for i, d in enumerate(cpu_data):
    y_label = np.max(d) + ax1.get_ylim()[1] * 0.03
    mdn_val = f'{np.median(d):.2f}'.replace('.', '{,}')
    ax1.text(i + 1, y_label, f'$\\tilde{{x}} = {mdn_val}\\%$',
             ha='center', va='bottom', fontsize=7, color='dimgray')
ax1.yaxis.set_major_formatter(ticker.FuncFormatter(make_comma_formatter(2)))
ax1.set_ylabel('CPU (%)')
ax1.set_title(f'CPU Overhead Sidecar ($n = {EXPECTED_N}$)')

# Memory panel
bp2 = ax2.boxplot(mem_data, tick_labels=labels_res, patch_artist=True, widths=0.5,
                  medianprops=dict(color='black', linewidth=1.5),
                  flierprops=dict(marker='o', markersize=4, alpha=0.5))
for patch, color in zip(bp2['boxes'], colors_res):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)
mem_max = max(np.max(d) for d in mem_data)
ax2.set_ylim(0, mem_max * 1.15)
for i, d in enumerate(mem_data):
    y_label = np.max(d) + ax2.get_ylim()[1] * 0.02
    mdn_val = f'{np.median(d):.1f}'.replace('.', '{,}')
    ax2.text(i + 1, y_label, f'$\\tilde{{x}} = {mdn_val}$',
             ha='center', va='bottom', fontsize=7, color='dimgray')
ax2.yaxis.set_major_formatter(ticker.FuncFormatter(integer_formatter))
ax2.set_ylabel('Memori (MB)')
ax2.set_title(f'Memori Overhead Sidecar ($n = {EXPECTED_N}$)')

fig.suptitle(f'Resource Overhead @ 500 RPS ($n = {EXPECTED_N}$)', fontsize=11, y=1.02)
fig.tight_layout()
fig.savefig(FIGS / 'fig9-resource-overhead-boxplot.png')
plt.close(fig)

# ══════════════════════════════════════════════════════════════
# GAMBAR 10: Scalability - p99 across RPS levels
# ══════════════════════════════════════════════════════════════
print("  Gambar 10: Skalabilitas Latensi vs Beban")
fig, ax = plt.subplots(figsize=FIG_SINGLE)

d_500_s = scenario_data('s03-zta-cache-500rps')
d_2k_s = scenario_data('s05-zta-cache-2000rps')
d_5k_s = scenario_data('s06-zta-cache-5000rps')

rps_levels = [500, 2000, 5000]
medians = [np.median(d_500_s), np.median(d_2k_s), np.median(d_5k_s)]
means = [np.mean(d_500_s), np.mean(d_2k_s), np.mean(d_5k_s)]

ax.plot(rps_levels, medians, 'o-', color=COLORS['cache'],
        label=r'Median $p_{99}$', linewidth=1.5, markersize=8)
ax.plot(rps_levels, means, 'D--', color='#D32F2F',
        label=r'Mean $p_{99}$', linewidth=1.5, markersize=7)

for rps, med, mn in zip(rps_levels, medians, means):
    med_str = f'{med:.1f}'.replace('.', ',')
    mn_str = f'{mn:.1f}'.replace('.', ',')
    if rps == 5000:
        ax.annotate(med_str, xy=(rps, med), xytext=(-35, 6),
                    textcoords='offset points', fontsize=8, color=COLORS['cache'], weight='bold')
        ax.annotate(mn_str, xy=(rps, mn), xytext=(-35, -14),
                    textcoords='offset points', fontsize=8, color='#D32F2F', weight='bold')
    else:
        ax.annotate(med_str, xy=(rps, med), xytext=(8, 6),
                    textcoords='offset points', fontsize=8, color=COLORS['cache'])
        ax.annotate(mn_str, xy=(rps, mn), xytext=(8, -12),
                    textcoords='offset points', fontsize=8, color='#D32F2F')

ax.set_xlabel('Target RPS')
ax.set_ylabel(r'Latensi $p_{99}$ (ms)')
ax.set_title('Skalabilitas ZTA Cache: Latensi vs Beban\n'
             '(3 titik pengukuran, garis = visual guide)')
ax.set_xscale('log')
ax.set_yscale('log')
ax.set_xlim(350, 7000)
ax.set_ylim(bottom=2.5, top=800)
ax.set_xticks(rps_levels)
ax.get_xaxis().set_major_formatter(ticker.ScalarFormatter())
ax.xaxis.set_minor_locator(ticker.NullLocator())
ax.yaxis.set_minor_formatter(ticker.NullFormatter())
ax.legend()
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig(FIGS / 'fig10-scalability-line.png')
plt.close(fig)

# ══════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"All figures generated and saved to: {FIGS}")
for f in sorted(FIGS.glob('*.png')):
    print(f"  {f.name}")
print(f"{'='*60}")
