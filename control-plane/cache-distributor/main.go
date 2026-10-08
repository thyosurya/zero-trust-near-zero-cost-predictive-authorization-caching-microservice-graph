package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/thyosurya/zta-predictive-cache/control-plane/cache-distributor/metrics"
	pb "github.com/thyosurya/zta-predictive-cache/control-plane/cache-distributor/proto"
	"github.com/thyosurya/zta-predictive-cache/control-plane/cache-distributor/revocation"
	"github.com/thyosurya/zta-predictive-cache/control-plane/cache-distributor/token"
	"google.golang.org/grpc"
)

// DistributorService mengorkestrasi pembuatan token, gRPC server, dan REST API.
// Struct utama sesuai dokumentasi 06_arsitektur_detail_per_file.md.
type DistributorService struct {
	signer      *token.Signer
	revoker     *revocation.Manager
	broadcaster *revocation.Broadcaster
	opaPDPURL   string
	graphURL    string

	mu           sync.RWMutex
	activeTokens map[string]*token.DelegationToken // key: "source->target"
}

// DistributionRequest adalah payload POST /distribute
type DistributionRequest struct {
	Source          string   `json:"source"`
	Target          string   `json:"target"`
	AllowedActions  []string `json:"allowed_actions"`
	SuggestedTTLMs  int64    `json:"suggested_ttl_ms,omitempty"`
	Sensitivity     string   `json:"sensitivity,omitempty"`
}

// RevocationRequestPayload adalah payload POST /revoke
type RevocationRequestPayload struct {
	Source string `json:"source"`
	Target string `json:"target"`
	Reason string `json:"reason"`
}

// CandidateResponse dari graph-analyzer /candidates
type CandidateResponse struct {
	Source          string  `json:"source"`
	Target          string  `json:"target"`
	CallsPerMin     int64   `json:"calls_per_min"`
	SuggestedTTL    int64   `json:"suggested_ttl_ms"`
	Sensitivity     string  `json:"sensitivity"`
	CentralityScore float64 `json:"centrality_score"`
}

// gRPC server implementation
type grpcServer struct {
	pb.UnimplementedCacheDistributorServer
	svc *DistributorService
}

func (s *grpcServer) StreamRevocations(req *pb.SubscribeRequest, stream pb.CacheDistributor_StreamRevocationsServer) error {
	s.svc.broadcaster.Register(req.SidecarId)
	metrics.GrpcStreamCount.Inc()
	defer func() {
		s.svc.broadcaster.Unregister(req.SidecarId)
		metrics.GrpcStreamCount.Dec()
	}()
	<-stream.Context().Done()
	return nil
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
	log.Println("Starting Cache Distributor...")

	// Baca ENV config
	signingKeyB64 := os.Getenv("SIGNING_KEY")
	if signingKeyB64 == "" {
		log.Fatal("SIGNING_KEY environment variable is required")
	}
	signingKey, err := base64.StdEncoding.DecodeString(signingKeyB64)
	if err != nil {
		log.Fatalf("Invalid SIGNING_KEY (must be base64): %v", err)
	}

	signer, err := token.NewSigner(signingKey)
	if err != nil {
		log.Fatalf("Failed to create signer: %v", err)
	}

	graphURL := envOrDefault("GRAPH_ANALYZER_URL", "http://graph-analyzer:8080")
	opaPDPURL := envOrDefault("OPA_URL", "http://opa-service:8181")
	grpcPort := envOrDefault("GRPC_PORT", "50051")
	restPort := envOrDefault("REST_PORT", "8081")
	distributionInterval := envIntOrDefault("DISTRIBUTION_INTERVAL_S", 30)

	svc := &DistributorService{
		signer:       signer,
		revoker:      revocation.NewManager(),
		broadcaster:  revocation.NewBroadcaster(),
		opaPDPURL:    opaPDPURL,
		graphURL:     graphURL,
		activeTokens: make(map[string]*token.DelegationToken),
	}

	// Metrics endpoint (port 2112)
	go func() {
		mux := http.NewServeMux()
		mux.Handle("/metrics", promhttp.Handler())
		log.Println("Metrics listening on :2112")
		http.ListenAndServe(":2112", mux)
	}()

	// gRPC Server
	go func() {
		lis, err := net.Listen("tcp", ":"+grpcPort)
		if err != nil {
			log.Fatalf("failed to listen on %s: %v", grpcPort, err)
		}
		s := grpc.NewServer()
		pb.RegisterCacheDistributorServer(s, &grpcServer{svc: svc})
		log.Printf("gRPC Server listening on :%s", grpcPort)
		s.Serve(lis)
	}()

	// Background goroutine: distributeLoop
	go svc.distributeLoop(time.Duration(distributionInterval) * time.Second)

	// Background goroutine: pruneBlacklist setiap 2 menit
	go func() {
		ticker := time.NewTicker(2 * time.Minute)
		defer ticker.Stop()
		for range ticker.C {
			svc.revoker.PruneBlacklist(2 * time.Minute)
		}
	}()

	// Background goroutine: expired token cleanup setiap 10 detik
	go svc.expiredTokenCleanup()

	// REST API
	mux := svc.routes()

	log.Printf("Cache Distributor API listening on :%s", restPort)
	log.Fatal(http.ListenAndServe(":"+restPort, mux))
}

