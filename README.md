# Replication Package: Zero Trust, Near-Zero Cost: Predictive Authorization Caching with Microservice Graph Prioritization in Service Mesh

[![Artifact Evaluation](https://img.shields.io/badge/Artifact-Available%20%26%20Reproducible-success.svg)](#)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Traceability](https://img.shields.io/badge/Traceability%20Audit-91%2F91%20PASS-brightgreen.svg)](#quick-start-1-click-verification)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

Official, standalone **Replication Package & Artifact Evaluation Suite** for the academic paper:

> **"Zero Trust, Near-Zero Cost: Predictive Authorization Caching with Microservice Graph Prioritization in Service Mesh"**  
> *Moh. Radithyo Surya Martuah (Universitas Negeri Gorontalo)*

---

## 1. Quick Start: 1-Click Verification (< 10 seconds)

Verify that **every single empirical number in the paper** matches the underlying data without re-running the 50-hour benchmark:

```bash
python scripts/verify_traceability.py
```

Expected output: `HASIL: 91/91 PASS, 0/91 FAIL` across all tables and statistical tests.

---

## 2. Reproducing the Full Data Pipeline (< 2 minutes)

1. **Audit Raw Data Integrity (600 files):**
   ```bash
   python scripts/validate-data.py
   ```
2. **Consolidate Benchmark Datasets:**
   ```bash
   python scripts/analyze-all-data.py
   ```
3. **Run Statistical Tests (TOST, Mann-Whitney, Kruskal-Wallis):**
   ```bash
   python scripts/statistical-analysis.py
   ```
4. **Regenerate Canonical Figures:**
   ```bash
   python scripts/generate-figures.py
   ```
5. **Evaluate Algorithmic Complexity Model:**
   ```bash
   python scripts/scalability-analysis.py
   ```

---

## 3. License & Commercial Adoption

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.  
It is completely free to read, replicate, evaluate, modify, and use for academic, research, and open-source purposes.

### Commercial Licensing & Proprietary Adoption
If your organization wishes to adopt, integrate, or commercialize this predictive authorization caching algorithm into proprietary, closed-source, or commercial enterprise products without being subject to the viral copyleft terms of GPLv3, a **separate commercial license** is required.

Please contact the author directly for commercial licensing agreements, custom enterprise integration, or consultancy:
- **Author:** Moh. Radithyo Surya Martuah
- **Email:** thyo.surya@gmail.com
