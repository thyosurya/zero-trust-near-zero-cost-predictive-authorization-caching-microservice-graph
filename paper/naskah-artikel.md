# Zero Trust, Near-Zero Cost: Predictive Authorization Caching with Microservice Graph Prioritization in Service Mesh

**Moh. Radithyo Surya Martuah[^1]**

[^1]: Program Studi Sistem Informasi, Universitas Negeri Gorontalo, email: thyo.surya@gmail.com

---

## Abstrak

Arsitektur Zero Trust (ZT) mewajibkan verifikasi otorisasi pada setiap panggilan antar-service dalam service mesh, yang berpotensi menimbulkan overhead latensi signifikan pada lingkungan microservice berskala besar. Penelitian ini mengusulkan algoritma predictive authorization caching yang memanfaatkan analisis graph topology secara real-time untuk menentukan Time-to-Live (TTL) delegation token secara adaptif berbasis frekuensi panggilan, sensitivitas data, dan validitas sertifikat. Sistem diimplementasikan melalui tiga komponen: Graph Topology Analyzer berbasis betweenness centrality, Cache Distributor (gRPC streaming), dan WASM filter pada Envoy sidecar sebagai local decision engine. Eksperimen dilakukan pada klaster Kubernetes tiga node (k3s, Istio) melingkupi 10 skenario pengujian dengan 30 repetisi. Hasil pengujian menunjukkan bahwa mekanisme caching menghasilkan latensi p99 yang setara secara statistik terhadap konfigurasi tanpa cache (U = 564,0; p = 0,093; Cliff's δ = 0,25) pada beban normal 500 RPS, yang dikonfirmasi oleh uji kesetaraan TOST (p_TOST < 0,001). Sistem mempertahankan performa stabil pada 2000 RPS (p99 = 16,74 ms) sebelum mengalami saturasi kapasitas klaster pada 5000 RPS (p99 = 407,38 ms). Strategi TTL adaptif menghasilkan latensi end-to-end yang setara dengan TTL statis (U = 450,0; p = 1,000) tanpa menimbulkan perbedaan signifikan pada beban CPU dan memori sidecar (p > 0,05). Latensi revokasi sertifikat tercatat sebesar 4,46 ms pada persentil ke-99, jauh memenuhi ambang batas 100 ms NIST SP 800-207, sementara perbandingan topologi menunjukkan perbedaan signifikan (H = 79,12; p < 0,001) akibat karakteristik konkurensi panggilan. Temuan ini membuktikan kelayakan predictive caching berbasis topologi sebagai akselerator otorisasi Zero Trust yang aman dan efisien sumber daya.

**Kata Kunci:** zero trust architecture, predictive caching, service mesh, micro-segmentation, graph topology, delegation token, latency optimization

---

## Abstract

Zero Trust (ZT) architecture mandates authorization verification for every inter-service call within a service mesh, potentially introducing significant latency overhead in large-scale microservice environments. This study proposes a predictive authorization caching algorithm that leverages real-time graph topology analysis to adaptively determine delegation token Time-to-Live (TTL) based on call frequency, data sensitivity, and certificate validity. The system comprises three components: a Graph Topology Analyzer based on betweenness centrality, a Cache Distributor via gRPC streaming, and a WASM filter on Envoy sidecars as a local decision engine. Experiments were conducted on a three-node Kubernetes cluster (k3s, Istio) across 10 test scenarios with 30 repetitions. Results show that the caching mechanism yields statistically equivalent p99 latency to the non-cached configuration (U = 564.0, p = 0.093, Cliff's δ = 0.25) under a normal 500 RPS load, corroborated by TOST equivalence testing (p_TOST < 0.001). The system maintains stable performance at 2000 RPS (p99 = 16.74 ms) before cluster saturation at 5000 RPS (p99 = 407.38 ms). The adaptive TTL strategy achieves end-to-end latency equivalent to static TTL (U = 450.0, p = 1.000) without statistically significant CPU or memory overhead on sidecars (p > 0.05). Certificate revocation latency reached 4.46 ms at the 99th percentile, well below the 100 ms threshold of NIST SP 800-207, while topology comparisons revealed significant differences (H = 79.12, p < 0.001) driven by call concurrency patterns. These findings demonstrate the viability of topology-based predictive caching as a secure, resource-efficient authorization accelerator for Zero Trust service meshes.

**Keywords:** zero trust architecture, predictive caching, service mesh, micro-segmentation, graph topology, delegation token, latency optimization

---

## 1. Pendahuluan

Adopsi arsitektur microservice telah mengubah paradigma pengembangan perangkat lunak dari monolitik menjadi layanan-layanan terdistribusi yang saling berkomunikasi melalui jaringan (Haindl et al., 2024). Microservice mendapat manfaat dari penekanan model Zero Trust pada kontrol akses dinamis dan verifikasi konstan karena sistem ini saling terhubung dan setiap permintaan dan jawaban perlu melalui pemeriksaan autentikasi yang ketat (Samonte et al., 2024). Perubahan ini menimbulkan tantangan keamanan baru, khususnya pada komunikasi East-West antar-service yang tidak lagi dilindungi oleh perimeter jaringan tradisional (Chandramouli, 2022). National Institute of Standards and Technology (NIST) melalui SP 800-207 merekomendasikan pendekatan Zero Trust Architecture (ZTA), yang mensyaratkan bahwa setiap permintaan akses harus diverifikasi secara eksplisit tanpa bergantung pada kepercayaan implisit berdasarkan lokasi jaringan (Rose et al., 2020). Kebutuhan akan kontrol akses modern di lingkungan terdistribusi kian menuntut karakteristik dinamis, adaptif, dan real-time, namun evaluasi kebijakan yang semakin kompleks dan tersentralisasi kerap memicu trade-off berupa performance overhead dan beban komputasi yang tinggi pada sistem berskala besar (Farhadighalati et al., 2025).

Implementasi ZTA pada service mesh umumnya menggunakan sidecar proxy seperti Envoy yang melakukan otorisasi pada setiap panggilan antar-service. Penempatan logika inspeksi langsung di dalam proxy (in-proxy) memanfaatkan modul WebAssembly memungkinkan penegakan otorisasi berbasis kebijakan dan mitigasi ancaman secara granular pada lalu lintas data in-transit L4–L7 tanpa memodifikasi kode inti proxy maupun aplikasi (Chandramouli & Hales, 2024). Pendekatan naif yang mengirimkan setiap permintaan ke Policy Decision Point (PDP) terpusat menimbulkan overhead latensi yang dapat berdampak signifikan pada performa aplikasi, terutama pada beban tinggi (Chandramouli & Butcher, 2023). Fenomena ini konsisten dengan tantangan pasca-implementasi ZTA yang telah didokumentasikan dalam literatur, khususnya terkait potensi degradasi performa dan kompleksitas akibat kebutuhan autentikasi dan otorisasi real-time pada jaringan berskala besar (Large-scale Networks) (Gambo & Almulhem, 2025). Lebih jauh lagi, skalabilitas tetap menjadi tantangan signifikan dalam mengimplementasikan ZTA, di mana pendekatan yang hanya mengandalkan model teoretis dinilai tidak cukup untuk mengatasi kompleksitas penskalaan di lingkungan cloud-native yang dinamis (Dakić et al., 2024). Oleh karena itu, berbagai upaya telah dilakukan untuk memitigasi masalah ini; misalnya, Dhanapala et al. (2024) mengusulkan mekanisme reputasi berbasis performa yang memungkinkan node melakukan beberapa sesi berturut-turut (consecutive sessions) tanpa re-autentikasi/re-otorisasi penuh di setiap request, sebagai cara mengurangi overhead ZTA pada perangkat edge dengan resource terbatas. Sementara itu, pada lingkungan service mesh, beberapa pendekatan caching telah diajukan untuk mengatasi masalah serupa, namun sebagian besar menggunakan TTL statis yang tidak mempertimbangkan dinamika topologi service mesh.

Penelitian terkait menunjukkan bahwa analisis graph pada topologi microservice dapat memberikan wawasan mengenai pola komunikasi antar-service yang bermanfaat untuk optimasi performa (Bakhtin et al., 2025). Betweenness centrality, sebagai metrik yang mengukur seberapa sering sebuah node menjadi perantara pada jalur terpendek antar-node lainnya, telah digunakan dalam berbagai konteks jaringan untuk mengidentifikasi node kritikal (Freeman, 1977). Namun, penerapan analisis graph topology secara real-time untuk menentukan kebijakan caching otorisasi pada service mesh belum banyak dieksplorasi.

Celah penelitian yang teridentifikasi adalah belum adanya mekanisme caching otorisasi yang secara adaptif menyesuaikan TTL berdasarkan karakteristik topologi service mesh secara real-time. Penelitian yang ada cenderung menggunakan TTL konstan atau hanya mempertimbangkan frekuensi panggilan tanpa memperhitungkan sensitivitas data dan validitas sertifikat secara bersamaan.

Berdasarkan permasalahan tersebut, penelitian ini mengajukan algoritma predictive authorization caching yang mengintegrasikan analisis graph topology, frekuensi panggilan, sensitivitas data, dan validitas sertifikat untuk menentukan TTL delegation token secara adaptif. Kontribusi utama penelitian ini meliputi:

1. Formulasi algoritma perhitungan TTL adaptif yang menggabungkan tiga faktor: frekuensi panggilan, tingkat sensitivitas data, dan sisa validitas sertifikat, serta mekanisme prioritas caching berbasis betweenness centrality untuk menentukan pasangan service yang diprioritaskan.
2. Arsitektur tiga komponen (Graph Topology Analyzer, Cache Distributor, WASM filter) yang dapat diintegrasikan ke dalam service mesh berbasis Istio tanpa modifikasi pada kode aplikasi.
3. Evaluasi eksperimental komprehensif dengan 10 skenario pengujian pada tiga variasi topologi (linear, fan-out, mesh) yang menunjukkan bahwa mekanisme caching tidak menimbulkan overhead performa yang signifikan secara statistik.

---

## 2. Tinjauan Pustaka

### 2.1 Zero Trust Architecture pada Service Mesh

Zero Trust Architecture (ZTA) merupakan paradigma keamanan yang menghilangkan konsep trusted network zone dan mengharuskan verifikasi eksplisit pada setiap permintaan akses (Rose et al., 2020). Penerapan Zero Trust Architecture (ZTA) pada lingkungan microservice didukung oleh praktik DevSecOps, di mana kebijakan keamanan seperti autentikasi dan otorisasi diotomatisasi melalui pipeline CI/CD sebagai Policy as Code (Chandramouli, 2022).

Service mesh merupakan lapisan arsitektur krusial untuk memfasilitasi interaksi lintas layanan yang robust, aman, dan BFF-limited dalam lingkungan cloud-native Zero Trust, di mana platform seperti Istio dimanfaatkan untuk meningkatkan observabilitas keamanan dan pengelolaan konektivitas (Verma, 2025). Implementasi ZTA pada service mesh seperti Istio menggunakan model sidecar proxy, di mana setiap pod pada Kubernetes memiliki container Envoy yang mencegat seluruh traffic masuk dan keluar. Pendekatan ini memungkinkan penerapan kebijakan keamanan secara transparan tanpa modifikasi kode aplikasi. Namun, penegakan mTLS dan inspeksi protokol pada proxy sidecar Envoy terbukti menimbulkan trade-off performa yang substansial, dengan lonjakan latensi p99 dan beban komputasi yang tinggi dibandingkan komunikasi native (Bremler-Barr et al., 2024). Selain itu, setiap panggilan antar-service memerlukan evaluasi kebijakan otorisasi yang dapat menambah latensi pada jalur kritikal (Chandramouli & Butcher, 2023).

### 2.2 Mekanisme Caching pada Sistem Terdistribusi

Caching merupakan teknik fundamental untuk mengurangi latensi akses pada sistem terdistribusi, cache menjadi sangat penting ketika beberapa layanan mengakses elemen data bersama (Kumar, 2025). Dalam konteks otorisasi, caching keputusan PDP di sisi klien atau sidecar dapat menghilangkan kebutuhan query ke PDP terpusat untuk keputusan yang masih valid. Tantangan utama caching otorisasi terletak pada penentuan TTL yang tepat: TTL terlalu panjang berisiko menggunakan keputusan yang sudah tidak valid (stale decision), sementara TTL terlalu pendek mengurangi efektivitas cache.

Beberapa pendekatan sebelumnya mengajukan mekanisme delegation token untuk mendistribusikan keputusan otorisasi ke edge node, namun TTL yang digunakan bersifat statis dan tidak memperhitungkan dinamika beban kerja. Penggunaan token berbasis JWT dengan TTL konstan membatasi adaptabilitas terhadap perubahan pola traffic, yang bertentangan dengan prinsip verifikasi berkelanjutan dalam ZTA. Kebutuhan akan kontrol durasi token yang fleksibel ini sejalan dengan temuan Ma et al. (2025), yang mendemonstrasikan bahwa delegasi verifikasi berbasis token berbatas waktu dinamis (time-bound dynamic tokens) di sisi edge mampu mereduksi hingga 70% latensi verifikasi lokal seraya mempertahankan postur Zero Trust melalui mekanisme re-autentikasi adaptif peka konteks.

### 2.3 Analisis Graph Topology pada Microservice

Graph topology telah digunakan untuk memodelkan dan menganalisis hubungan antar-service dalam arsitektur microservice. Betweenness centrality, yang mengukur seberapa sering suatu node menjadi perantara dalam jalur terpendek antar-node lain, telah terbukti efektif untuk mengidentifikasi service kritikal dalam ekosistem microservice.

Du et al. (2025) menunjukkan bahwa pola panggilan antar-service bersifat dinamis dan dapat berubah seiring waktu berdasarkan fitur yang diaktifkan dan beban pengguna. Temuan ini mendukung argumen bahwa mekanisme caching yang statis kurang optimal dan diperlukan pendekatan adaptif yang merespons perubahan topologi secara real-time.

Dalam konteks keamanan, analisis graph telah digunakan untuk mendeteksi anomali pada pola komunikasi microservice. Penelitian ini memperluas penerapan analisis graph dengan menggunakannya untuk optimasi TTL caching otorisasi, sebuah pendekatan yang belum dieksplorasi dalam literatur yang ada.

### 2.4 Posisi Penelitian

Tabel 1 merangkum posisi penelitian ini terhadap karya terkait.

**Tabel 1.** Perbandingan dengan penelitian terkait

| Referensi | TTL Adaptif | Graph Topology | Delegation Token | Evaluasi Eksperimental |
|---|---|---|---|---|
| Haindl et al. (2024) | Tidak | Tidak | Tidak | SLR |
| Dhanapala et al. (2024) | Tidak | Tidak | Tidak (reputation-based) | Simulasi (LEAF) |
| Chandramouli dan Butcher (2023) | Tidak | Tidak | Ya | Framework |
| Bakhtin et al. (2025) | Tidak | Ya | Tidak | Studi kasus |
| Du et al. (2025) | Tidak | Ya | Tidak | Benchmark |
| **Penelitian ini** | **Ya** | **Ya** | **Ya** | **Testbed Kubernetes** |

---

## 3. Metode Penelitian

### 3.1 Desain Penelitian

Penelitian ini menggunakan pendekatan eksperimental kuantitatif dengan metode pengukuran black-box performance testing. Empat hipotesis penelitian dirumuskan sebagai berikut:

- **H1:** Mekanisme predictive caching menghasilkan latensi p99 yang berbeda secara signifikan dibandingkan konfigurasi ZTA naif (tanpa cache).
- **H2:** Latensi revokasi sertifikat memenuhi batas waktu 100 ms yang ditetapkan NIST SP 800-207.
- **H3:** TTL adaptif (graph-aware) menghasilkan latensi p99 yang berbeda secara signifikan dibandingkan TTL statis.
- **H4:** Variasi pola komunikasi topologi (linear, fan-out, mesh) menghasilkan perbedaan latensi p99 yang signifikan secara statistik.

Hipotesis H1 dan H3 diuji menggunakan uji non-parametrik Mann-Whitney U dua sisi (α = 0,05). Apabila uji signifikansi konvensional gagal menolak hipotesis nol ($p > 0,05$), protokol pengujian dilanjutkan dengan uji kesetaraan praktis Two One-Sided Tests (TOST) untuk menguji secara positif apakah perbedaan performa berada dalam batas margin ekuivalensi yang dapat diterima. Hipotesis H2 dievaluasi secara deskriptif terhadap ambang batas 100 ms NIST SP 800-207, sedangkan H4 diuji menggunakan uji Kruskal-Wallis multi-kelompok yang dilanjutkan dengan analisis post-hoc Mann-Whitney terkoreksi Bonferroni.

Eksperimen dilakukan pada testbed Kubernetes yang dikonfigurasi untuk merepresentasikan lingkungan microservice produksi. Secara desain, Kubernetes memiliki beberapa prinsip dasar yang konsisten dengan konsep Zero Trust, sehingga memungkinkan untuk menerapkan kontrol keamanan di dalam klaster dengan dukungan Network Segmentation, Role-Based Access Control (RBAC), dan Open Policy Agent (OPA) (Verma, 2025). Variabel independen meliputi konfigurasi otorisasi (PBS baseline, ZTA naif, ZTA dengan predictive cache), beban request (500, 2000, dan 5000 RPS), dan topologi graph (linear, fan-out, mesh). Variabel dependen yang diukur mencakup latensi end-to-end persentil ke-99 (p99), throughput aktual, overhead CPU dan memori sidecar, serta latensi revokasi. Setiap skenario diulang sebanyak 30 kali. Perlu dicatat bahwa setiap satu repetisi (eksekusi selama 5 menit steady-state) menghasilkan sekitar 150.000 hingga 600.000 HTTP request individual (bergantung pada target RPS), sehingga estimasi titik p99 internal pada setiap run sudah stabil secara konvergensi empiris berdasarkan jumlah sampel yang sangat besar. Dengan demikian, 30 repetisi di sini merepresentasikan 30 observasi independen dari nilai p99 itu sendiri, yang kemudian diuji menggunakan statistik non-parametrik antar-kelompok. Jumlah ini memenuhi kecukupan minimal untuk estimasi distribusi antar-repetisi (Walpole et al., 2020).

### 3.2 Arsitektur Sistem

Sistem yang dikembangkan terdiri dari tiga komponen utama yang terintegrasi dengan service mesh Istio, sebagaimana diilustrasikan pada Gambar 1.

**Gambar 1.** Arsitektur sistem predictive authorization caching

![Arsitektur sistem predictive authorization caching](figures/fig1-system-architecture.png)

**Graph Topology Analyzer** memantau pola panggilan antar-service secara real-time dengan mencatat setiap pasangan source-target dan menghitung frekuensi panggilan per menit. Komponen ini menggunakan algoritma betweenness centrality dari pustaka gonum/graph untuk mengidentifikasi service yang memiliki peran sentral dalam topologi. Edge graph yang tidak aktif selama lebih dari 120 detik secara otomatis dihapus (pruned) untuk menjaga akurasi representasi topologi.

**Cache Distributor** menerima daftar kandidat cache dari Graph Topology Analyzer dan menghasilkan delegation token yang ditandatangani menggunakan HMAC-SHA256. Token didistribusikan ke sidecar melalui gRPC streaming setiap 30 detik. Setiap token berisi informasi source, target, allowed actions, TTL, dan revocation nonce.

**WASM Filter** beroperasi di dalam Envoy sidecar sebagai local decision engine. Pemilihan WebAssembly didasarkan pada kemampuannya menyediakan lingkungan sandboxing in-process yang aman, terisolasi secara memori, dan berkinerja tinggi mendekati kecepatan native melalui embedder API runtime (Zhang et al., 2025), sehingga evaluasi otorisasi dapat dieksekusi secara lokal tanpa memperkenalkan overhead konkurensi antar-proses. Filter ini mengevaluasi setiap permintaan masuk dengan urutan validasi: (1) verifikasi signature HMAC, (2) pemeriksaan expiry, (3) validasi nonce terhadap daftar revokasi, dan (4) pencocokan action. Jika cache miss terjadi, filter melakukan fallback ke PDP (OPA) terpusat.

### 3.3 Algoritma Perhitungan TTL

TTL untuk setiap pasangan service dihitung menggunakan formula berikut:

$$TTL(A \rightarrow B) = T_{base} \times w_f \times (1 - p_s) \times v_c \quad \text{...(1)}$$

di mana:

- $T_{base}$ = 30.000 ms, merupakan nilai dasar TTL
- $w_f = \min\left(\dfrac{f_{calls}}{100},\ 1{,}0\right)$, bobot frekuensi yang memberikan TTL lebih panjang untuk pasangan service yang sering berkomunikasi, dengan $f_{calls}$ adalah jumlah panggilan per menit
- $p_s \in \{0{,}0;\ 0{,}3;\ 0{,}7\}$ untuk tingkat sensitivitas data *low*, *medium*, dan *high* secara berturut-turut, mempersingkat TTL untuk data sensitif. Nilai penalti ditetapkan berdasarkan praktik klasifikasi data tiga tingkat yang umum digunakan dalam standar keamanan informasi (ISO 27001), di mana data sensitif tinggi memerlukan TTL yang jauh lebih pendek untuk meminimalkan jendela paparan risiko. Secara teknis, tingkat sensitivitas data didefinisikan secara deklaratif dalam basis data kebijakan OPA (`data.service_rules` pada `data.json`). Modul Graph Topology Analyzer dan Cache Distributor membaca atribut sensitivitas ini melalui kueri REST API ke OPA per pasangan identitas SPIFFE sumber dan target, yang kemudian dipetakan secara deterministik ke dalam nilai penalti numerik $p_s$ oleh modul perhitungan TTL (`ttl.go`).
- $v_c = \dfrac{t_{remaining}}{t_{total}}$, rasio sisa validitas terhadap total validitas sertifikat, memastikan TTL tidak melebihi sisa validitas sertifikat.

Karena seluruh faktor pengali memiliki rentang $[0, 1]$, nilai maksimum yang dapat dihasilkan Persamaan (1) adalah $T_{base}$ = 30.000 ms. Hasil akhir dibatasi (*clamped*) pada rentang $[5.000\ \text{ms},\ 30.000\ \text{ms}]$ untuk mencegah *cache thrashing* akibat TTL terlalu pendek maupun *stale decision* akibat TTL terlalu panjang.

Prioritas kandidat cache ditentukan menggunakan skor gabungan pada Persamaan (2):

$$S(e) = w \times \hat{f}(e) + (1 - w) \times C_B(source_e) \quad \text{...(2)}$$

di mana $S(e)$ adalah skor prioritas untuk edge $e$, $\hat{f}(e)$ adalah frekuensi panggilan ternormalisasi pada rentang $[0, 1]$, $C_B(source_e)$ adalah *betweenness centrality* ternormalisasi dari node sumber, dan $w$ adalah parameter bobot. Pada implementasi ini ditetapkan $w = 0{,}7$.

Formula ini memberikan bobot lebih tinggi pada frekuensi panggilan (70%) dibandingkan posisi topologis (30%). Rasio ini ditetapkan berdasarkan dua pertimbangan. Pertama, manfaat caching bersifat proporsional terhadap frekuensi penggunaan cache entry: pasangan service yang jarang dipanggil memperoleh benefit minimal dari caching, sehingga frekuensi menjadi prediktor utama utilitas cache. Kedua, centrality berfungsi sebagai faktor koreksi untuk memprioritaskan service yang berperan sebagai hub (perantara banyak jalur) dalam topologi, karena kegagalan cache pada hub berdampak lebih luas.

Analisis sensitivitas terhadap variasi parameter $w$ (dari 0,0 hingga 1,0 dengan interval 0,05) menunjukkan bahwa ranking prioritas edge tetap stabil (Kendall's $\tau$ = 1,0 terhadap referensi $w$ = 0,7) pada seluruh rentang bobot yang diuji untuk topologi eksperimen ini (Gambar 2). Hal ini mengindikasikan bahwa pemilihan $w$ = 0,7 bersifat robust dan tidak sensitif terhadap perubahan kecil pada parameter bobot. Pada topologi yang lebih kompleks dengan variasi centrality yang lebih tinggi, bobot centrality yang lebih besar ($w < 0{,}7$) dapat dipertimbangkan.

**Gambar 2.** Analisis sensitivitas bobot prioritas cache

![Analisis sensitivitas bobot prioritas cache](figures/fig2-weight-sensitivity.png)

### 3.4 Spesifikasi Testbed

Eksperimen dilakukan pada klaster Kubernetes yang terdiri dari tiga node virtual machine pada Microsoft Azure, dengan spesifikasi pada Tabel 2.

**Tabel 2.** Spesifikasi testbed

| Komponen | Spesifikasi |
|---|---|
| Node (3 unit) | 2 vCPU (AMD EPYC 7763), 8 GB RAM, 50 GB SSD |
| Sistem operasi | Ubuntu 22.04.5 LTS, kernel 6.8.0-1059-azure |
| Container orchestrator | k3s v1.28.5+k3s1 (containerd 1.7.11) |
| Service mesh | Istio 1.20.1 (Envoy proxy 1.28.0) |
| Policy engine | Open Policy Agent 0.60.0 |
| Load generator | k6 v1.6.1 |
| Monitoring | Prometheus 2.48.1 (scrape interval 5 detik) |
| mTLS | STRICT mode pada seluruh namespace |

Aplikasi target menggunakan Online Boutique (Google Microservices Demo) yang dimodifikasi dan terdiri dari tiga service: frontend (entry point yang menyediakan endpoint `/api/products`, `/api/cart`, dan `/health`), productcatalogservice, dan cartservice. Seluruh traffic dari load generator dikirimkan ke frontend, yang menangani request secara lokal. Setiap service memiliki sidecar Envoy yang di-inject oleh Istio dengan resource limit 200m CPU dan 128 Mi memori. Evaluasi otorisasi dilakukan oleh WASM filter pada sidecar frontend untuk setiap request masuk.

### 3.5 Skenario Pengujian

Sepuluh skenario pengujian dirancang untuk mengevaluasi berbagai aspek performa sistem, sebagaimana ditunjukkan pada Tabel 3.

**Tabel 3.** Matrix skenario pengujian

| Kode | Konfigurasi | RPS | Topologi | Tujuan |
|---|---|---|---|---|
| S01 | PBS Baseline | 500 | Linear | Referensi baseline tanpa otorisasi |
| S02 | ZTA Naif | 500 | Linear | Overhead ZTA tanpa cache |
| S03 | ZTA Cache | 500 | Linear | Efektivitas cache pada beban normal |
| S04 | ZTA Naif | 2000 | Linear | Degradasi PDP saat beban tinggi |
| S05 | ZTA Cache | 2000 | Linear | Ketahanan cache saat beban tinggi |
| S06 | ZTA Cache | 5000 | Linear | Stress test batas kapasitas cache |
| S07 | ZTA Cache | 2000 | Fan-out | Efektivitas pada topologi fan-out |
| S08 | ZTA Cache | 2000 | Mesh | Efektivitas pada topologi mesh |
| S09 | ZTA Cache | 500 | Linear | Pengujian revokasi sertifikat |
| S10 | ZTA Cache (TTL statis) | 2000 | Fan-out | Baseline TTL statis untuk perbandingan dengan S07 (TTL adaptif) |

Setiap skenario menggunakan executor `constant-arrival-rate` pada k6 dengan durasi 5 menit steady-state. Prosedur eksekusi meliputi: (1) reset state testbed, (2) warmup selama 30 detik dengan 10 VU, (3) cooldown 30 detik, (4) eksekusi skenario, dan (5) cooldown 120 detik antar-skenario. Pada pengumpulan data awal, skenario fan-out (S07, S10) dan mesh (S08) mengalami pembatasan laju kedatangan request pada skrip generator k6 akibat perbedaan interpretasi laju iterasi (`rate` per detik) terhadap pemanggilan batch paralel, sehingga throughput aktual awal berada di bawah target 2000 RPS (~428–500 RPS). Oleh karena itu, ketiga skenario tersebut dijalankan ulang (*rerun*) menggunakan skrip eksekusi yang telah disesuaikan konfigurasi kedatangannya (`rerun-fixed-scenarios.sh`), sehingga menghasilkan pencapaian throughput aktual yang setara dan valid (~1700 RPS untuk S07 dan S10, serta ~1475 RPS untuk S08).

Variasi topologi dalam eksperimen ini ditentukan oleh pola panggilan yang dikirimkan load generator (k6) ke frontend service, yang menghasilkan pola evaluasi otorisasi yang berbeda pada Envoy sidecar. Topologi linear menggunakan satu endpoint per iterasi (`/api/products`), sehingga sidecar hanya mengevaluasi satu pasangan otorisasi. Topologi fan-out mengirimkan tiga request secara bersamaan menggunakan `http.batch()` ke endpoint `/api/products`, `/api/cart`, dan `/health`, sehingga sidecar mengevaluasi tiga pasangan otorisasi dalam satu iterasi. Topologi mesh mengirimkan satu request per iterasi secara bergantian (round-robin) ke tiga endpoint tersebut, mensimulasikan pola komunikasi yang lebih terdistribusi. Gambar 3 mengilustrasikan ketiga variasi tersebut.

**Gambar 3.** Variasi pola panggilan (topologi) dalam eksperimen

![Variasi pola panggilan (topologi) dalam eksperimen](figures/fig3-topology-variations.png)

Perlu dicatat bahwa seluruh endpoint (`/api/products`, `/api/cart`, `/health`) ditangani secara lokal oleh frontend service. Perbedaan topologi tidak mencerminkan rantai panggilan antar-backend service (chain), melainkan perbedaan pola request yang melewati Envoy sidecar, yang menghasilkan pola evaluasi otorisasi dan pencatatan graph topology yang berbeda. Pada topologi fan-out, latensi p99 ditentukan oleh response terlambat dalam batch (ceiling effect), sedangkan pada topologi mesh, satu request per iterasi dievaluasi secara independen. Seluruh komunikasi dilindungi oleh mTLS dan melewati WASM filter yang melakukan evaluasi otorisasi.

### 3.6 Metode Analisis Statistik

Analisis statistik kuantitatif dilakukan secara berjenjang dengan formalisasi matematis sebagai berikut:

1. **Uji normalitas** menggunakan uji Shapiro-Wilk ($n = 30$ per kelompok) untuk menentukan sifat parametrik distribusi data:

$$W = \frac{\left(\sum_{i=1}^n a_i x_{(i)}\right)^2}{\sum_{i=1}^n (x_i - \bar{x})^2} \quad \text{...(3)}$$

di mana $x_{(i)}$ adalah statistik urutan (*order statistics*) ke-$i$ dari sampel terurut, $a_i$ adalah koefisien bobot Shapiro-Wilk yang diturunkan dari kovarians statistik urutan distribusi normal standar, dan $\bar{x}$ adalah nilai rata-rata sampel. Hipotesis nol $H_0$ (data berdistribusi normal) ditolak jika nilai $p < \alpha$ ($\alpha = 0{,}05$).

2. **Uji hipotesis dua kelompok independen** menggunakan uji non-parametrik Mann-Whitney U:

$$U = n_1 n_2 + \frac{n_1(n_1 + 1)}{2} - R_1 \quad \text{...(4)}$$

di mana $n_1$ dan $n_2$ adalah ukuran sampel masing-masing kelompok ($n_1 = n_2 = 30$), dan $R_1$ adalah jumlah peringkat (*rank sum*) untuk kelompok pertama pada data gabungan. Hipotesis dua sisi yang diuji adalah $H_0: P(X > Y) = P(Y > X)$ dengan tingkat signifikansi $\alpha = 0{,}05$.

3. **Pengukuran ukuran efek (*effect size*)** menggunakan Cliff's Delta ($\delta$) untuk mengukur derajat perbedaan non-parametrik:

$$\delta = \frac{\#\{x_i > y_j\} - \#\{x_i < y_j\}}{n_1 \times n_2} \quad \text{...(5)}$$

di mana $\#\{x_i > y_j\}$ menyatakan jumlah pasangan di mana observasi kelompok pertama lebih besar daripada kelompok kedua, dan $\#\{x_i < y_j\}$ menyatakan jumlah pasangan sebaliknya. Nilai $\delta \in [-1, 1]$ diinterpretasikan mengikuti ambang batas empiris Romano et al. (2006): $|\delta| < 0{,}147$ (*negligible*), $0{,}147 \leq |\delta| < 0{,}330$ (*small*), $0{,}330 \leq |\delta| < 0{,}474$ (*medium*), dan $|\delta| \geq 0{,}474$ (*large*).

4. **Uji perbedaan multi-kelompok** menggunakan uji Kruskal-Wallis H:

$$H = \left[\frac{12}{N(N+1)} \sum_{j=1}^{k} \frac{R_j^2}{n_j}\right] - 3(N+1) \quad \text{...(6)}$$

di mana $N$ adalah total seluruh observasi ($N = \sum_{j=1}^k n_j$), $k$ adalah jumlah kelompok perlakuan ($k = 3$), $n_j$ adalah ukuran sampel kelompok ke-$j$, dan $R_j$ adalah jumlah peringkat kelompok ke-$j$. Pengujian *post-hoc* dilakukan melalui uji Mann-Whitney berpasangan dengan koreksi Bonferroni untuk mengendalikan *family-wise error rate*, di mana taraf signifikansi terkoreksi adalah $\alpha' = \alpha / k'$ dengan $k' = \binom{k}{2} = 3$ pasangan ($\alpha' = 0{,}0167$).

5. **Uji kesetaraan praktis (*equivalence testing*)** menggunakan prosedur Two One-Sided Tests (TOST) (Schuirmann, 1987) untuk memverifikasi secara positif bahwa perbedaan performa berada di dalam batas kesetaraan praktis. Formulasi pengujian didasarkan pada dua hipotesis satu sisi:

$$\begin{aligned} H_{01}: \theta \leq -\Delta \quad &\text{lawan} \quad H_{11}: \theta > -\Delta \\ H_{02}: \theta \geq +\Delta \quad &\text{lawan} \quad H_{12}: \theta < +\Delta \end{aligned} \quad \text{...(7)}$$

di mana $\theta$ adalah parameter pergeseran lokasi (*location shift*) perbedaan median yang diestimasi menggunakan estimator Hodges-Lehmann, dan $\Delta$ adalah batas margin kesetaraan yang ditetapkan sebesar $\Delta = 5\%$ dari median baseline ($0{,}214\text{ ms}$). Nilai $p$ gabungan dihitung sebagai $p_{TOST} = \max(p_1, p_2)$. Kesetaraan praktis diterima jika $p_{TOST} < \alpha$ ($\alpha = 0{,}05$).

6. **Interval kepercayaan (*confidence interval*)** untuk estimasi median dihitung menggunakan metode *percentile bootstrap* non-parametrik dengan $B = 10.000$ sampel ulang dan penentu acak tetap (*random seed* = 42) (Efron & Tibshirani, 1993):

$$CI_{1-\alpha} = \left[\hat{\theta}^*_{(\alpha/2)},\ \hat{\theta}^*_{(1 - \alpha/2)}\right] \quad \text{...(8)}$$

di mana $\hat{\theta}^*_{(q)}$ adalah nilai persentil ke-$q$ dari distribusi estimasi median hasil resampling bootstrap.

Sumber data primer untuk latensi dan throughput adalah k6 summary export (format JSON), sedangkan data resource overhead (CPU, memori) diperoleh dari Prometheus melalui query `container_cpu_usage_seconds_total` dan `container_memory_working_set_bytes`.

### 3.7 Verifikasi Pengolahan Data

Pengolahan data dilakukan menggunakan pipeline otomatis yang terdiri dari tiga tahap. Tahap pertama, skrip `analyze-all-data.py` (Python 3.10, pandas 2.2, scipy 1.14, numpy 2.2) melakukan penggabungan (merge) 300 file k6 JSON summary dan 300 file Prometheus CSV menjadi dataset terkonsolidasi. Skrip ini mengekstrak metrik kunci (p99, mean, actual RPS, error rate) dari setiap file dan menghasilkan empat file output: `latency-all-scenarios.csv`, `resource-overhead.csv`, `cache-performance.csv`, dan `revocation-latency.csv`.

Tahap kedua, skrip `validate-data.py` melakukan audit otomatis terhadap kelengkapan dan integritas dataset melalui 10 pemeriksaan: (1) kelengkapan 600 file (300 JSON + 300 CSV), (2) kelengkapan 30 repetisi per skenario, (3) integritas JSON dan keberadaan metrik wajib, (4) error rate di bawah 1%, (5) deviasi RPS aktual terhadap target, (6) durasi eksperimen mendekati 300 detik, (7) deteksi outlier menggunakan metode IQR 1,5, (8) konten CSV Prometheus, (9) validasi silang sumber data (original vs rerun), dan (10) sanity check statistik deskriptif.

Tahap ketiga, seluruh uji statistik (Shapiro-Wilk, Mann-Whitney U, Cliff's Delta, Kruskal-Wallis) dihitung secara otomatis oleh skrip analisis dan disimpan dalam format CSV di direktori `data/reports/`. Visualisasi statistik dihasilkan menggunakan skrip `generate-figures.py` (matplotlib 3.10). Seluruh skrip tersedia dalam repositori untuk keperluan reproduksi.

---

## 4. Hasil dan Pembahasan

### 4.1 Statistik Deskriptif

Tabel 4 menyajikan ringkasan statistik deskriptif latensi p99 untuk seluruh skenario.

**Tabel 4.** Statistik deskriptif latensi p99 (n = 30 per skenario)

| Kode | Konfigurasi | Median (ms) | 95% CI | Mean (ms) | Std Dev (ms) | CV (%) | RPS Aktual |
|---|---|---|---|---|---|---|---|
| S01 | PBS Baseline 500 | 4,28 | [4,23; 4,33] | 4,27 | 0,10 | 2,4 | 499,8 |
| S02 | ZTA Naif 500 | 4,30 | [4,24; 4,33] | 4,28 | 0,12 | 2,7 | 499,8 |
| S03 | ZTA Cache 500 | 4,22 | [4,15; 4,31] | 4,24 | 0,12 | 2,9 | 499,8 |
| S04 | ZTA Naif 2000 | 16,24 | - | 16,16 | 1,76 | 10,9 | 1999,6 |
| S05 | ZTA Cache 2000 | 16,74 | - | 16,62 | 1,70 | 10,2 | 1999,6 |
| S06 | ZTA Cache 5000 | 407,38 | - | 407,60 | 7,28 | 1,8 | 4185,2 |
| S07 | ZTA Cache Fan-out | 1322,49 | - | 1320,82 | 77,85 | 5,9 | 1725,2 |
| S08 | ZTA Cache Mesh | 499,25 | - | 497,36 | 17,41 | 3,5 | 1478,0 |
| S09 | Revocation Test | 4,25 | - | 4,26 | 0,11 | 2,7 | 499,8 |
| S10 | Static TTL Fan-out | 1317,52 | - | 1323,93 | 69,45 | 5,2 | 1715,5 |

*Catatan: 95% CI dihitung menggunakan percentile bootstrap (B = 10.000, seed = 42). CI hanya dilaporkan untuk skenario S01-S03 yang menjadi objek uji kesetaraan.*

Koefisien variasi (CV) seluruh skenario berada di bawah 11%, menunjukkan reproducibility yang baik antar-repetisi. Error rate tercatat 0,00% pada seluruh skenario kecuali S09 (0,007%, terkait mekanisme revokasi).

Tabel 5 menyajikan data overhead resource pada sidecar Envoy.

**Tabel 5.** Resource overhead sidecar Envoy (n = 30 per skenario)

| Kode | Konfigurasi | CPU Avg (%) | Memory Avg (MB) |
|---|---|---|---|
| S01 | PBS Baseline 500 RPS | 1,79 | 55,90 |
| S02 | ZTA Naif 500 RPS | 1,78 | 55,85 |
| S03 | ZTA Cache 500 RPS | 1,76 | 55,29 |
| S04 | ZTA Naif 2000 RPS | 5,90 | 55,38 |
| S05 | ZTA Cache 2000 RPS | 6,02 | 55,44 |
| S06 | ZTA Cache 5000 RPS | 11,42 | 56,35 |
| S07 | ZTA Cache Fan-out | 10,35 | 61,95 |
| S08 | ZTA Cache Mesh | 8,98 | 61,56 |
| S09 | Revocation Test 500 RPS | 1,76 | 56,03 |
| S10 | Static TTL Fan-out | 11,74 | 66,78 |

### 4.2 Overhead Otorisasi ZTA dan Efektivitas Caching (H1)

Gambar 4 menyajikan distribusi latensi p99 untuk tiga konfigurasi pada 500 RPS.

**Gambar 4.** Boxplot perbandingan konfigurasi pada 500 RPS

![Boxplot perbandingan konfigurasi pada 500 RPS](figures/fig4-config-500rps-boxplot.png)

Sebelum menguji efektivitas caching, terlebih dahulu diverifikasi apakah mekanisme otorisasi ZTA naif menimbulkan overhead yang terdeteksi dibandingkan konfigurasi tanpa otorisasi (PBS baseline). Uji Mann-Whitney U (Persamaan 4) dan Cliff's Delta (Persamaan 5) antara PBS Baseline (S01) dan ZTA Naif (S02) pada 500 RPS menunjukkan hasil berikut:

**Tabel 6a.** Hasil uji Mann-Whitney U: PBS Baseline vs ZTA Naif

| Perbandingan | n | Median A (ms) | Median B (ms) | U | p | δ | Effect |
|---|---|---|---|---|---|---|---|
| PBS vs ZTA Naif @ 500 | 30 vs 30 | 4,28 | 4,30 | 429,0 | 0,762 | -0,05 | Negligible |

Perbedaan median sebesar 0,02 ms antara PBS (4,28 ms) dan ZTA Naif (4,30 ms) tidak signifikan secara statistik (p = 0,762; δ = -0,05, negligible). Temuan ini menunjukkan bahwa pada beban 500 RPS, overhead otorisasi ZTA naif per-panggilan sangat kecil dan tidak terdeteksi pada level latensi end-to-end. Implikasi dari temuan ini adalah bahwa overhead ZTA naif sudah minimal, sehingga ruang perbaikan yang dapat diberikan oleh mekanisme caching juga terbatas pada level latensi E2E.

Selanjutnya, hipotesis H1 menguji apakah mekanisme predictive caching menurunkan latensi p99 dibandingkan konfigurasi ZTA naif. Hasil uji Shapiro-Wilk (Persamaan 3) menunjukkan distribusi normal pada seluruh kelompok data (ZTA Naif 500: W = 0,9707, p = 0,559; ZTA Cache 500: W = 0,9390, p = 0,085). Uji Mann-Whitney U (Persamaan 4) tetap digunakan secara konsisten sebagai uji non-parametrik.

**Tabel 6b.** Hasil uji Mann-Whitney U untuk H1

| Perbandingan | n | Median A (ms) | Median B (ms) | U | p | δ | Effect |
|---|---|---|---|---|---|---|---|
| ZTA Naif vs Cache @ 500 | 30 vs 30 | 4,30 | 4,22 | 564,0 | 0,093 | 0,25 | Small |
| ZTA Naif vs Cache @ 2000 | 30 vs 30 | 16,24 | 16,74 | 392,0 | 0,395 | -0,13 | Negligible |

Pada beban 500 RPS, perbedaan median latensi p99 antara ZTA Naif (4,30 ms) dan ZTA Cache (4,22 ms) tidak signifikan secara statistik (p = 0,093 > 0,05), meskipun effect size tergolong small (δ = 0,25). Pada beban 2000 RPS, hasil serupa diperoleh (p = 0,395; δ = -0,13, negligible).

Gambar 5 menyajikan distribusi perbandingan pada beban 2000 RPS.

**Gambar 5.** Boxplot perbandingan konfigurasi pada 2000 RPS

![Boxplot perbandingan konfigurasi pada 2000 RPS](figures/fig5-config-2000rps-boxplot.png)

Kombinasi temuan Tabel 6a dan 6b menunjukkan konsistensi: overhead otorisasi ZTA per-panggilan sangat kecil (kurang dari 0,1 ms) relatif terhadap latensi end-to-end total, sehingga baik otorisasi naif maupun cached tidak menghasilkan perbedaan yang terdeteksi secara statistik. Perbandingan langsung PBS Baseline vs ZTA Cache disajikan pada Tabel 6c.

**Tabel 6c.** Hasil uji Mann-Whitney U: PBS Baseline vs ZTA Cache

| Perbandingan | n | Median A (ms) | Median B (ms) | U | p | δ | Effect |
|---|---|---|---|---|---|---|---|
| PBS vs ZTA Cache @ 500 | 30 vs 30 | 4,28 | 4,22 | 547,0 | 0,154 | 0,22 | Small |

Hasil uji PBS Baseline vs ZTA Cache juga tidak signifikan (p = 0,154; δ = 0,22, small), mengonfirmasi bahwa penambahan seluruh mekanisme ZTA (otorisasi naif + caching) tidak menghasilkan penalti performa yang terdeteksi secara statistik. Perlu dicatat bahwa ketiga perbandingan di Tabel 6a-6c tidak menerapkan koreksi Bonferroni secara eksplisit; dengan α terkoreksi = 0,0167, seluruh kesimpulan tetap tidak berubah (semua p >> 0,0167). Dengan n = 30 per kelompok dan α = 0,05, uji Mann-Whitney memiliki power yang memadai untuk mendeteksi efek berukuran large (|δ| ≥ 0,474), namun power untuk mendeteksi efek small (|δ| ≈ 0,25) diperkirakan sekitar 0,40, sehingga ketidakmampuan mendeteksi efek kecil bukan berarti efek tersebut tidak ada.

Untuk memverifikasi kesetaraan performa secara positif, dilakukan equivalence testing menggunakan TOST (Two One-Sided Tests) (Schuirmann, 1987) dengan margin kesetaraan Δ = 5% dari median baseline (0,214 ms). Tabel 6d menyajikan hasil uji kesetaraan.

**Tabel 6d.** Hasil uji kesetaraan TOST (Δ = 0,214 ms, α = 0,05)

| Perbandingan | Δ̂ Hodges-Lehmann (ms) | p_TOST | Keputusan |
|---|---|---|---|
| PBS vs ZTA Naif @ 500 | -0,011 | < 0,001 | Setara |
| ZTA Naif vs Cache @ 500 | 0,062 | < 0,001 | Setara |
| PBS vs ZTA Cache @ 500 | 0,042 | < 0,001 | Setara |

Seluruh perbandingan menunjukkan kesetaraan secara statistik (p_TOST < 0,001), dengan estimator Hodges-Lehmann untuk *location shift* yang jauh di bawah margin kesetaraan (Δ̂ < 0,07 ms << Δ = 0,214 ms). Bootstrap 95% CI untuk perbedaan median (PBS − ZTA Cache) adalah [-0,047; 0,158] ms, yang seluruhnya berada dalam batas kesetaraan [−0,214; +0,214] ms. Temuan ini mengonfirmasi bahwa lapisan keamanan ZTA dengan mekanisme predictive caching tidak hanya secara statistik tidak signifikan, tetapi juga **terbukti setara secara praktis** (*practically equivalent*) dengan konfigurasi tanpa otorisasi, dan dapat ditambahkan ke service mesh tanpa penalti performa yang bermakna pada kondisi pengujian ini.

Skala overhead yang ditemukan pada penelitian ini (kurang dari 0,1 ms per-panggilan) jauh lebih kecil dibandingkan dengan pendekatan verifikasi kontinu pada ZTA lain yang dilaporkan dalam literatur. Sebagai perbandingan, mekanisme verifikasi keotentikan pengguna berbasis biometrik perilaku pada web browser melaporkan peningkatan response time dari sekitar 20 ms menjadi mendekati 130 ms pada salah satu layanan yang diuji (Sasada et al., 2024). Perbedaan signifikan ini kemungkinan besar disebabkan oleh perbedaan unit verifikasi: pendekatan berbasis biometrik memerlukan pemrosesan pola perilaku pengguna secara kontinu pada setiap akses, sementara mekanisme predictive caching pada penelitian ini beroperasi pada level otorisasi antar-service dengan lookup cache lokal yang jauh lebih ringan secara komputasional.

### 4.3 Pengujian Hipotesis H2: Latensi Revokasi

Hipotesis kedua menguji apakah latensi revokasi sertifikat memenuhi batas 100 ms sebagaimana direkomendasikan NIST SP 800-207. Tabel 7 menyajikan hasil pengujian S09.

**Tabel 7.** Hasil pengujian latensi revokasi (n = 30)

| Metrik | Nilai |
|---|---|
| Mean latensi p99 | 4,26 ms |
| Median latensi p99 | 4,25 ms |
| Persentil ke-99 dari distribusi p99 | 4,46 ms |
| Batas NIST SP 800-207 | 100 ms |
| Memenuhi batas | Ya (margin 95,54 ms) |
| Revokasi berhasil per run (mean) | 10,7 event |

Gambar 6 memvisualisasikan distribusi latensi revokasi.

**Gambar 6.** Distribusi latensi revokasi

![Distribusi latensi revokasi](figures/fig6-revocation-histogram.png)

Latensi revokasi tercatat 4,46 ms pada persentil ke-99, jauh di bawah batas 100 ms dengan margin 95,54 ms. Hasil ini menunjukkan bahwa mekanisme revokasi berbasis nonce blacklist pada WASM filter berfungsi efektif, di mana token yang direvokasi segera ditolak pada pemeriksaan nonce tanpa memerlukan komunikasi ke PDP terpusat. Temuan ini konsisten dengan prinsip Failure Management Mechanism (FMM) pada arsitektur Zero Trust terdistribusi yang mewajibkan isolasi keputusan usang secara instan sebelum transaksi berikutnya dieksekusi guna meminimalkan jendela paparan risiko (Ma et al., 2025).

### 4.4 Pengujian Hipotesis H3: TTL Adaptif vs Statis

Hipotesis ketiga membandingkan efektivitas TTL adaptif (graph-aware) dengan TTL statis. Pengujian dilakukan dengan membandingkan S07 (graph-aware TTL, graph-analyzer aktif) dan S10 (static TTL, graph-analyzer dinonaktifkan sehingga TTL default = 30 detik konstan) pada topologi fan-out dan beban 2000 RPS.

**Tabel 8.** Hasil perbandingan TTL adaptif vs statis (n = 30 per kelompok)

| Perbandingan | Median S10 (ms) | Median S07 (ms) | U | p | δ | Effect |
|---|---|---|---|---|---|---|
| Static TTL vs Graph-aware TTL | 1317,52 | 1322,49 | 450,0 | 1,000 | 0,00 | Negligible |

Perbandingan sebaran latensi p99 antara konfigurasi TTL statis (S10) dan TTL adaptif (S07) disajikan pada Gambar 7.

**Gambar 7.** Boxplot perbandingan TTL statis vs adaptif

![Boxplot TTL statis vs adaptif](figures/fig7-ttl-comparison-boxplot.png)

Hasil menunjukkan tidak terdapat perbedaan signifikan (U = 450,0; p = 1,000; δ = 0,00) antara TTL adaptif dan TTL statis pada level latensi end-to-end. Kedua distribusi memenuhi asumsi normalitas melalui uji Shapiro-Wilk pada Persamaan (3) (S07: W = 0,9491, p = 0,160; S10: W = 0,9704, p = 0,550). Uji Mann-Whitney U (Persamaan 4) dan Cliff's Delta (Persamaan 5) mengonfirmasi kesetaraan distribusi kedua strategi TTL tersebut.

Perlu dijelaskan bahwa perbandingan ini menggunakan latensi end-to-end sebagai metrik utama, bukan cache hit ratio secara langsung. Hal ini disebabkan oleh arsitektur WASM filter yang beroperasi sebagai local decision engine di dalam proses Envoy: keputusan cache hit atau miss terjadi secara internal tanpa menambahkan header respons yang dapat diobservasi dari sisi klien. Mekanisme otorisasi pada kedua konfigurasi (S07 dan S10) tetap aktif, dengan perbedaan hanya pada cara penentuan TTL (adaptif vs konstan 30 detik). Latensi end-to-end merupakan proxy yang valid karena setiap perbedaan efektivitas caching (misalnya akibat TTL yang lebih tepat) akan tercermin pada frekuensi cache miss dan konsekuensi fallback ke PDP terpusat, yang secara langsung memengaruhi latensi total.

Temuan ini dapat diinterpretasikan dari dua perspektif. Pertama, mekanisme TTL adaptif tidak menambahkan overhead komputasi yang terdeteksi pada jalur kritikal, yang mengonfirmasi bahwa seluruh perhitungan TTL terjadi di luar jalur request (off-path) pada komponen Graph Topology Analyzer. Kedua, pada kondisi beban stabil selama 5 menit, perbedaan antara TTL adaptif dan statis belum cukup terakumulasi untuk menghasilkan efek yang terukur pada latensi end-to-end. Manfaat TTL adaptif diperkirakan lebih terlihat pada skenario dengan perubahan pola traffic yang dinamis dalam durasi yang lebih panjang, di mana TTL statis berpotensi menghasilkan stale decision yang lebih banyak.

### 4.5 Pengaruh Topologi

Analisis pengaruh topologi dilakukan menggunakan uji Kruskal-Wallis pada tiga konfigurasi topologi di beban 2000 RPS. Gambar 8 menunjukkan perbedaan distribusi latensi p99 antar-topologi.

**Gambar 8.** Boxplot perbandingan topologi pada 2000 RPS

![Boxplot perbandingan topologi](figures/fig8-topology-boxplot.png)

**Tabel 9.** Hasil uji Kruskal-Wallis untuk pengaruh topologi

| Topologi | Skenario | Median p99 (ms) | RPS Aktual |
|---|---|---|---|
| Linear | S05 | 16,74 | 1999,6 |
| Mesh | S08 | 499,25 | 1478,0 |
| Fan-out | S07 | 1322,49 | 1725,2 |

Uji Kruskal-Wallis (Persamaan 6) menghasilkan H = 79,12 (p < 0,001), menunjukkan perbedaan signifikan antar-topologi. Post-hoc Mann-Whitney (Persamaan 4) dengan koreksi Bonferroni (alfa = 0,0167) mengonfirmasi perbedaan signifikan pada seluruh pasangan: Linear vs Fan-out (δ = -1,0; large), Linear vs Mesh (δ = -1,0; large), dan Fan-out vs Mesh (δ = 1,0; large).

Pola latensi yang diobservasi (Linear < Mesh < Fan-out) mencerminkan karakteristik inherent dari masing-masing pola panggilan, meskipun perlu dicatat bahwa perbedaan ini juga dipengaruhi oleh variabel pengganggu (*confounding variables*) berupa pola request yang berbeda (single-endpoint, batch, round-robin) dan RPS aktual yang bervariasi (1478-2000 RPS) pada masing-masing topologi. Topologi linear dengan satu endpoint per iterasi menghasilkan latensi terendah karena hanya satu evaluasi otorisasi per request. Topologi mesh mengirimkan satu request per iterasi secara round-robin ke tiga endpoint berbeda, sehingga latensi per-request tetap moderat meskipun melibatkan variasi pasangan otorisasi yang lebih banyak. Topologi fan-out mengirimkan tiga request secara bersamaan (batch), di mana latensi ditentukan oleh response terlambat dalam batch (ceiling effect), sehingga menghasilkan p99 tertinggi.

Perlu dicatat bahwa ketiga konfigurasi non-linear tidak mencapai target 2000 RPS: S07 (fan-out) mencapai 1725 RPS (86,3%), S08 (mesh) mencapai 1478 RPS (73,9%), dan S10 (static TTL fan-out) mencapai 1716 RPS (85,8%). Keterbatasan ini disebabkan oleh saturasi resource klaster pada topologi dengan jumlah pasangan service atau concurrent request yang lebih besar. Hal ini merupakan refleksi kapasitas riil klaster dan bukan merupakan kesalahan konfigurasi, serta tidak mengurangi validitas perbandingan antar-topologi karena perbedaan latensi yang diobservasi (satu hingga dua orde magnitudo) jauh melebihi perbedaan RPS aktual.

### 4.6 Resource Overhead

Uji Kruskal-Wallis (Persamaan 6) pada overhead CPU dan memori di beban 500 RPS menunjukkan tidak ada perbedaan signifikan antara tiga konfigurasi (PBS, ZTA Naif, ZTA Cache):

**Tabel 10.** Hasil uji Kruskal-Wallis untuk resource overhead @ 500 RPS

| Metrik | PBS (S01) | ZTA Naif (S02) | ZTA Cache (S03) | H | p |
|---|---|---|---|---|---|
| CPU (%) | 1,79 | 1,78 | 1,76 | 0,81 | 0,668 |
| Memory (MB) | 55,90 | 55,85 | 55,29 | 2,46 | 0,292 |

Sebaran penggunaan CPU dan memori sidecar Envoy pada ketiga konfigurasi tersebut divisualisasikan melalui boxplot pada Gambar 9, yang menyajikan median dan rentang interkuartil (IQR) melengkapi nilai rata-rata pada Tabel 10.

**Gambar 9.** Resource overhead sidecar Envoy pada 500 RPS

![Resource overhead sidecar](figures/fig9-resource-overhead-boxplot.png)

Hasil uji Kruskal-Wallis tersebut tidak mendeteksi adanya perbedaan yang signifikan secara statistik pada penggunaan CPU maupun memori antar-konfigurasi di beban 500 RPS ($p > 0,05$). Temuan ini mengindikasikan bahwa data empiris belum cukup untuk menolak hipotesis nol kesamaan distribusi beban sumber daya pada kondisi pengujian ini. Namun demikian, ketiadaan perbedaan signifikan ini tidak boleh diinterpretasikan sebagai bukti kesetaraan performa secara definitif, mengingat uji kesetaraan formal (TOST) dalam penelitian ini hanya dievaluasi pada metrik latensi. Secara praktis pada lingkungan uji tiga node yang dievaluasi, operasional WASM filter di dalam proses Envoy yang memanfaatkan shared memory untuk local cache tidak menimbulkan penambahan alokasi memori terpisah yang substansial.

### 4.7 Skalabilitas

Gambar 10 menggambarkan tren latensi p99 terhadap peningkatan beban.

**Gambar 10.** Skalabilitas ZTA Cache: latensi vs beban

![Skalabilitas latensi vs beban](figures/fig10-scalability-line.png)

Perbandingan antara S05 (2000 RPS) dan S06 (5000 RPS) menunjukkan degradasi performa yang signifikan: median p99 meningkat dari 16,74 ms menjadi 407,38 ms (U = 0,0; p < 0,001; δ = -1,0). Degradasi ini disebabkan oleh saturasi resource klaster yang hanya mencapai throughput aktual 4185 RPS dari target 5000 RPS (83,7%). Temuan ini menunjukkan bahwa kapasitas klaster tiga node dengan spesifikasi yang digunakan memiliki batas efektif pada kisaran 4000-5000 RPS total, dan penskalaan horizontal diperlukan untuk beban yang lebih tinggi.

### 4.8 Analisis Skalabilitas Algoritmik

Meskipun eksperimen dilakukan pada 3 service, skalabilitas algoritma untuk $N$ service pada lingkungan produksi dapat dijustifikasi melalui analisis kompleksitas algoritmik setiap komponen.

**Data Plane (WASM Filter): Evaluasi Per-Request Sinkron.** Kompleksitas per-request pada jalur kritikal adalah:

$$T_{request}(N) = T_{hash} + T_{hmac} + T_{nonce} = O(1) \quad \text{...(9)}$$

di mana $T_{hash}$ adalah waktu lookup hash-map cache lokal, $T_{hmac}$ adalah waktu verifikasi HMAC-SHA256, dan $T_{nonce}$ adalah waktu pemeriksaan nonce blacklist. Seluruh operasi bersifat $O(1)$ karena cache lokal per sidecar dibatasi oleh parameter `maxCandidates` = 50 entries, sehingga **tidak tergantung pada $N$**. Data eksperimen mengonfirmasi overhead per-request sebesar ~0,016 ms (selisih median data tak terbulatkan S02 4,295 ms vs S01 4,279 ms), yang akan tetap konstan pada skala produksi.

**Control Plane (Graph Topology Analyzer): Analisis Periodik Asinkron.** Bottleneck utama adalah perhitungan betweenness centrality menggunakan algoritma Brandes:

$$T_{analysis}(V, E) = O(V \cdot E) + O(E \cdot \log E) + O(K) \quad \text{...(10)}$$

di mana $V$ adalah jumlah service (node), $E$ adalah jumlah pasangan service aktif (edge), dan $K = \min(E_{active}, 50)$. Pada arsitektur microservice, setiap service berkomunikasi dengan rata-rata $c$ downstream service ($c \in [2, 5]$), sehingga $E \approx c \cdot V$ dan kompleksitas menjadi $O(c \cdot V^2)$. Perhitungan ini dilakukan secara asinkron setiap 30 detik dan tidak berada pada jalur kritikal request. Tabel 11 menyajikan proyeksi waktu komputasi.

**Tabel 11.** Proyeksi skalabilitas control plane ($c = 3$, $\alpha = 0{,}005$ ms)

| $V$ (service) | $E \approx 3V$ | $T_{analysis}$ (ms) | $< 30$ detik? | Overhead per-request |
|---|---|---|---|---|
| 3 (eksperimen) | 9 | 0,19 | ✅ | 0,016 ms |
| 10 | 30 | 1,79 | ✅ | 0,016 ms |
| 50 | 150 | 39,67 | ✅ | 0,016 ms |
| 100 | 300 | 154,94 | ✅ | 0,016 ms |
| 500 | 1500 | 3.781,65 | ✅ | 0,016 ms |
| 1000 | 3000 | 15.069,30 | ✅ | 0,016 ms |

**Memory per sidecar.** Setiap sidecar menyimpan paling banyak $K$ delegation token:

$$M_{sidecar} = K \times S_{token} \leq 50 \times 400\ \text{B} = 19{,}5\ \text{KB} \quad \text{...(11)}$$

Nilai ini konstan dan independen terhadap $N$. Total memory tambahan klaster pada $N = 1000$ diproyeksikan sebesar $1000 \times 19{,}5\ \text{KB} \approx 19$ MB, yang negligible terhadap kapasitas klaster produksi.

**Bandwidth distribusi token.** Bandwidth gRPC streaming dibatasi oleh `maxCandidates`:

$$BW = \frac{K \times S_{token}}{T_{interval}} \leq \frac{50 \times 400}{30} \approx 667\ \text{B/s} \quad \text{...(12)}$$

Untuk $N \geq 50$, bandwidth konvergen pada ~0,65 KB/s, yang bersifat *negligible* pada jaringan klaster.

Analisis ini menunjukkan bahwa algoritma layak untuk lingkungan produksi hingga $N \leq 1000$ service. Untuk $N > 1000$, partisi graph per-namespace atau algoritma *approximate betweenness centrality* dengan kompleksitas $O(V + E)$ dapat dipertimbangkan (Geisberger et al., 2008).

---

## 5. Simpulan

Penelitian ini telah mengembangkan dan mengevaluasi algoritma predictive authorization caching berbasis graph topology untuk mengurangi overhead latensi pada arsitektur Zero Trust service mesh. Berdasarkan eksperimen komprehensif dengan 10 skenario pengujian pada 30 repetisi, diperoleh temuan-temuan berikut.

Pertama, overhead otorisasi ZTA naif terhadap PBS baseline tidak signifikan secara statistik (U = 429,0; p = 0,762; δ = -0,05), dan mekanisme predictive caching terhadap ZTA naif juga tidak signifikan (U = 564,0; p = 0,093; δ = 0,25) pada beban 500 RPS. Lebih dari itu, uji kesetaraan TOST (Schuirmann, 1987) dengan margin Δ = 5% dari median baseline mengonfirmasi bahwa seluruh perbandingan **terbukti setara secara praktis** (p_TOST < 0,001), dengan estimasi *location shift* Hodges-Lehmann kurang dari 0,07 ms. Bootstrap 95% CI untuk perbedaan median PBS vs ZTA Cache ([-0,047; 0,158] ms) seluruhnya berada dalam batas kesetaraan [−0,214; +0,214] ms. Kedua, latensi revokasi sertifikat tercatat 4,46 ms pada persentil ke-99, memenuhi batas 100 ms yang ditetapkan NIST SP 800-207 dengan margin yang lebar. Ketiga, topologi service mesh berpengaruh signifikan terhadap latensi (H = 79,12; p < 0,001), dengan pola Linear (16,74 ms) < Mesh (499,25 ms) < Fan-out (1322,49 ms). Keempat, overhead CPU dan memori sidecar tidak menunjukkan perbedaan signifikan antara konfigurasi dengan dan tanpa cache (p > 0,05).

Penelitian ini memiliki beberapa keterbatasan. Pertama, eksperimen dilakukan pada klaster tiga node yang belum sepenuhnya merepresentasikan lingkungan produksi berskala besar. Kedua, perbandingan TTL adaptif dan statis dilakukan pada skenario beban konstan selama 5 menit, yang mungkin belum cukup untuk menunjukkan keunggulan TTL adaptif pada kondisi traffic yang sangat dinamis. Ketiga, metrik cache hit ratio tidak dapat diukur secara langsung dari sisi klien karena arsitektur WASM filter yang melakukan evaluasi otorisasi secara lokal di dalam proses Envoy tanpa memancarkan header status cache pada respons HTTP. Keputusan cache hit atau miss hanya tercatat pada log internal sidecar dan tidak terekspor ke Prometheus pada konfigurasi eksperimen ini. Sebagai konsekuensi, evaluasi efektivitas cache menggunakan latensi end-to-end sebagai proxy, yaitu pendekatan yang valid karena setiap cache miss memicu fallback ke PDP terpusat dengan latensi tambahan yang terdeteksi pada level end-to-end. Keempat, skenario fan-out dan mesh menggunakan pola request yang berbeda (batch vs single), yang menjadi confounding variable pada perbandingan topologi. Kelima, testbed yang digunakan merupakan arsitektur single entry-point di mana seluruh endpoint ditangani oleh frontend service secara lokal tanpa panggilan East-West antar-backend service. Konsekuensinya, pengukuran overhead otorisasi (H1, H2) dan resource overhead yang terjadi di level Envoy sidecar tetap valid, namun graph topology yang dianalisis oleh Graph Topology Analyzer bersifat trivial (satu node aktif) sehingga manfaat penuh dari analisis betweenness centrality dan mekanisme TTL adaptif belum dapat didemonstrasikan secara optimal. Perbedaan latensi antar-topologi yang diobservasi pada Kruskal-Wallis (H4) lebih mencerminkan perbedaan pola beban request (jumlah dan konkurensi request per iterasi) daripada efek topologi multi-hop pada mekanisme caching.

Penelitian selanjutnya dapat diarahkan pada: (1) evaluasi pada testbed dengan panggilan East-West antar-service yang sesungguhnya (multi-hop chain) untuk memvalidasi efektivitas betweenness centrality dan TTL adaptif pada graph topology yang non-trivial, (2) evaluasi pada klaster yang lebih besar dengan variasi beban yang dinamis untuk mengukur keunggulan TTL adaptif secara lebih konklusif, (3) instrumentasi cache hit ratio melalui penambahan custom response header pada WASM filter dan custom Prometheus exporter yang mengekspor metrik `zta_cache_hits_total` dan `zta_cache_misses_total` dari sidecar, dan (4) pengembangan mekanisme TTL yang mengintegrasikan betweenness centrality secara langsung dalam formula perhitungan TTL, tidak hanya pada penentuan prioritas caching.

---

## Pernyataan

**Konflik Kepentingan:** Penulis menyatakan tidak terdapat konflik kepentingan dalam penelitian ini.

**Pendanaan:** Penelitian ini tidak menerima pendanaan dari pihak eksternal.

**Ketersediaan Data:** Seluruh data mentah, skrip analisis, dan kode sumber yang digunakan dalam penelitian ini tersedia secara publik pada repositori replikasi: https://github.com/thyosurya/zero-trust-near-zero-cost-predictive-authorization-caching-microservice-graph.

---

## Daftar Pustaka

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

Romano, J., Kromrey, J. D., Coraggio, J., & Skowronek, J. (2006). Appropriate statistics for ordinal level data: Should we really be using t-test and Cohen's d for evaluating group differences on the NSSE and similar surveys? *Annual Meeting of the Florida Association of Institutional Research*, 1–33.

Rose, S., Borchert, O., Mitchell, S., & Connelly, S. (2020). *Zero trust architecture* (NIST SP 800-207). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-207

Samonte, M. J. C., Aparize, J. E. R., Geronimo, J. M., & Oriño, C. C. (2024, September). Implementing zero trust security in microservice architecture of electronic health record. In *2024 4th International Conference on Computer Systems (ICCS)* (pp. 98–105). IEEE. https://doi.org/10.1109/ICCS62594.2024.10795827

Sasada, T., Taenaka, Y., Kadobayashi, Y., & Fall, D. (2024). Web-biometrics for user authenticity verification in zero trust access control. *IEEE Access*, 12, 129611–129622. https://doi.org/10.1109/ACCESS.2024.3413696

Schuirmann, D. J. (1987). A comparison of the two one-sided tests procedure and the power approach for assessing the equivalence of average bioavailability. *Journal of Pharmacokinetics and Biopharmaceutics*, 15(6), 657–680. https://doi.org/10.1007/BF01068419

Shapiro, S. S., & Wilk, M. B. (1965). An analysis of variance test for normality. *Biometrika*, 52(3/4), 591–611. https://doi.org/10.2307/2333709

Verma, S. (2025). Zero Trust Architecture in Cloud-Native Environments: Implementation Strategies & Best Practices. *International Journal of Computer Trends and Technology*, 73(4), 114–122. https://doi.org/10.14445/22312803/IJCTT-V73I4P114

Walpole, R. E., Myers, R. H., Myers, S. L., & Ye, K. (2020). *Probability and statistics for engineers and scientists* (9th ed.). Pearson.

Zhang, Y., Liu, M., Wang, H., Ma, Y., Huang, G., & Liu, X. (2025). Research on WebAssembly runtimes: A survey. ACM Transactions on Software Engineering and Methodology, 34(8), Article 239. https://doi.org/10.1145/3714465