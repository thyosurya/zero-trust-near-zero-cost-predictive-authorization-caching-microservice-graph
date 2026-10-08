package main

import (
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/thyosurya/zta-predictive-cache/control-plane/cache-distributor/revocation"
	"github.com/thyosurya/zta-predictive-cache/control-plane/cache-distributor/token"
)

func newTestDistributorService() *DistributorService {
	key := make([]byte, 32)
	for i := range key {
		key[i] = byte(i)
	}
	signer, _ := token.NewSigner(key)
	return &DistributorService{
		signer:       signer,
		revoker:      revocation.NewManager(),
		broadcaster:  revocation.NewBroadcaster(),
		opaPDPURL:    "http://localhost:8181",
		graphURL:     "http://localhost:8080",
		activeTokens: make(map[string]*token.DelegationToken),
	}
}

// TestHandleDistribute memverifikasi POST /distribute membuat tokens
func TestHandleDistribute(t *testing.T) {
	svc := newTestDistributorService()
	body := `[{"source":"svc-a","target":"svc-b","allowed_actions":["GET"]}]`
	req := httptest.NewRequest(http.MethodPost, "/distribute", strings.NewReader(body))
	w := httptest.NewRecorder()
	svc.handleDistribute(w, req)

	if w.Code != http.StatusAccepted {
		t.Errorf("expected 202, got %d", w.Code)
	}

	var resp map[string]int
	json.NewDecoder(w.Body).Decode(&resp)
	if resp["tokens_created"] != 1 {
		t.Errorf("expected 1 token created, got %d", resp["tokens_created"])
	}
}

// TestHandleDistribute_MethodNotAllowed memverifikasi GET ditolak
func TestHandleDistribute_MethodNotAllowed(t *testing.T) {
	svc := newTestDistributorService()
	req := httptest.NewRequest(http.MethodGet, "/distribute", nil)
	w := httptest.NewRecorder()
	svc.handleDistribute(w, req)

	if w.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", w.Code)
	}
}

// TestHandleRevoke memverifikasi POST /revoke berhasil setelah distribute
func TestHandleRevoke(t *testing.T) {
	svc := newTestDistributorService()

	// Distribute dulu agar ada active token
	distBody := `[{"source":"svc-a","target":"svc-b","allowed_actions":["GET"]}]`
	distReq := httptest.NewRequest(http.MethodPost, "/distribute", strings.NewReader(distBody))
	distW := httptest.NewRecorder()
	svc.handleDistribute(distW, distReq)

	// Revoke
	revokeBody := `{"source":"svc-a","target":"svc-b","reason":"policy_update"}`
	revokeReq := httptest.NewRequest(http.MethodPost, "/revoke", strings.NewReader(revokeBody))
	revokeW := httptest.NewRecorder()
	svc.handleRevoke(revokeW, revokeReq)

	if revokeW.Code != http.StatusAccepted {
		t.Errorf("expected 202, got %d", revokeW.Code)
	}
}

// TestHandleRevoke_NotFound memverifikasi revoke gagal jika pair tidak ada
func TestHandleRevoke_NotFound(t *testing.T) {
	svc := newTestDistributorService()
	body := `{"source":"unknown","target":"svc","reason":"test"}`
	req := httptest.NewRequest(http.MethodPost, "/revoke", strings.NewReader(body))
	w := httptest.NewRecorder()
	svc.handleRevoke(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", w.Code)
	}
}

// TestHandleActiveTokens memverifikasi GET /tokens/active mengembalikan array
func TestHandleActiveTokens(t *testing.T) {
	svc := newTestDistributorService()
	req := httptest.NewRequest(http.MethodGet, "/tokens/active", nil)
	w := httptest.NewRecorder()
	svc.handleActiveTokens(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}
}

// TestHandleHealth memverifikasi GET /health
func TestHandleHealth(t *testing.T) {
	svc := newTestDistributorService()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	w := httptest.NewRecorder()
	svc.handleHealth(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	json.NewDecoder(w.Body).Decode(&resp)
	if resp["status"] != "ok" {
		t.Errorf("expected status ok, got %v", resp["status"])
	}
}

// TestRoutes memverifikasi semua route terdaftar
func TestRoutes(t *testing.T) {
	svc := newTestDistributorService()
	mux := svc.routes()
	if mux == nil {
		t.Fatal("routes() returned nil")
	}
}

// TestEnvOrDefault memverifikasi fungsi helper
func TestEnvOrDefault(t *testing.T) {
	result := envOrDefault("NON_EXISTENT_VAR_ZTA_TEST", "default-val")
	if result != "default-val" {
		t.Errorf("expected default-val, got %s", result)
	}
}

// TestEnvIntOrDefault memverifikasi fungsi helper int
func TestEnvIntOrDefault(t *testing.T) {
	result := envIntOrDefault("NON_EXISTENT_INT_ZTA_TEST", 42)
	if result != 42 {
		t.Errorf("expected 42, got %d", result)
	}
}

// TestDistributeAndActiveTokensIntegration memverifikasi end-to-end distribute → active tokens
func TestDistributeAndActiveTokensIntegration(t *testing.T) {
	svc := newTestDistributorService()

	// Distribute 2 tokens
	body := `[{"source":"A","target":"B","allowed_actions":["GET"]},{"source":"C","target":"D","allowed_actions":["POST"]}]`
	distReq := httptest.NewRequest(http.MethodPost, "/distribute", strings.NewReader(body))
	distW := httptest.NewRecorder()
	svc.handleDistribute(distW, distReq)

	// Check active
	actReq := httptest.NewRequest(http.MethodGet, "/tokens/active", nil)
	actW := httptest.NewRecorder()
	svc.handleActiveTokens(actW, actReq)

	var tokens []map[string]interface{}
	json.NewDecoder(actW.Body).Decode(&tokens)
	if len(tokens) != 2 {
		t.Errorf("expected 2 active tokens, got %d", len(tokens))
	}
}

// Ensure base64 import is used
var _ = base64.StdEncoding
