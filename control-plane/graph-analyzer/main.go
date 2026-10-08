package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/thyosurya/zta-predictive-cache/control-plane/graph-analyzer/cache"
	"github.com/thyosurya/zta-predictive-cache/control-plane/graph-analyzer/graph"
	"github.com/thyosurya/zta-predictive-cache/control-plane/graph-analyzer/metrics"
)

// AnalyzerService mengorkestrasi semua sub-paket Graph Analyzer
type AnalyzerService struct {
	topology   *graph.TopologyGraph
	selector   *cache.CandidateSelector
	metrics    *metrics.Collector
	adminToken string
}

// RecordRequest adalah payload POST /record
type RecordRequest struct {
	Source    string `json:"source"`
	Target   string `json:"target"`
	Method   string `json:"method"`
	Timestamp int64 `json:"timestamp"`
}

// CacheCandidateResponse adalah response GET /candidates
type CacheCandidateResponse struct {
	Source          string  `json:"source"`
	Target          string  `json:"target"`
	CallsPerMin     int64   `json:"calls_per_min"`
	SuggestedTTL    int64   `json:"suggested_ttl_ms"`
	Sensitivity     string  `json:"sensitivity"`
	CentralityScore float64 `json:"centrality_score"`
}

func envOrDefault(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}

func envIntOrDefault(key string, defaultVal int) int {
	if val := os.Getenv(key); val != "" {
		if i, err := strconv.Atoi(val); err == nil {
			return i
		}
	}
	return defaultVal
}

func main() {
	log.Println("Starting Graph Analyzer...")

	adminToken := os.Getenv("ADMIN_TOKEN")
	minCallsPerMin := envIntOrDefault("MIN_CALLS_PER_MIN", 10)
	analysisInterval := envIntOrDefault("ANALYSIS_INTERVAL_S", 30)
	port := envOrDefault("PORT", "8080")

	svc := &AnalyzerService{
		topology:   graph.NewTopologyGraph(),
		selector:   cache.NewCandidateSelector(int64(minCallsPerMin), 50),
		metrics:    metrics.NewCollector(),
		adminToken: adminToken,
	}

	// Background goroutine: analysisLoop setiap N detik
	go svc.analysisLoop(time.Duration(analysisInterval) * time.Second)

	// Metrics endpoint
	go func() {
		mux := http.NewServeMux()
		mux.Handle("/metrics", promhttp.Handler())
		log.Println("Metrics listening on :2112")
		http.ListenAndServe(":2112", mux)
	}()

	mux := svc.routes()

	log.Printf("Graph Analyzer API listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}

func (svc *AnalyzerService) routes() *http.ServeMux {
	mux := http.NewServeMux()

	mux.HandleFunc("/record", svc.handleRecordCall)
	mux.HandleFunc("/candidates", svc.handleGetCandidates)
	mux.HandleFunc("/graph", svc.handleGetGraph)
	mux.HandleFunc("/graph/reset", svc.handleReset)
	mux.HandleFunc("/health", svc.handleHealth)

	return mux
}

// POST /record — mencatat panggilan antar service
func (svc *AnalyzerService) handleRecordCall(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req RecordRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	if req.Source == "" || req.Target == "" {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{"error": "source and target are required"})
		return
	}

	svc.topology.RecordCall(req.Source, req.Target)
	svc.metrics.RecordCall(req.Source, req.Target)

	w.WriteHeader(http.StatusAccepted)
	json.NewEncoder(w).Encode(map[string]bool{"recorded": true})
}

// GET /candidates — mengembalikan daftar kandidat cache
func (svc *AnalyzerService) handleGetCandidates(w http.ResponseWriter, r *http.Request) {
	centrality := graph.ComputeBetweenness(svc.topology)

	// Default policyFn — return semua action dengan sensitivity medium
	policyFn := func(source, target string) ([]string, cache.SensitivityLevel) {
		return []string{"GET", "POST", "PUT", "DELETE"}, cache.SensitivityMedium
	}

	candidates := svc.selector.Select(svc.topology, centrality, policyFn)

	var resp []CacheCandidateResponse
	for _, c := range candidates {
		resp = append(resp, CacheCandidateResponse{
			Source:          c.Source,
			Target:          c.Target,
			CallsPerMin:     c.CallsPerMin,
			SuggestedTTL:    c.SuggestedTTLMs,
			CentralityScore: c.CentralityScore,
		})
	}

	if resp == nil {
		resp = []CacheCandidateResponse{}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// GET /graph — mengembalikan snapshot seluruh graph
func (svc *AnalyzerService) handleGetGraph(w http.ResponseWriter, r *http.Request) {
	pairs := svc.topology.GetHighFrequencyPairs(0) // threshold 0 = semua edge
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(pairs)
}

// DELETE /graph/reset — menghapus semua data graph [butuh X-Admin-Token]
func (svc *AnalyzerService) handleReset(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if svc.adminToken != "" {
		token := r.Header.Get("X-Admin-Token")
		if token != svc.adminToken {
			http.Error(w, "Unauthorized", http.StatusUnauthorized)
			return
		}
	}

	svc.topology.Reset()
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]bool{"reset": true})
}

// GET /health — health check
func (svc *AnalyzerService) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"ok"}`))
}

// analysisLoop menjalankan analisis periodik
func (svc *AnalyzerService) analysisLoop(interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for range ticker.C {
		start := time.Now()
		svc.topology.PruneStale(2 * time.Minute)
		elapsed := time.Since(start)
		svc.metrics.ObserveAnalysisDuration(float64(elapsed.Milliseconds()))
	}
}
