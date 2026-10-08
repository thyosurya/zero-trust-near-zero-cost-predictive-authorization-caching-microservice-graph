package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/thyosurya/zta-predictive-cache/control-plane/graph-analyzer/cache"
	"github.com/thyosurya/zta-predictive-cache/control-plane/graph-analyzer/graph"
	"github.com/thyosurya/zta-predictive-cache/control-plane/graph-analyzer/metrics"
)

func newTestService() *AnalyzerService {
	return &AnalyzerService{
		topology:   graph.NewTopologyGraph(),
		selector:   cache.NewCandidateSelector(1, 50),
		metrics:    metrics.NewCollector(),
		adminToken: "test-admin-token",
	}
}

// TestHandleRecordCall memverifikasi POST /record mencatat panggilan
func TestHandleRecordCall(t *testing.T) {
	svc := newTestService()
	body := `{"source":"A","target":"B"}`
	req := httptest.NewRequest(http.MethodPost, "/record", strings.NewReader(body))
	w := httptest.NewRecorder()
	svc.handleRecordCall(w, req)

	if w.Code != http.StatusAccepted {
		t.Errorf("expected 202, got %d", w.Code)
	}
}

// TestHandleRecordCall_MethodNotAllowed memverifikasi GET /record ditolak
func TestHandleRecordCall_MethodNotAllowed(t *testing.T) {
	svc := newTestService()
	req := httptest.NewRequest(http.MethodGet, "/record", nil)
	w := httptest.NewRecorder()
	svc.handleRecordCall(w, req)

	if w.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected 405, got %d", w.Code)
	}
}

// TestHandleGetCandidates memverifikasi GET /candidates mengembalikan array
func TestHandleGetCandidates(t *testing.T) {
	svc := newTestService()
	req := httptest.NewRequest(http.MethodGet, "/candidates", nil)
	w := httptest.NewRecorder()
	svc.handleGetCandidates(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}
	var result []CacheCandidateResponse
	json.NewDecoder(w.Body).Decode(&result)
	if result == nil {
		t.Error("expected non-nil array response")
	}
}

// TestHandleHealth memverifikasi GET /health mengembalikan status ok
func TestHandleHealth(t *testing.T) {
	svc := newTestService()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	w := httptest.NewRecorder()
	svc.handleHealth(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}
}

// TestHandleReset_WithValidToken memverifikasi DELETE /graph/reset berhasil dengan token valid
func TestHandleReset_WithValidToken(t *testing.T) {
	svc := newTestService()
	// Tambah data dulu
	svc.topology.RecordCall("A", "B")

	req := httptest.NewRequest(http.MethodDelete, "/graph/reset", nil)
	req.Header.Set("X-Admin-Token", "test-admin-token")
	w := httptest.NewRecorder()
	svc.handleReset(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}
}

// TestHandleReset_Unauthorized memverifikasi DELETE /graph/reset ditolak tanpa token
func TestHandleReset_Unauthorized(t *testing.T) {
	svc := newTestService()
	req := httptest.NewRequest(http.MethodDelete, "/graph/reset", nil)
	req.Header.Set("X-Admin-Token", "wrong-token")
	w := httptest.NewRecorder()
	svc.handleReset(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", w.Code)
	}
}

// TestHandleGetGraph memverifikasi GET /graph mengembalikan snapshot
func TestHandleGetGraph(t *testing.T) {
	svc := newTestService()
	svc.topology.RecordCall("X", "Y")

	req := httptest.NewRequest(http.MethodGet, "/graph", nil)
	w := httptest.NewRecorder()
	svc.handleGetGraph(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}
}
