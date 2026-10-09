# Zero Trust, Near-Zero Cost: Predictive Authorization Caching with Microservice Graph Prioritization in Service Mesh

**Moh. Radithyo Surya Martuah[^1]**

[^1]: Department of Information Systems, Universitas Negeri Gorontalo, Indonesia, email: thyo.surya@gmail.com

---

## Abstract

Zero Trust (ZT) architecture mandates authorization verification for every inter-service call within a service mesh, potentially introducing significant latency overhead in large-scale microservice environments. This study proposes a predictive authorization caching algorithm that leverages real-time graph topology analysis to adaptively determine delegation token Time-to-Live (TTL) based on call frequency, data sensitivity, and certificate validity. The system comprises three components: a Graph Topology Analyzer based on betweenness centrality, a Cache Distributor via gRPC streaming, and a WASM filter on Envoy sidecars as a local decision engine. Experiments were conducted on a three-node Kubernetes cluster (k3s, Istio) across 10 test scenarios with 30 repetitions. Results show that the caching mechanism yields statistically equivalent p99 latency to the non-cached configuration ($U = 564.0$, $p = 0.093$, Cliff's $\delta = 0.25$) under a normal 500 RPS load, corroborated by TOST equivalence testing ($p_{TOST} < 0.001$). The system maintains stable performance at 2000 RPS (p99 = 16.74 ms) before cluster saturation at 5000 RPS (p99 = 407.38 ms). The adaptive TTL strategy achieves end-to-end latency equivalent to static TTL ($U = 450.0$, $p = 1.000$) without statistically significant CPU or memory overhead on sidecars ($p > 0.05$). Certificate revocation latency reached 4.46 ms at the 99th percentile, well below the 100 ms threshold of NIST SP 800-207, while topology comparisons revealed significant differences ($H = 79.12$, $p < 0.001$) driven by call concurrency patterns. These findings demonstrate the viability of topology-based predictive caching as a secure, resource-efficient authorization accelerator for Zero Trust service meshes.

**Keywords:** zero trust architecture, predictive caching, service mesh, micro-segmentation, graph topology, delegation token, latency optimization

---

## 1. Introduction

The widespread adoption of microservice architectures has fundamentally transformed the software engineering paradigm from monolithic codebases toward distributed, loosely coupled services communicating over the network (Haindl et al., 2024). Microservices naturally benefit from the Zero Trust model's core tenets of dynamic access control and continuous verification, as interconnected service topologies necessitate rigorous authentication and authorization checks for every inter-service request and response (Samonte et al., 2024). However, this architectural decomposition introduces critical security challenges, particularly across East-West inter-service communications that can no longer rely on perimeter-based perimeter security mechanisms (Chandramouli, 2022). The National Institute of Standards and Technology (NIST) Special Publication 800-207 formally establishes Zero Trust Architecture (ZTA), stipulating that every individual access request must be explicitly evaluated and authorized without granting implicit trust based on network topology or host physical location (Rose et al., 2020). While modern distributed environments increasingly require access control mechanisms that are dynamic, adaptive, and evaluated in real time, complex centralized policy enforcement points routinely incur significant latency overhead and severe computational bottlenecks in large-scale deployments (Farhadighalati et al., 2025).

In cloud-native service meshes, ZTA is predominantly enforced using sidecar proxies, such as Envoy, which intercept and mediate all inbound and outbound inter-service traffic. Situating inspection and policy evaluation logic directly in-proxy via WebAssembly (WASM) extensions enables granular, policy-based access control and threat mitigation across in-transit L4–L7 traffic without requiring intrusive modifications to application source code or the core proxy runtime (Chandramouli & Hales, 2024). Nevertheless, naive ZTA implementations that forward every individual request to a centralized Policy Decision Point (PDP) induce substantial latency overhead that degrades end-to-end application responsiveness, particularly under elevated concurrency (Chandramouli & Butcher, 2023). This phenomenon aligns directly with empirical post-implementation challenges documented in recent literature, which emphasize acute performance degradation and operational complexity resulting from continuous real-time authorization checks in large-scale distributed systems (Gambo & Almulhem, 2025). Furthermore, runtime scalability remains an open hurdle in ZTA implementations, as purely theoretical security abstractions often fail to withstand the throughput demands of dynamic cloud-native workloads (Dakić et al., 2024). Consequently, diverse mitigation strategies have been proposed; for example, Dhanapala et al. (2024) introduced a performance-driven reputation framework permitting nodes to conduct consecutive operational sessions without repeated full re-authentication and re-authorization, thereby reducing ZTA overhead on resource-constrained edge systems. Within cloud-native service meshes, local caching mechanisms have similarly been introduced to amortize policy lookup latencies; however, conventional implementations rely almost exclusively on static Time-to-Live (TTL) thresholds that remain entirely oblivious to the underlying structural dynamics of the service mesh.

Recent research demonstrates that graph-theoretic analysis of microservice call topologies offers critical structural insights into inter-service communication patterns, creating opportunities for systemic performance optimization (Bakhtin et al., 2025). Betweenness centrality, which quantifies how frequently a particular node serves as an intermediary along the shortest communication paths connecting other nodes, has proven effective across diverse networked domains for identifying mission-critical service hubs (Freeman, 1977). Despite this diagnostic utility, the practical application of real-time graph topological analysis to govern authorization caching strategies in cloud-native service meshes remains largely unexplored.

A critical research gap therefore persists: the lack of an authorization caching mechanism that adaptively calibrates token TTLs based on live service mesh topological characteristics in real time. Existing paradigms either apply static, blanket TTL durations or narrowly evaluate raw invocation frequencies without concurrently accounting for data sensitivity classifications and cryptographic certificate lifespans.

To resolve these limitations, this paper proposes a predictive authorization caching algorithm that synthesizes real-time graph topology analysis, call frequencies, data sensitivity levels, and certificate validity windows to adaptively compute delegation token TTLs. The primary contributions of this paper are threefold:

1. **Formulation of an Adaptive TTL Computation Algorithm**: We formulate a multi-factor TTL calculation model combining call frequency, data sensitivity penalties, and residual certificate lifespans, coupled with a betweenness-centrality-based graph prioritization mechanism to identify and prioritize critical inter-service communication channels.
2. **Cloud-Native Non-Intrusive Architecture**: We design and implement a tripartite system architecture comprising a Graph Topology Analyzer, a high-throughput gRPC Cache Distributor, and an Envoy WebAssembly (WASM) filter, enabling plug-and-play integration into production Istio service meshes without modifying application source code.
3. **Rigorous Experimental Validation Across Topologies**: We conduct an extensive experimental evaluation across 10 benchmark scenarios, 30 independent repetitions (300 benchmark runs), and three topological patterns (linear, fan-out, and mesh), empirically validating through two one-sided tests (TOST) that the proposed predictive caching achieves near-zero latency overhead without compromising cryptographic safety or proxy resource budgets.

---

## 2. Related Work

### 2.1 Zero Trust Architecture in Service Meshes

Zero Trust Architecture (ZTA) is a foundational cybersecurity paradigm that eliminates the traditional concept of an implicit trusted network zone, mandating strict, continuous, and explicit verification for every access request (Rose et al., 2020). In microservice environments, operationalizing ZTA is substantially reinforced by DevSecOps practices, wherein security policies, specifically mutual authentication and fine-grained authorization, are automated across continuous integration and continuous deployment (CI/CD) pipelines as Policy-as-Code (Chandramouli, 2022).

Within cloud-native deployments, a service mesh provides an indispensable architectural infrastructure layer to govern, secure, and monitor cross-service interactions, with control and data planes (such as Istio and Envoy) deployed to deliver uniform traffic management, end-to-end observability, and automated cryptographic enforcement (Verma, 2025). Service mesh ZTA implementations conventionally employ the sidecar proxy pattern, where every workload pod incorporates an Envoy proxy container that transparently intercepts all inbound and outbound traffic. While this design decouples security enforcement from application source code, pervasive mutual TLS (mTLS) handshaking and protocol parsing across sidecars impose severe latency overheads, resulting in substantial p99 latency spikes and elevated CPU consumption compared to unencrypted native communication (Bremler-Barr et al., 2024). Furthermore, evaluating authorization policies at every hop across deep microservice invocation call chains introduces cumulative latency delays directly onto critical request-processing paths (Chandramouli & Butcher, 2023).

### 2.2 Caching Mechanisms in Distributed Systems

Caching represents a classical and effective strategy to amortize data access and computation latencies across distributed architectures, particularly when multiple services concurrently query shared computational resources or metadata stores (Kumar, 2025). In access control workflows, caching Policy Decision Point (PDP) decisions within local sidecar proxies eliminates the recurring network overhead of querying external authorization engines for subsequent requests that share identical security contexts. However, the efficacy of authorization caching hinges critically on calibrating the Time-to-Live (TTL): excessively long TTL intervals heighten security exposure windows by serving revoked or stale permissions, whereas excessively brief TTLs degrade cache hit ratios and overwhelm upstream authorization engines.

Prior research has explored cryptographic delegation tokens to distribute authorization decisions toward edge nodes and proxies; however, these mechanisms predominantly enforce static, hardcoded TTL values that fail to reflect fluctuating traffic conditions. Enforcing uniform, constant TTL intervals across JSON Web Tokens (JWT) or symmetric delegation tokens curtails responsiveness to shifting traffic regimes and undermines the principle of continuous verification in ZTA. The imperative for flexible, risk-adaptive token lifetimes is further underscored by Ma et al. (2025), who demonstrated that delegating verification to edge nodes using dynamic time-bound tokens can reduce local verification latency by up to 70% while safeguarding the Zero Trust security posture through context-aware re-authentication mechanisms.

### 2.3 Graph Topology Analysis in Microservices

Graph-theoretic modeling has emerged as a powerful paradigm for analyzing and optimizing complex dependencies within microservice architectures. Betweenness centrality, which evaluates the proportion of shortest topological communication paths traversing a particular vertex, has demonstrated particular efficacy in pinpointing structural bottlenecks and mission-critical services within microservice dependency graphs (Freeman, 1977; Bakhtin et al., 2025).

Moreover, empirical analyses by Du et al. (2025) demonstrate that inter-service invocation patterns are inherently non-stationary, exhibiting temporal fluctuations driven by user workloads, distributed tracing pathways, and dynamic feature activation. This volatility highlights the shortcomings of static, uniform caching mechanisms, accentuating the necessity of an adaptive paradigm capable of reacting to topology shifts in real time.

In security contexts, graph analysis has traditionally been harnessed for intrusion detection and communication anomaly discovery. This study extends graph-theoretic principles beyond passive observability, employing real-time betweenness centrality to dynamically calibrate cache retention and prioritize cache pre-population for critical authorization pathways, which represents an approach unprecedented in cloud-native security literature.

### 2.4 Research Positioning

Table 1 summarizes the positioning of this study relative to related state-of-the-art works in the literature.

**Table 1.** Comparison with related research

| Reference | Adaptive TTL | Graph Topology | Delegation Token | Experimental Evaluation |
|---|---|---|---|---|
| Haindl et al. (2024) | No | No | No | Systematic Literature Review (SLR) |
| Dhanapala et al. (2024) | No | No | No (Reputation-based) | Simulation (LEAF) |
| Chandramouli & Butcher (2023) | No | No | Yes | Conceptual Framework (NIST) |
| Bakhtin et al. (2025) | No | Yes | No | Empirical Case Study |
| Du et al. (2025) | No | Yes | No | Synthetic Benchmark |
| **This study** | **Yes** | **Yes** | **Yes** | **Production Kubernetes Testbed** |

---

## 3. Research Methodology

### 3.1 Research Design

This research employs a quantitative experimental methodology using black-box performance evaluation techniques. Four distinct research hypotheses are formulated as follows:

- **H1:** The predictive caching mechanism produces a p99 latency that differs significantly from the naive ZTA configuration (without caching).
- **H2:** Certificate revocation latency satisfies the 100 ms threshold mandated by NIST SP 800-207.
- **H3:** Adaptive (graph-aware) TTL produces a p99 latency that differs significantly from static TTL.
- **H4:** Variations in topological communication patterns (linear, fan-out, and mesh) produce statistically significant differences in p99 latency.

Hypotheses H1 and H3 are evaluated using the non-parametric two-sided Mann-Whitney U test ($\alpha = 0.05$). If the conventional significance test fails to reject the null hypothesis ($p > 0.05$), the evaluation protocol proceeds with the Two One-Sided Tests (TOST) equivalence procedure to positively verify whether performance differences reside strictly within an acceptable practical equivalence margin. Hypothesis H2 is evaluated descriptively against the 100 ms threshold specified in NIST SP 800-207, whereas H4 is assessed using the multi-group Kruskal-Wallis H test, followed by post-hoc pairwise Mann-Whitney tests with Bonferroni correction.

Experiments were conducted on a Kubernetes testbed configured to represent a production microservice environment. By design, Kubernetes incorporates foundational principles consistent with Zero Trust concepts, enabling the deployment of internal cluster security controls backed by Network Segmentation, Role-Based Access Control (RBAC), and Open Policy Agent (OPA) (Verma, 2025). The independent variables comprise the authorization configuration (PBS baseline, naive ZTA, and ZTA with predictive cache), request workload (500, 2000, and 5000 RPS), and graph topology (linear, fan-out, and mesh). The measured dependent variables include 99th percentile end-to-end latency (p99), actual throughput, sidecar CPU and memory overhead, and certificate revocation latency. Each scenario was executed with 30 independent repetitions. It is noteworthy that each individual repetition (a 5-minute steady-state execution) generates between 150,000 and 600,000 individual HTTP requests depending on the target RPS, ensuring that internal p99 point estimates per run achieve empirical asymptotic stability. Consequently, the 30 repetitions represent 30 independent observations of the p99 metric itself, which are subsequently analyzed via non-parametric inferential statistics across groups. This sample size fulfills the required minimum for inter-repetition distribution estimation (Walpole et al., 2020).

### 3.2 System Architecture

The proposed system comprises three primary components integrated into the Istio service mesh data plane, as illustrated in Figure 1.

**Figure 1.** Predictive authorization caching system architecture

![Predictive authorization caching system architecture](figures/fig1-system-architecture.png)

The **Graph Topology Analyzer** monitors inter-service call patterns in real time by logging unique source-target identity pairs and computing invocation frequencies per minute. This component implements the betweenness centrality algorithm from the `gonum/graph` library to identify services occupying central structural roles within the dependency graph. Inactive graph edges exhibiting zero traffic for more than 120 seconds are automatically pruned to preserve graph fidelity.

The **Cache Distributor** receives the curated list of cache candidates from the Graph Topology Analyzer and generates delegation tokens cryptographically signed using HMAC-SHA256. Tokens are proactively streamed to sidecars via high-throughput gRPC connections every 30 seconds. Each token payload encapsulates the source SPIFFE ID, target SPIFFE ID, permitted actions, calibrated TTL, and a unique revocation nonce.

The **WASM Filter** operates within the Envoy sidecar proxy as an in-process local decision engine. The selection of WebAssembly is driven by its capability to provide secure, memory-isolated sandboxing and near-native runtime performance via the embedder runtime API (Zhang et al., 2025), thereby enabling local authorization evaluation without incurring inter-process communication overhead. The filter evaluates inbound requests through a sequential validation pipeline: (1) HMAC signature verification, (2) expiration check, (3) nonce validation against a local revocation bloom filter or blacklist, and (4) action matching. Upon a cache miss, the filter safely falls back to querying the centralized PDP (OPA).

### 3.3 TTL Computation Algorithm

The TTL for any directed service pair is computed using the following formulation:

$$TTL(A \rightarrow B) = T_{base} \times w_f \times (1 - p_s) \times v_c \quad \text{...(1)}$$

where:

- $T_{base} = 30,000\text{ ms}$ represents the base TTL duration.
- $w_f = \min\left(\dfrac{f_{calls}}{100},\ 1.0\right)$ denotes the frequency weight, which scales TTL upward for frequently communicating service pairs, where $f_{calls}$ is the call frequency per minute.
- $p_s \in \{0.0,\ 0.3,\ 0.7\}$ corresponds to the data sensitivity penalty for *low*, *medium*, and *high* sensitivity levels, respectively, shortening cache retention for sensitive data assets. These penalty values reflect the three-tier data classification standard widely adopted in enterprise information security (ISO 27001), where high-sensitivity data mandates substantially restricted TTLs to minimize security exposure windows. Technically, data sensitivity ratings are defined declaratively in the OPA policy database (`data.service_rules` in `data.json`). The Graph Topology Analyzer and Cache Distributor query these sensitivity attributes via REST API calls to OPA per source-target SPIFFE pair, deterministically mapping them to the numeric penalty $p_s$ within the TTL computation module (`ttl.go`).
- $v_c = \dfrac{t_{remaining}}{t_{total}}$ expresses the residual validity ratio of the workload mTLS certificate, ensuring that the delegation token lifetime never outlasts certificate validity.

Because all scaling multipliers are bounded within $[0, 1]$, the maximum theoretical value produced by Equation (1) is $T_{base} = 30,000\text{ ms}$. The final computed TTL is clamped to the operational range of $[5,000\text{ ms},\ 30,000\text{ ms}]$ to prevent cache thrashing from excessively brief lifetimes while avoiding stale decision windows from excessively prolonged retention.

Cache candidate prioritization is governed by the composite priority score formulated in Equation (2):

$$S(e) = w \times \hat{f}(e) + (1 - w) \times C_B(source_e) \quad \text{...(2)}$$

where $S(e)$ is the priority score for directed edge $e$, $\hat{f}(e)$ is the normalized call frequency scaled to $[0, 1]$, $C_B(source_e)$ is the normalized betweenness centrality of the source node, and $w$ is a tuning weight parameter. In this implementation, $w$ is set to $0.7$.

This formulation assigns greater weight to call frequency (70%) relative to topological positioning (30%). This weighting ratio is established based on two considerations. First, caching benefits scale directly with entry reuse frequency: infrequently invoked service pairs derive negligible latency advantages from cache retention, making call frequency the primary predictor of cache utility. Second, centrality acts as a structural correction factor, ensuring that services acting as routing hubs across multiple execution paths receive prioritized cache allocation, as cache misses on hub nodes inflict disproportionate downstream delays.

A sensitivity analysis evaluating variations in $w$ (from 0.0 to 1.0 in increments of 0.05) reveals that edge priority rankings remain entirely stable (Kendall's $\tau = 1.0$ against the baseline reference $w = 0.7$) across all tested weight ranges for the experimental topology (Figure 2). This demonstrates that $w = 0.7$ is robust and insensitive to minor weight perturbations. In larger, more complex topologies exhibiting greater centrality variance, an increased centrality weight ($w < 0.7$) can be readily accommodated.

**Figure 2.** Sensitivity analysis of cache priority weights

![Sensitivity analysis of cache priority weights](figures/fig2-weight-sensitivity.png)

### 3.4 Testbed Specifications

Experiments were executed on a three-node Kubernetes virtual machine cluster deployed on Microsoft Azure, with hardware and software specifications detailed in Table 2.

**Table 2.** Testbed specifications

| Component | Specification |
|---|---|
| Nodes (3 units) | 2 vCPU (AMD EPYC 7763), 8 GB RAM, 50 GB SSD |
| Operating system | Ubuntu 22.04.5 LTS, kernel 6.8.0-1059-azure |
| Container orchestrator | k3s v1.28.5+k3s1 (containerd 1.7.11) |
| Service mesh | Istio 1.20.1 (Envoy proxy 1.28.0) |
| Policy engine | Open Policy Agent 0.60.0 |
| Load generator | k6 v1.6.1 |
| Monitoring | Prometheus 2.48.1 (scrape interval: 5 seconds) |
| mTLS | STRICT mode across all namespaces |

The benchmark workload utilizes a customized deployment of Online Boutique (Google Cloud Microservices Demo), comprising three core services: frontend (the ingress entry point exposing endpoints `/api/products`, `/api/cart`, and `/health`), productcatalogservice, and cartservice. All load generator traffic is directed to the frontend service, which handles requests locally. Each service pod is injected with an Istio Envoy sidecar with strict resource limits of 200m CPU and 128 Mi memory. Authorization evaluation is executed locally by the WASM filter deployed on the frontend sidecar for each incoming request.

### 3.5 Experimental Scenarios

Ten benchmark scenarios were systematically designed to assess diverse dimensions of system performance, as outlined in Table 3.

**Table 3.** Experimental scenario matrix

| Code | Configuration | RPS | Topology | Objective |
|---|---|---|---|---|
| S01 | PBS Baseline | 500 | Linear | Baseline reference without authorization |
| S02 | Naive ZTA | 500 | Linear | ZTA overhead without caching |
| S03 | ZTA Cache | 500 | Linear | Cache efficacy under normal workload |
| S04 | Naive ZTA | 2000 | Linear | PDP degradation under high concurrency |
| S05 | ZTA Cache | 2000 | Linear | Cache resilience under high concurrency |
| S06 | ZTA Cache | 5000 | Linear | Stress test at cluster saturation threshold |
| S07 | ZTA Cache | 2000 | Fan-out | Cache efficacy under fan-out topology |
| S08 | ZTA Cache | 2000 | Mesh | Cache efficacy under mesh topology |
| S09 | ZTA Cache | 500 | Linear | Certificate revocation evaluation |
| S10 | ZTA Cache (Static TTL) | 2000 | Fan-out | Static TTL baseline for comparison with S07 (Adaptive TTL) |

Every scenario was driven by the `constant-arrival-rate` executor in k6 for a 5-minute steady-state duration. The standardized execution procedure comprises five phases: (1) testbed state reset, (2) a 30-second warmup period with 10 Virtual Users (VUs), (3) a 30-second pre-test cooldown, (4) benchmark execution, and (5) a 120-second cooldown period between scenarios. During initial data collection, the fan-out scenarios (S07, S10) and mesh scenario (S08) encountered request arrival throttling within the k6 load generator script due to discrepant interpretations of iteration arrival rates (`rate` per second) during parallel batch calls, resulting in initial throughput falling below the 2000 RPS target (~428–500 RPS). Consequently, these three scenarios were re-executed (*rerun*) using an updated execution script configured with adjusted arrival rates (`rerun-fixed-scenarios.sh`), successfully achieving commensurate and valid throughput levels (~1700 RPS for S07 and S10, and ~1475 RPS for S08).

Topology variations in this experiment are defined by the call patterns dispatched by the load generator (k6) to the frontend service, yielding distinct authorization evaluation dynamics across the Envoy sidecar. The linear topology queries a single endpoint per iteration (`/api/products`), prompting the sidecar to evaluate a single authorization pair. The fan-out topology dispatches three concurrent requests via `http.batch()` to `/api/products`, `/api/cart`, and `/health`, requiring the sidecar to evaluate three authorization pairs within a single iteration. The mesh topology dispatches one request per iteration in a round-robin rotation across all three endpoints, simulating a distributed communication spread. Figure 3 illustrates these three structural variations.

**Figure 3.** Call pattern (topology) variations in the experiment

![Call pattern (topology) variations in the experiment](figures/fig3-topology-variations.png)

It should be emphasized that all endpoints (`/api/products`, `/api/cart`, and `/health`) are handled locally by the frontend service. The topology variations do not represent deep inter-backend service invocation chains; rather, they reflect distinct request patterns traversing the Envoy sidecar, producing varied authorization evaluation loads and graph topology recordings. Under the fan-out topology, p99 latency is governed by the slowest response within each batch (ceiling effect), whereas under the mesh topology, each request per iteration is evaluated independently. All communication is secured via mTLS and mediated by the WASM filter executing authorization decisions.

### 3.6 Statistical Analysis Methods

Quantitative statistical evaluation follows a multi-tiered inferential protocol governed by the following mathematical formalisms:

1. **Normality Testing**: Evaluated using the Shapiro-Wilk test ($n = 30$ per group) to determine the distributional normality of the empirical data:

$$W = \frac{\left(\sum_{i=1}^n a_i x_{(i)}\right)^2}{\sum_{i=1}^n (x_i - \bar{x})^2} \quad \text{...(3)}$$

where $x_{(i)}$ is the $i$-th order statistic from the ordered sample, $a_i$ represents the Shapiro-Wilk weights derived from the expected order statistic covariances of a standard normal distribution, and $\bar{x}$ denotes the sample mean. The null hypothesis $H_0$ (normal distribution) is rejected if $p < \alpha$ ($\alpha = 0.05$).

2. **Two-Sample Hypothesis Testing**: Evaluated using the non-parametric Mann-Whitney U test:

$$U = n_1 n_2 + \frac{n_1(n_1 + 1)}{2} - R_1 \quad \text{...(4)}$$

where $n_1$ and $n_2$ are the sample sizes of the respective groups ($n_1 = n_2 = 30$), and $R_1$ is the rank sum of the first group within the pooled data. The evaluated two-sided hypothesis is $H_0: P(X > Y) = P(Y > X)$ at a significance level of $\alpha = 0.05$.

3. **Effect Size Measurement**: Quantified using Cliff's Delta ($\delta$) to assess the magnitude of non-parametric group differences:

$$\delta = \frac{\#\{x_i > y_j\} - \#\{x_i < y_j\}}{n_1 \times n_2} \quad \text{...(5)}$$

where $\#\{x_i > y_j\}$ denotes the number of paired occurrences in which an observation from the first group exceeds that of the second group, and $\#\{x_i < y_j\}$ denotes the converse. Values of $\delta \in [-1, 1]$ are interpreted using the empirical benchmarks established by Romano et al. (2006): $|\delta| < 0.147$ (*negligible*), $0.147 \leq |\delta| < 0.330$ (*small*), $0.330 \leq |\delta| < 0.474$ (*medium*), and $|\delta| \geq 0.474$ (*large*).

4. **Multi-Group Comparison**: Evaluated using the Kruskal-Wallis H test:

$$H = \left[\frac{12}{N(N+1)} \sum_{j=1}^{k} \frac{R_j^2}{n_j}\right] - 3(N+1) \quad \text{...(6)}$$

where $N$ is the total pooled sample size ($N = \sum_{j=1}^k n_j$), $k$ is the number of experimental groups ($k = 3$), $n_j$ is the sample size of group $j$, and $R_j$ is the rank sum of group $j$. Post-hoc pairwise comparisons are conducted via Mann-Whitney U tests with Bonferroni correction to control the family-wise error rate, yielding an adjusted significance threshold of $\alpha' = \alpha / k'$ across $k' = \binom{k}{2} = 3$ pairs ($\alpha' = 0.0167$).

5. **Practical Equivalence Testing**: Evaluated using the Two One-Sided Tests (TOST) procedure (Schuirmann, 1987) to positively confirm whether observed performance differences reside within a predefined practical equivalence band. The test evaluates two composite one-sided hypotheses:

$$\begin{aligned} H_{01}: \theta \leq -\Delta \quad &\text{vs.} \quad H_{11}: \theta > -\Delta \\ H_{02}: \theta \geq +\Delta \quad &\text{vs.} \quad H_{12}: \theta < +\Delta \end{aligned} \quad \text{...(7)}$$

where $\theta$ is the location shift parameter of median differences estimated via the Hodges-Lehmann estimator, and $\Delta$ is the equivalence margin set to $\Delta = 5\%$ of the baseline median ($0.214\text{ ms}$). The overall test $p$-value is defined as $p_{TOST} = \max(p_1, p_2)$. Practical equivalence is confirmed if $p_{TOST} < \alpha$ ($\alpha = 0.05$).

6. **Confidence Intervals**: The confidence interval for median estimates is determined using non-parametric percentile bootstrap resampling with $B = 10,000$ iterations and a fixed pseudorandom seed (seed = 42) (Efron & Tibshirani, 1993):

$$CI_{1-\alpha} = \left[\hat{\theta}^*_{(\alpha/2)},\ \hat{\theta}^*_{(1 - \alpha/2)}\right] \quad \text{...(8)}$$

where $\hat{\theta}^*_{(q)}$ is the $q$-th percentile value of the bootstrap median distribution.

Primary data for latency and throughput metrics were acquired from k6 JSON summary exports, while sidecar resource overhead metrics (CPU and memory) were collected from Prometheus via the queries `container_cpu_usage_seconds_total` and `container_memory_working_set_bytes`.

### 3.7 Data Processing and Verification Pipeline

Data processing was executed via an automated three-stage analytical pipeline. In the first stage, the script `analyze-all-data.py` (Python 3.10, pandas 2.2, scipy 1.14, numpy 2.2) consolidated 300 k6 JSON summary files and 300 Prometheus CSV files into a unified dataset. This script extracted primary metrics (p99 latency, mean latency, actual RPS, and error rate) across all experimental runs, generating four primary dataset files: `latency-all-scenarios.csv`, `resource-overhead.csv`, `cache-performance.csv`, and `revocation-latency.csv`.

In the second stage, the validation script `validate-data.py` conducted an automated audit across 10 distinct integrity checks: (1) completeness of all 600 data files (300 JSON + 300 CSV), (2) verification of 30 repetitions per scenario, (3) JSON parsing integrity and required metric presence, (4) verification that error rates remained below 1%, (5) assessment of actual throughput deviation against targets, (6) confirmation of test durations approximating 300 seconds, (7) outlier detection using the $1.5 \times \text{IQR}$ rule, (8) Prometheus CSV schema validation, (9) cross-validation of data provenance (original vs. rerun sources), and (10) descriptive statistical sanity checks.

In the third stage, all statistical tests (Shapiro-Wilk, Mann-Whitney U, Cliff's Delta, and Kruskal-Wallis) were computed automatically by the analysis scripts and exported as structured CSV files in `data/reports/`. Canonical statistical visualizations were generated using `generate-figures.py` (matplotlib 3.10). All analytical scripts are publicly available within the replication repository to support independent reproducibility.

---

## 4. Results and Discussion

### 4.1 Descriptive Statistics

Table 4 summarizes the descriptive statistics of the p99 latency metric across all experimental scenarios.

**Table 4.** Descriptive statistics of p99 latency ($n = 30$ per scenario)

| Code | Configuration | Median (ms) | 95% CI | Mean (ms) | Std Dev (ms) | CV (%) | Actual RPS |
|---|---|---|---|---|---|---|---|
| S01 | PBS Baseline 500 | 4.28 | [4.23; 4.33] | 4.27 | 0.10 | 2.4 | 499.8 |
| S02 | Naive ZTA 500 | 4.30 | [4.24; 4.33] | 4.28 | 0.12 | 2.7 | 499.8 |
| S03 | ZTA Cache 500 | 4.22 | [4.15; 4.31] | 4.24 | 0.12 | 2.9 | 499.8 |
| S04 | Naive ZTA 2000 | 16.24 | - | 16.16 | 1.76 | 10.9 | 1999.6 |
| S05 | ZTA Cache 2000 | 16.74 | - | 16.62 | 1.70 | 10.2 | 1999.6 |
| S06 | ZTA Cache 5000 | 407.38 | - | 407.60 | 7.28 | 1.8 | 4185.2 |
| S07 | ZTA Cache Fan-out | 1322.49 | - | 1320.82 | 77.85 | 5.9 | 1725.2 |
| S08 | ZTA Cache Mesh | 499.25 | - | 497.36 | 17.41 | 3.5 | 1478.0 |
| S09 | Revocation Test | 4.25 | - | 4.26 | 0.11 | 2.7 | 499.8 |
| S10 | Static TTL Fan-out | 1317.52 | - | 1323.93 | 69.45 | 5.2 | 1715.5 |

*Note: 95% CI is computed using percentile bootstrap ($B = 10,000$, seed = 42). CI is reported exclusively for scenarios S01–S03, which form the focus of formal equivalence testing.*

The coefficient of variation (CV) remains below 11% across all scenarios, demonstrating robust empirical reproducibility across independent repetitions. Error rates were recorded at 0.00% across all scenarios with the exception of S09 (0.007%, attributed directly to the active certificate revocation mechanism).

Table 5 presents the resource overhead measurements recorded on the Envoy sidecar proxies.

**Table 5.** Envoy sidecar resource overhead ($n = 30$ per scenario)

| Code | Configuration | CPU Avg (%) | Memory Avg (MB) |
|---|---|---|---|
| S01 | PBS Baseline 500 RPS | 1.79 | 55.90 |
| S02 | Naive ZTA 500 RPS | 1.78 | 55.85 |
| S03 | ZTA Cache 500 RPS | 1.76 | 55.29 |
| S04 | Naive ZTA 2000 RPS | 5.90 | 55.38 |
| S05 | ZTA Cache 2000 RPS | 6.02 | 55.44 |
| S06 | ZTA Cache 5000 RPS | 11.42 | 56.35 |
| S07 | ZTA Cache Fan-out | 10.35 | 61.95 |
| S08 | ZTA Cache Mesh | 8.98 | 61.56 |
| S09 | Revocation Test 500 RPS | 1.76 | 56.03 |
| S10 | Static TTL Fan-out | 11.74 | 66.78 |

### 4.2 ZTA Authorization Overhead and Caching Efficacy (H1)

Figure 4 illustrates the p99 latency distributions across the three baseline and evaluation configurations under the 500 RPS workload.

**Figure 4.** Boxplot comparing configurations at 500 RPS

![Boxplot comparing configurations at 500 RPS](figures/fig4-config-500rps-boxplot.png)

Prior to evaluating caching efficacy, we empirically verify whether naive ZTA authorization introduces detectable overhead compared to the baseline configuration without authorization (PBS baseline). The Mann-Whitney U test (Equation 4) and Cliff's Delta (Equation 5) between PBS Baseline (S01) and Naive ZTA (S02) at 500 RPS yield the results summarized in Table 6a.

**Table 6a.** Mann-Whitney U test results: PBS Baseline vs Naive ZTA

| Comparison | n | Median A (ms) | Median B (ms) | U | p | δ | Effect |
|---|---|---|---|---|---|---|---|
| PBS vs Naive ZTA @ 500 | 30 vs 30 | 4.28 | 4.30 | 429.0 | 0.762 | -0.05 | Negligible |

The median difference of 0.02 ms between PBS (4.28 ms) and Naive ZTA (4.30 ms) is not statistically significant ($p = 0.762$; $\delta = -0.05$, negligible). This finding reveals that at 500 RPS, the per-call authorization overhead imposed by naive ZTA is minimal and imperceptible at the end-to-end latency tier. Consequently, because naive ZTA overhead is inherently small under moderate load, the absolute headroom for latency reduction achievable by client-side caching is similarly constrained at the end-to-end response level.

Next, hypothesis H1 evaluates whether predictive caching reduces p99 latency relative to the naive ZTA configuration. The Shapiro-Wilk test (Equation 3) indicates that the underlying data distributions satisfy normality assumptions (Naive ZTA 500: $W = 0.9707$, $p = 0.559$; ZTA Cache 500: $W = 0.9390$, $p = 0.085$). The Mann-Whitney U test (Equation 4) is retained consistently across all inferential comparisons as a robust non-parametric standard.

**Table 6b.** Mann-Whitney U test results for H1

| Comparison | n | Median A (ms) | Median B (ms) | U | p | δ | Effect |
|---|---|---|---|---|---|---|---|
| Naive ZTA vs Cache @ 500 | 30 vs 30 | 4.30 | 4.22 | 564.0 | 0.093 | 0.25 | Small |
| Naive ZTA vs Cache @ 2000 | 30 vs 30 | 16.24 | 16.74 | 392.0 | 0.395 | -0.13 | Negligible |

Under the 500 RPS load, the median p99 latency difference between Naive ZTA (4.30 ms) and ZTA Cache (4.22 ms) is not statistically significant ($p = 0.093 > 0.05$), although the effect size is classified as small ($\delta = 0.25$). Under the elevated 2000 RPS workload, a comparable outcome is observed ($p = 0.395$; $\delta = -0.13$, negligible).

Figure 5 visualizes the comparative latency distributions under the 2000 RPS workload.

**Figure 5.** Boxplot comparing configurations at 2000 RPS

![Boxplot comparing configurations at 2000 RPS](figures/fig5-config-2000rps-boxplot.png)

Synthesizing the findings from Tables 6a and 6b highlights an important empirical reality: per-call ZTA authorization overhead is minuscule (less than 0.1 ms) relative to cumulative end-to-end processing latencies, meaning neither naive evaluation nor cached resolution produces a statistically discernible shift in total request durations. A direct comparison between PBS Baseline and ZTA Cache is presented in Table 6c.

**Table 6c.** Mann-Whitney U test results: PBS Baseline vs ZTA Cache

| Comparison | n | Median A (ms) | Median B (ms) | U | p | δ | Effect |
|---|---|---|---|---|---|---|---|
| PBS vs ZTA Cache @ 500 | 30 vs 30 | 4.28 | 4.22 | 547.0 | 0.154 | 0.22 | Small |

The comparison between PBS Baseline and ZTA Cache likewise reveals no statistically significant difference ($p = 0.154$; $\delta = 0.22$, small), confirming that integrating the full ZTA security apparatus (policy enforcement combined with predictive caching) incurs no detectable performance penalty. Notably, these three comparisons (Tables 6a–6c) do not explicitly apply Bonferroni corrections; under an adjusted threshold of $\alpha' = 0.0167$, all conclusions remain strictly unchanged (all $p \gg 0.0167$). With $n = 30$ per group and $\alpha = 0.05$, the Mann-Whitney test possesses sufficient statistical power to detect large effects ($|\delta| \geq 0.474$), whereas statistical power for detecting small effects ($|\delta| \approx 0.25$) is estimated at approximately 0.40; therefore, the absence of statistical significance does not imply that subtle differences are definitively nonexistent.

To positively confirm practical equivalence rather than merely relying on a failure to reject the null hypothesis, formal equivalence testing was conducted using the Two One-Sided Tests (TOST) framework (Schuirmann, 1987) with an equivalence margin set to $\Delta = 5\%$ of the baseline median (0.214 ms). Table 6d reports the equivalence testing results.

**Table 6d.** TOST equivalence test results ($\Delta = 0.214\text{ ms}$, $\alpha = 0.05$)

| Comparison | Hodges-Lehmann $\hat{\Delta}$ (ms) | p_TOST | Decision |
|---|---|---|---|
| PBS vs Naive ZTA @ 500 | -0.011 | < 0.001 | Equivalent |
| Naive ZTA vs Cache @ 500 | 0.062 | < 0.001 | Equivalent |
| PBS vs ZTA Cache @ 500 | 0.042 | < 0.001 | Equivalent |

All comparisons confirm practical equivalence ($p_{TOST} < 0.001$), with the Hodges-Lehmann location shift estimates falling substantially within the equivalence boundary ($\hat{\Delta} < 0.07\text{ ms} \ll \Delta = 0.214\text{ ms}$). The bootstrap 95% confidence interval for the median difference (PBS − ZTA Cache) spans $[-0.047, 0.158]\text{ ms}$, entirely bounded within the equivalence interval of $[-0.214, +0.214]\text{ ms}$. This empirical evidence confirms that establishing ZTA security with predictive caching is not merely non-inferior statistically, but is **proven practically equivalent** to an unsecured baseline configuration, validating that Zero Trust can be operationalized without measurable latency compromises under these testing regimes.

The minimal overhead scale observed in this investigation (under 0.1 ms per call) is substantially lower than continuous verification penalties documented elsewhere in Zero Trust literature. By way of comparison, browser-based behavioral biometrics for user authenticity verification reported response time escalations from approximately 20 ms to nearly 130 ms in production web application environments (Sasada et al., 2024). This divergence stems primarily from the unit of verification: behavioral biometrics necessitates compute-intensive inference over user interaction models upon every transaction, whereas the predictive caching proposed here operates at inter-service network boundaries through local in-process memory lookups that incur negligible computational overhead.

### 4.3 Hypothesis Testing H2: Revocation Latency

The second hypothesis investigates whether certificate revocation latency complies with the 100 ms upper bound prescribed by NIST SP 800-207. Table 7 details the empirical findings from scenario S09.

**Table 7.** Revocation latency test results ($n = 30$)

| Metric | Value |
|---|---|
| Mean p99 latency | 4.26 ms |
| Median p99 latency | 4.25 ms |
| 99th percentile of p99 distribution | 4.46 ms |
| NIST SP 800-207 threshold | 100 ms |
| Threshold satisfied | Yes (margin: 95.54 ms) |
| Successful revocations per run (mean) | 10.7 events |

Figure 6 visualizes the empirical distribution of revocation latencies.

**Figure 6.** Revocation latency distribution

![Revocation latency distribution](figures/fig6-revocation-histogram.png)

Revocation latency reached 4.46 ms at the 99th percentile, residing well below the 100 ms threshold by a substantial safety margin of 95.54 ms. This confirms the efficacy of the nonce-based invalidation mechanism within the Envoy WASM filter, whereby revoked credentials are immediately denied upon local nonce verification without waiting for round-trip synchronization with an upstream policy decision point. This outcome aligns with the Failure Management Mechanism (FMM) principles governing distributed Zero Trust architectures, which dictate immediate invalidation of compromised credentials prior to subsequent transaction processing to minimize exposure windows (Ma et al., 2025).

### 4.4 Hypothesis Testing H3: Adaptive vs. Static TTL

The third hypothesis evaluates whether graph-aware adaptive TTL offers measurable performance differentiation compared to static TTL regimes. The evaluation benchmarks S07 (graph-aware TTL with active topology analyzer) against S10 (static TTL with analyzer disabled, enforcing a uniform 30-second TTL) under the fan-out topology at 2000 RPS.

**Table 8.** Comparison of adaptive vs static TTL ($n = 30$ per group)

| Comparison | Median S10 (ms) | Median S07 (ms) | U | p | δ | Effect |
|---|---|---|---|---|---|---|
| Static TTL vs Graph-aware TTL | 1317.52 | 1322.49 | 450.0 | 1.000 | 0.00 | Negligible |

The latency distributions between static TTL (S10) and adaptive TTL (S07) configurations are illustrated in Figure 7.

**Figure 7.** Boxplot comparing static vs adaptive TTL

![Boxplot comparing static vs adaptive TTL](figures/fig7-ttl-comparison-boxplot.png)

The statistical analysis indicates no significant difference ($U = 450.0$; $p = 1.000$; $\delta = 0.00$) between adaptive and static TTL strategies at the end-to-end latency tier. Both sample groups conform to normality assumptions under the Shapiro-Wilk test (Equation 3) (S07: $W = 0.9491$, $p = 0.160$; S10: $W = 0.9704$, $p = 0.550$). The Mann-Whitney U test (Equation 4) and Cliff's Delta (Equation 5) corroborate the exact equivalence between the two caching configurations.

It should be clarified that this comparison evaluates end-to-end latency as the primary observable metric rather than direct cache hit ratios. This methodological choice is dictated by the design of the Envoy WASM filter operating as an in-process local decision engine: cache hits and misses are resolved internally within sidecar memory without appending observable tracing headers to downstream client responses. Authorization checks remained active in both configurations, differing strictly in how token lifetimes were assigned (dynamically computed vs. constant 30 seconds). End-to-end latency represents an authoritative proxy because any divergence in caching efficacy directly triggers fallback requests to the centralized PDP, which would immediately manifest as quantifiable latency spikes.

These empirical results can be interpreted through two operational perspectives. First, the adaptive TTL computation imposes zero detectable latency overhead on the request path, verifying that all topological graph processing executes strictly out-of-band on the control plane. Second, during a 5-minute steady-state benchmark, differences between adaptive and static expiration windows do not accumulate sufficiently to create measurable divergences in end-to-end response times. The distinct security and operational advantages of adaptive TTL are expected to manifest predominantly in longer-running deployments characterized by non-stationary call patterns, where static TTL intervals heighten the risk of serving stale decisions.

### 4.5 Impact of Topology

The influence of communication topology was evaluated using the Kruskal-Wallis H test across the three structural configurations at 2000 RPS. Figure 8 illustrates the distributional variations across topologies.

**Figure 8.** Boxplot comparing topologies at 2000 RPS

![Boxplot comparing topologies](figures/fig8-topology-boxplot.png)

**Table 9.** Kruskal-Wallis test results for topology effect

| Topology | Scenario | Median p99 (ms) | Actual RPS |
|---|---|---|---|
| Linear | S05 | 16.74 | 1999.6 |
| Mesh | S08 | 499.25 | 1478.0 |
| Fan-out | S07 | 1322.49 | 1725.2 |

The Kruskal-Wallis test (Equation 6) yields $H = 79.12$ ($p < 0.001$), demonstrating statistically significant differences across topologies. Post-hoc pairwise Mann-Whitney tests (Equation 4) with Bonferroni correction ($\alpha' = 0.0167$) confirm significant differences across all pairs: Linear vs. Fan-out ($\delta = -1.0$, large), Linear vs. Mesh ($\delta = -1.0$, large), and Fan-out vs. Mesh ($\delta = 1.0$, large).

The observed latency hierarchy (Linear < Mesh < Fan-out) mirrors the structural mechanics of the respective dispatch patterns, although these comparisons are influenced by confounding factors related to request patterns (single-endpoint, round-robin, and batch) and slight variations in achieved throughput (1478–2000 RPS). The linear topology evaluates one endpoint per iteration, yielding the lowest latency due to minimal evaluation concurrency. The mesh topology alternates across three endpoints sequentially, maintaining moderate latency despite traversing multiple authorization rules. In contrast, the fan-out topology dispatches three concurrent requests via `http.batch()`, where p99 latency is governed by the slowest response within each batch (ceiling effect), resulting in the highest observed p99 latency.

Additionally, the non-linear topologies did not fully reach the 2000 RPS target: S07 (fan-out) reached 1725 RPS (86.3%), S08 (mesh) reached 1478 RPS (73.9%), and S10 (static TTL fan-out) reached 1716 RPS (85.8%). These constraints reflect cluster hardware capacity saturation under multi-target concurrency rather than software misconfiguration. Crucially, this throughput variance does not undermine the validity of topological comparisons, as observed latency differentials (spanning one to two orders of magnitude) vastly exceed minor discrepancies in realized throughput.

### 4.6 Resource Overhead

The Kruskal-Wallis test (Equation 6) assessing sidecar CPU and memory consumption under the 500 RPS workload indicates no statistically significant difference across the three configurations (PBS, Naive ZTA, and ZTA Cache):

**Table 10.** Kruskal-Wallis test results for resource overhead @ 500 RPS

| Metric | PBS (S01) | Naive ZTA (S02) | ZTA Cache (S03) | H | p |
|---|---|---|---|---|---|
| CPU (%) | 1.79 | 1.78 | 1.76 | 0.81 | 0.668 |
| Memory (MB) | 55.90 | 55.85 | 55.29 | 2.46 | 0.292 |

The distribution of Envoy sidecar CPU and memory utilization across the three configurations is depicted in Figure 9, displaying median values and interquartile ranges (IQR) to complement the averages reported in Table 10.

**Figure 9.** Envoy sidecar resource overhead at 500 RPS

![Sidecar resource overhead](figures/fig9-resource-overhead-boxplot.png)

The Kruskal-Wallis test detects no statistically significant variance in CPU or memory utilization across configurations under 500 RPS ($p > 0.05$). This indicates that empirical observations provide insufficient evidence to reject the null hypothesis of identical resource demand distributions under these operational conditions. However, the lack of statistical significance should not be construed as definitive proof of equivalence, as formal equivalence testing (TOST) was confined to the latency dimension. In practical terms within the evaluated three-node cluster, running the WASM filter directly in-process within Envoy using shared memory for local cache lookups incurs no measurable memory inflation or processing overhead.

### 4.7 Scalability

Figure 10 depicts the progression of p99 latency under increasing workload intensities.

**Figure 10.** Scalability of ZTA Cache: latency vs workload

![Scalability of latency vs workload](figures/fig10-scalability-line.png)

Benchmarking S05 (2000 RPS) against S06 (5000 RPS) reveals severe latency escalation: median p99 increases from 16.74 ms to 407.38 ms ($U = 0.0$; $p < 0.001$; $\delta = -1.0$). This performance degradation is driven by hardware capacity saturation, as the cluster achieved an actual throughput of 4185 RPS against the 5000 RPS target (83.7%). This indicates that the experimental three-node VM configuration reaches its saturation limit between 4000 and 5000 RPS total, demonstrating that horizontal cluster scaling is required to sustain higher concurrency volumes.

### 4.8 Algorithmic Scalability Analysis

Although experimental validations were conducted across three primary services, the scalability of the proposed algorithm across $N$ microservices in production environments can be formally demonstrated through asymptotic complexity analysis.

**Data Plane (WASM Filter): Synchronous Per-Request Evaluation.** The critical-path per-request execution complexity is expressed as:

$$T_{request}(N) = T_{hash} + T_{hmac} + T_{nonce} = O(1) \quad \text{...(9)}$$

where $T_{hash}$ represents local cache hash-map lookup latency, $T_{hmac}$ is HMAC-SHA256 signature verification time, and $T_{nonce}$ is revocation check duration. All operations execute in $O(1)$ constant time because the sidecar local cache is strictly constrained by `maxCandidates` = 50 entries, rendering execution time **strictly independent of $N$**. Experimental measurements confirm a per-request execution overhead of approximately ~0.016 ms (the difference between unrounded medians of S02 at 4.295 ms and S01 at 4.279 ms), which remains invariable as cluster scale expands.

**Control Plane (Graph Topology Analyzer): Asynchronous Periodic Analysis.** The computational bottleneck resides in betweenness centrality calculation via Brandes' algorithm:

$$T_{analysis}(V, E) = O(V \cdot E) + O(E \cdot \log E) + O(K) \quad \text{...(10)}$$

where $V$ is the number of services (vertices), $E$ is the number of active communication edges, and $K = \min(E_{active}, 50)$. In typical microservice topologies, each service communicates with an average of $c$ downstream dependencies ($c \in [2, 5]$), yielding $E \approx c \cdot V$ and reducing computational complexity to $O(c \cdot V^2)$. Crucially, this calculation executes asynchronously out-of-band every 30 seconds, residing completely off the critical request path. Table 11 presents computational scaling projections.

**Table 11.** Control plane scalability projections ($c = 3$, $\alpha = 0.005\text{ ms}$)

| $V$ (Services) | $E \approx 3V$ | $T_{analysis}$ (ms) | $< 30$ seconds? | Per-request overhead |
|---|---|---|---|---|
| 3 (Experiment) | 9 | 0.19 | ✅ | 0.016 ms |
| 10 | 30 | 1.79 | ✅ | 0.016 ms |
| 50 | 150 | 39.67 | ✅ | 0.016 ms |
| 100 | 300 | 154.94 | ✅ | 0.016 ms |
| 500 | 1500 | 3,781.65 | ✅ | 0.016 ms |
| 1000 | 3000 | 15,069.30 | ✅ | 0.016 ms |

**Memory Footprint per Sidecar.** Each Envoy proxy stores at most $K$ delegation tokens:

$$M_{sidecar} = K \times S_{token} \leq 50 \times 400\ \text{B} = 19.5\ \text{KB} \quad \text{...(11)}$$

This value is constant and independent of $N$. For a cluster with $N = 1000$ services, the cumulative memory footprint across all proxies is approximately $1000 \times 19.5\text{ KB} \approx 19.5\text{ MB}$, which is negligible within production cluster memory reserves.

**Token Distribution Bandwidth.** gRPC streaming distribution bandwidth is bounded by `maxCandidates`:

$$BW = \frac{K \times S_{token}}{T_{interval}} \leq \frac{50 \times 400}{30} \approx 667\ \text{B/s} \quad \text{...(12)}$$

For $N \geq 50$, streaming bandwidth converges to approximately ~0.65 KB/s, exerting no observable strain on cluster network fabrics.

This complexity analysis confirms that the proposed architecture readily scales to enterprise microservice clusters comprising up to $N \leq 1000$ services. For deployments exceeding 1000 services, per-namespace topological graph partitioning or approximate betweenness centrality algorithms with $O(V + E)$ complexity can be readily integrated (Geisberger et al., 2008).

---

## 5. Conclusion

This study has developed and evaluated a graph topology-based predictive authorization caching algorithm designed to mitigate latency overhead in Zero Trust service mesh architectures. Based on comprehensive empirical evaluations across 10 test scenarios evaluated over 30 repetitions each, the primary findings are synthesized as follows.

First, the authorization overhead of naive ZTA relative to the PBS baseline was not statistically significant (U = 429.0, p = 0.762, $\delta = -0.05$), and the predictive caching mechanism compared to naive ZTA was likewise not statistically significant (U = 564.0, p = 0.093, $\delta = 0.25$) at a workload of 500 RPS. Furthermore, the Two One-Sided Tests (TOST) equivalence procedure (Schuirmann, 1987) under an equivalence margin of $\Delta = 5\%$ of the baseline median confirmed that all pairwise comparisons were **demonstrated to be practically equivalent** ($p_{\text{TOST}} < 0.001$), with Hodges-Lehmann location shift estimates of less than 0.07 ms. The 95% bootstrap confidence interval for the median difference between PBS and ZTA Cache ([-0.047, 0.158] ms) fell entirely within the equivalence bounds of [-0.214, +0.214] ms. Second, certificate revocation propagation latency was recorded at 4.46 ms at the 99th percentile, satisfying the 100 ms threshold stipulated by NIST SP 800-207 with a substantial margin (95.54 ms margin). Third, service mesh topology exerted a statistically significant effect on end-to-end latency ($H = 79.12, p < 0.001$), following the ordinal hierarchy of Linear (16.74 ms) < Mesh (499.25 ms) < Fan-out (1322.49 ms). Fourth, Envoy proxy sidecar CPU and memory resource consumption exhibited no statistically significant differences between configurations with and without predictive caching (p > 0.05).

This study is subject to several limitations. First, empirical experiments were conducted on a three-node cluster that does not fully replicate the scale and complexity of large-scale production enterprise environments. Second, the comparison between adaptive and static TTL was performed under constant load conditions for 5 minutes, which may not have provided sufficient traffic volatility to demonstrate the dynamic adaptation advantages of adaptive TTL. Third, the cache hit ratio metric could not be measured directly from the client side because the WASM filter evaluates authorization locally within the Envoy process without emitting cache status headers in downstream HTTP responses. Cache hit or miss decisions were recorded exclusively in internal sidecar logs and were not exported to Prometheus in this experimental setup. Consequently, cache effectiveness was evaluated using end-to-end latency as an empirical proxy, an approach that remains valid because every cache miss triggers a fallback to the centralized PDP, introducing measurable additional latency at the end-to-end level. Fourth, the fan-out and mesh scenarios employed differing request dispatch patterns (batch versus single requests), introducing a confounding variable into cross-topology comparisons. Fifth, the testbed deployed a single entry-point architecture where all endpoints were handled locally by the frontend service without invoking East-West calls across backend microservices. Consequently, while the authorization overhead evaluations (H1, H2) and sidecar resource metrics remain fully valid at the Envoy proxy level, the topology analyzed by the Graph Topology Analyzer was trivial (a single active node), meaning the full potential of betweenness centrality analysis and adaptive TTL mechanisms could not be comprehensively manifested. The cross-topology latency differences observed in the Kruskal-Wallis test (H4) reflect differences in request workload patterns (batch volume and concurrency per iteration) rather than multi-hop structural effects on the caching mechanism.

Future research may be directed toward several key avenues: (1) evaluating the proposed system on microservice testbeds featuring genuine East-West inter-service invocation chains (multi-hop execution paths) to validate the effectiveness of betweenness centrality and adaptive TTL on non-trivial topologies, (2) expanding evaluations to larger-scale multi-node clusters subjected to dynamic and bursty traffic profiles to conclusively assess adaptive TTL elasticity, (3) implementing explicit cache hit ratio instrumentation by injecting custom HTTP response headers within the WASM filter and deploying custom Prometheus exporters to track `zta_cache_hits_total` and `zta_cache_misses_total` directly from Envoy proxies, and (4) developing advanced TTL formulations that directly integrate betweenness centrality metrics into the numerical TTL decay equation, beyond its current role in token priority ranking.

---

## Declarations

**Conflict of Interest:** The authors declare that they have no conflict of interest.

**Funding:** This research received no external funding.

**Data Availability:** All raw experimental datasets, statistical analysis scripts, and source code generated and utilized during this study are publicly available in the dedicated replication repository for reproducibility.

---

## References

Bakhtin, A., Esposito, M., Lenarduzzi, V., & Taibi, D. (2025). Network centrality as a new perspective on microservice architecture. *Proceedings of the 2025 IEEE 22nd International Conference on Software Architecture (ICSA)*, 72–83. https://doi.org/10.1109/ICSA65012.2025.00017

Bremler-Barr, A., Lavi, O., Naor, Y., Rampal, S., & Tavori, J. (2024). Performance comparison of service mesh frameworks: The mTLS test case (arXiv:2411.02267). arXiv. https://doi.org/10.48550/arXiv.2411.02267

Chandramouli, R. (2022). *Implementation of DevSecOps for a microservices-based application with service mesh* (NIST SP 800-204C). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-204C

Chandramouli, R., & Hales, W. (2024). A data protection approach for cloud-native applications (NIST Interagency Report NIST IR 8505). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.IR.8505

Chandramouli, R., & Butcher, Z. (2023). *A zero trust architecture model for access control in cloud-native applications in multi-location environments* (NIST SP 800-207A). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-207A

Dakić, V., Morić, Z., Kapulica, A., & Regvart, D. (2024). Analysis of azure zero trust architecture implementation for mid-size organizations. Journal of cybersecurity and privacy, 5(1), 2. https://doi.org/10.3390/jcp5010002

Dhanapala, I., Bharti, S., McGibney, A., & Rea, S. (2024). Toward a performance-based trustworthy edge-cloud continuum. *IEEE Access*, 12, 99201–99212. https://doi.org/10.1109/ACCESS.2024.3429197

Du, F., Shi, J., Chen, Q., Li, L., & Guo, M. (2025). Generating microservice graphs with production characteristics for efficient resource scaling. *Proceedings of the 2025 International Conference on Supercomputing (ICS '25)*. https://doi.org/10.1145/3721145.3725761

Efron, B., & Tibshirani, R. J. (1993). *An introduction to the bootstrap*. Chapman & Hall/CRC.

Farhadighalati, N., Estrada-Jimenez, L. A., Nikghadam-Hojjati, S., & Barata, J. (2025). A systematic review of access control models: Background, existing research, and challenges. IEEE Access, 13, 17777–17806. https://doi.org/10.1109/ACCESS.2025.3533145

Freeman, L. C. (1977). A set of measures of centrality based on betweenness. *Sociometry*, 40(1), 35–41. https://doi.org/10.2307/3033543

Gambo, M. L., & Almulhem, A. (2025). Zero Trust Architecture: A Systematic Literature Review. Journal of Network and Systems Management, 34(1), 25. https://doi.org/10.1007/s10922-025-09998-x

Geisberger, R., Sanders, P., & Schultes, D. (2008). Better approximation of betweenness centrality. *Proceedings of the 10th Workshop on Algorithm Engineering and Experiments (ALENEX)*, 90–100. https://doi.org/10.1137/1.9781611972887.9

Haindl, P., Kochberger, P., & Sveggen, M. (2024). A systematic literature review of inter-service security threats and mitigation strategies in microservice architectures. *IEEE Access*, 12, 90252–90286. https://doi.org/10.1109/ACCESS.2024.3406500

Kumar, V. (2025). Microservice-driven performance optimization in large-scale transaction processing systems. *International Journal of Computational and Experimental Science and Engineering*, 11(4). https://doi.org/10.22399/ijcesen.4461

Ma, Z., Wei, H., Jiang, J., Wang, B., Wang, H., & Di, Z. (2025). A lightweight zero-trust authentication architecture for IoT via unified enhanced FAST-SM9 and dynamic re-authentication. *PLOS ONE*, 20(10), e0332943. https://doi.org/10.1371/journal.pone.0332943

Romano, J., Kromrey, J. D., Coraggio, J., & Skowronek, J. (2006). Appropriate statistics for ordinal level data: Should we really be using t-test and Cohen's d for evaluating group differences on the NSSE findings? *Annual Meeting of the Florida Association of Institutional Research*, 1–33.

Rose, S., Borchert, O., Mitchell, S., & Connelly, S. (2020). *Zero trust architecture* (NIST SP 800-207). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-207

Samonte, M. J. C., Aparize, J. E. R., Geronimo, J. M., & Oriño, C. C. (2024, September). Implementing zero trust security in microservice architecture of electronic health record. In *2024 4th International Conference on Computer Systems (ICCS)* (pp. 98–105). IEEE. https://doi.org/10.1109/ICCS62594.2024.10795827

Sasada, T., Taenaka, Y., Kadobayashi, Y., & Fall, D. (2024). Web-biometrics for user authenticity verification in zero trust access control. *IEEE Access*, 12, 129611–129622. https://doi.org/10.1109/ACCESS.2024.3413696

Schuirmann, D. J. (1987). A comparison of the two one-sided tests procedure and the power approach for assessing the equivalence of average bioavailability. *Journal of Pharmacokinetics and Biopharmaceutics*, 15(6), 657–680. https://doi.org/10.1007/BF01068419

Shapiro, S. S., & Wilk, M. B. (1965). An analysis of variance test for normality. *Biometrika*, 52(3/4), 591–611. https://doi.org/10.2307/2333709

Verma, S. (2025). Zero Trust Architecture in Cloud-Native Environments: Implementation Strategies & Best Practices. *International Journal of Computer Trends and Technology*, 73(4), 114–122. https://doi.org/10.14445/22312803/IJCTT-V73I4P114

Walpole, R. E., Myers, R. H., Myers, S. L., & Ye, K. (2020). *Probability and statistics for engineers and scientists* (9th ed.). Pearson.

Zhang, Y., Liu, M., Wang, H., Ma, Y., Huang, G., & Liu, X. (2025). Research on WebAssembly runtimes: A survey. ACM Transactions on Software Engineering and Methodology, 34(8), Article 239. https://doi.org/10.1145/3714465