func (svc *DistributorService) routes() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/distribute", svc.handleDistribute)
	mux.HandleFunc("/revoke", svc.handleRevoke)
	mux.HandleFunc("/tokens/active", svc.handleActiveTokens)
	mux.HandleFunc("/health", svc.handleHealth)
	return mux
}

// POST /distribute — menerima kandidat dan membuat delegation token
func (svc *DistributorService) handleDistribute(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var reqs []DistributionRequest
	if err := json.NewDecoder(r.Body).Decode(&reqs); err != nil {
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	var created int
	for _, req := range reqs {
		nonce, err := token.GenerateNonce()
		if err != nil {
			continue
		}

		// Register nonce di revocation manager
		svc.revoker.RegisterNonce(req.Source, req.Target, nonce)

		// TTL dari request atau default 30s
		ttl := 30 * time.Second
		if req.SuggestedTTLMs > 0 {
			ttl = time.Duration(req.SuggestedTTLMs) * time.Millisecond
		}

		// Sensitivity dari request atau default "medium"
		sensitivity := "medium"
		if req.Sensitivity != "" {
			sensitivity = req.Sensitivity
		}

		// Buat delegation token
		tok, err := token.NewDelegationToken(
			req.Source, req.Target,
			req.AllowedActions,
			sensitivity,
			ttl,
			nonce,
		)
		if err != nil {
			continue
		}

		// Sign token
		payload, _ := tok.ToJSON()
		sig, _ := svc.signer.Sign(payload)

		// Simpan di active tokens
		svc.mu.Lock()
		key := req.Source + "->" + req.Target
		svc.activeTokens[key] = tok
		svc.mu.Unlock()

		// Record metrics
		metrics.TokensIssuedTotal.Inc()
		metrics.TokensActive.Set(float64(len(svc.activeTokens)))
		metrics.TokenTTL.WithLabelValues(req.Source, req.Target).Observe(float64(tok.CacheTTLMs))

		_ = sig // signature digunakan saat push ke sidecar via gRPC
		created++
	}

	w.WriteHeader(http.StatusAccepted)
	json.NewEncoder(w).Encode(map[string]int{"tokens_created": created})
}

// POST /revoke — mencabut token untuk pasangan service
func (svc *DistributorService) handleRevoke(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req RevocationRequestPayload
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		log.Printf("ERROR: JSON decode failed: %v", err)
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	start := time.Now()
	newNonce, err := svc.revoker.Revoke(req.Source, req.Target)
	if err != nil {
		http.Error(w, fmt.Sprintf("Revocation failed: %v", err), http.StatusNotFound)
		return
	}

	// Broadcast ke semua sidecar
	svc.broadcaster.Broadcast(req.Source, req.Target, newNonce)

	// Hapus dari active tokens
	svc.mu.Lock()
	delete(svc.activeTokens, req.Source+"->"+req.Target)
	metrics.TokensActive.Set(float64(len(svc.activeTokens)))
	svc.mu.Unlock()

	// Record revocation metrics
	elapsed := float64(time.Since(start).Milliseconds())
	metrics.RevocationLatency.Observe(elapsed)
	metrics.RevocationEventsTotal.WithLabelValues(req.Reason).Inc()

	w.WriteHeader(http.StatusAccepted)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"revoked":   true,
		"new_nonce": newNonce,
	})
}

