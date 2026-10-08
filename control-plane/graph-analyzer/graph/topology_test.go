// control-plane/graph-analyzer/graph/topology_test.go
package graph

import (
    "testing"
    "time"
)

// TestNewTopologyGraph memverifikasi inisialisasi graph kosong
func TestNewTopologyGraph(t *testing.T) {
    g := NewTopologyGraph()
    if g == nil {
        t.Fatal("NewTopologyGraph() returned nil")
    }
    if len(g.edges) != 0 {
        t.Errorf("expected 0 edges, got %d", len(g.edges))
    }
}

// TestRecordCall_NewEdge memverifikasi edge baru dibuat saat panggilan pertama
func TestRecordCall_NewEdge(t *testing.T) {
    g := NewTopologyGraph()
    g.RecordCall("service-a", "service-b")

    key := "service-a->service-b"
    edge, exists := g.edges[key]
    if !exists {
        t.Fatalf("expected edge %q to exist", key)
    }
    if edge.CallCount != 1 {
        t.Errorf("expected CallCount=1, got %d", edge.CallCount)
    }
    if edge.Source != "service-a" {
        t.Errorf("expected Source=service-a, got %s", edge.Source)
    }
    if edge.Target != "service-b" {
        t.Errorf("expected Target=service-b, got %s", edge.Target)
    }
}

// TestRecordCall_Increment memverifikasi counter bertambah pada panggilan berulang
func TestRecordCall_Increment(t *testing.T) {
    g := NewTopologyGraph()

    for i := 0; i < 50; i++ {
        g.RecordCall("service-a", "service-b")
    }

    edge := g.edges["service-a->service-b"]
    if edge.CallCount != 50 {
        t.Errorf("expected CallCount=50, got %d", edge.CallCount)
    }
}

// TestRecordCall_DirectionalIsolation memverifikasi A→B dan B→A adalah edge terpisah
func TestRecordCall_DirectionalIsolation(t *testing.T) {
    g := NewTopologyGraph()
    g.RecordCall("service-a", "service-b")
    g.RecordCall("service-b", "service-a")

    if len(g.edges) != 2 {
        t.Errorf("expected 2 separate edges, got %d", len(g.edges))
    }
}

// TestGetHighFrequencyPairs_AboveThreshold memverifikasi hanya edge di atas threshold yang dikembalikan
func TestGetHighFrequencyPairs_AboveThreshold(t *testing.T) {
    g := NewTopologyGraph()

    // Edge dengan frekuensi tinggi
    for i := 0; i < 20; i++ {
        g.RecordCall("service-a", "service-b")
    }

    // Edge dengan frekuensi rendah
    for i := 0; i < 5; i++ {
        g.RecordCall("service-c", "service-d")
    }

    candidates := g.GetHighFrequencyPairs(10)

    if len(candidates) != 1 {
        t.Errorf("expected 1 candidate, got %d", len(candidates))
    }
    if candidates[0].Source != "service-a" || candidates[0].Target != "service-b" {
        t.Errorf("unexpected candidate: %+v", candidates[0])
    }
}

// TestGetHighFrequencyPairs_StaleEdgeExcluded memverifikasi edge lama (>1 menit) dikecualikan
func TestGetHighFrequencyPairs_StaleEdgeExcluded(t *testing.T) {
    g := NewTopologyGraph()
    g.RecordCall("service-a", "service-b")

    // Manipulasi LastSeen ke masa lalu
    edge := g.edges["service-a->service-b"]
    edge.CallCount = 100
    edge.LastSeen = time.Now().Add(-2 * time.Minute) // sudah stale

    candidates := g.GetHighFrequencyPairs(10)
    if len(candidates) != 0 {
        t.Errorf("expected 0 candidates (stale), got %d", len(candidates))
    }
}

// TestGetHighFrequencyPairs_Empty memverifikasi graph kosong mengembalikan slice kosong
func TestGetHighFrequencyPairs_Empty(t *testing.T) {
    g := NewTopologyGraph()
    candidates := g.GetHighFrequencyPairs(10)
    if candidates != nil && len(candidates) != 0 {
        t.Errorf("expected empty result, got %v", candidates)
    }
}

// TestRecordCall_Concurrent memverifikasi thread-safety saat concurrent writes
func TestRecordCall_Concurrent(t *testing.T) {
    g := NewTopologyGraph()
    done := make(chan struct{})

    for i := 0; i < 100; i++ {
        go func() {
            g.RecordCall("service-a", "service-b")
            done <- struct{}{}
        }()
    }

    for i := 0; i < 100; i++ {
        <-done
    }

    edge := g.edges["service-a->service-b"]
    if edge.CallCount != 100 {
        t.Errorf("concurrent writes: expected 100, got %d", edge.CallCount)
    }
}