// GET /tokens/active — mengembalikan daftar token aktif
func (svc *DistributorService) handleActiveTokens(w http.ResponseWriter, r *http.Request) {
	svc.mu.RLock()
	defer svc.mu.RUnlock()

	type activeToken struct {
		Source    string `json:"source"`
		Target   string `json:"target"`
		ExpiresAt int64 `json:"expires_at"`
		TTLMs    int64  `json:"ttl_ms"`
	}

	var tokens []activeToken
	for _, tok := range svc.activeTokens {
		tokens = append(tokens, activeToken{
			Source:    tok.SourceIdentity,
			Target:   tok.TargetIdentity,
			ExpiresAt: tok.ExpiresAt,
			TTLMs:    tok.CacheTTLMs,
		})
	}

	if tokens == nil {
		tokens = []activeToken{}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(tokens)
}

// GET /health — health check
func (svc *DistributorService) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":            "ok",
		"connected_sidecars": svc.broadcaster.ConnectedCount(),
		"active_tokens":     len(svc.activeTokens),
	})
}

// distributeLoop — query graph-analyzer setiap interval, buat token untuk kandidat
func (svc *DistributorService) distributeLoop(interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	client := &http.Client{Timeout: 5 * time.Second}

	for range ticker.C {
		// 1. Query graph-analyzer /candidates
		resp, err := client.Get(svc.graphURL + "/candidates")
		if err != nil {
			log.Printf("distributeLoop: failed to query graph-analyzer: %v", err)
			continue
		}

		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		var candidates []CandidateResponse
		if err := json.Unmarshal(body, &candidates); err != nil {
			log.Printf("distributeLoop: failed to parse candidates: %v", err)
			continue
		}

		// 2. Untuk tiap kandidat: buat token
		for _, c := range candidates {
			nonce, err := token.GenerateNonce()
			if err != nil {
				continue
			}

			svc.revoker.RegisterNonce(c.Source, c.Target, nonce)

			ttl := time.Duration(c.SuggestedTTL) * time.Millisecond
			if ttl <= 0 {
				ttl = 30 * time.Second
			}

			// Gunakan sensitivity dari graph-analyzer, default "medium"
			sensitivity := c.Sensitivity
			if sensitivity == "" {
				sensitivity = "medium"
			}

			// Query OPA untuk allowed actions per pasangan
			actions := svc.queryAllowedActions(client, c.Source, c.Target)
			if len(actions) == 0 {
				actions = []string{"GET", "POST"} // fallback
			}

			tok, err := token.NewDelegationToken(
				c.Source, c.Target,
				actions,
				sensitivity,
				ttl,
				nonce,
			)
			if err != nil {
				continue
			}

			payload, _ := tok.ToJSON()
			_, _ = svc.signer.Sign(payload)

			svc.mu.Lock()
			svc.activeTokens[c.Source+"->"+c.Target] = tok
			svc.mu.Unlock()

			metrics.TokensIssuedTotal.Inc()
			metrics.TokenTTL.WithLabelValues(c.Source, c.Target).Observe(float64(tok.CacheTTLMs))
		}

		svc.mu.RLock()
		metrics.TokensActive.Set(float64(len(svc.activeTokens)))
		svc.mu.RUnlock()

		if len(candidates) > 0 {
			log.Printf("distributeLoop: processed %d candidates, %d active tokens", len(candidates), len(svc.activeTokens))
		}
	}
}

// queryAllowedActions queries OPA untuk mendapat allowed actions per pasangan service.
// Fallback: return nil jika OPA tidak terjangkau.
func (svc *DistributorService) queryAllowedActions(client *http.Client, source, target string) []string {
	reqBody := fmt.Sprintf(`{"input":{"source_identity":"%s","target_identity":"%s","action":"*"}}`, source, target)
	resp, err := client.Post(svc.opaPDPURL+"/v1/data/service_rules", "application/json", strings.NewReader(reqBody))
	if err != nil {
		return nil
	}
	defer resp.Body.Close()

	var result struct {
		Result []struct {
			AllowedActions []string `json:"allowed_actions"`
		} `json:"result"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil
	}

	// Cari rule yang cocok
	for _, rule := range result.Result {
		if len(rule.AllowedActions) > 0 {
			return rule.AllowedActions
		}
	}
	return nil
}

// expiredTokenCleanup menghapus token yang sudah expired dari activeTokens.
// Dijalankan sebagai goroutine setiap 10 detik.
func (svc *DistributorService) expiredTokenCleanup() {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()
	for range ticker.C {
		now := time.Now().Unix()
		svc.mu.Lock()
		for k, tok := range svc.activeTokens {
			if tok.ExpiresAt < now {
				delete(svc.activeTokens, k)
				metrics.TokensExpiredTotal.Inc()
			}
		}
		metrics.TokensActive.Set(float64(len(svc.activeTokens)))
		svc.mu.Unlock()
	}
}
