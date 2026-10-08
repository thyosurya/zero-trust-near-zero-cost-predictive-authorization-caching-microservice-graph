package graph

import (
	"testing"
)

// TestComputeBetweenness_LinearChain memverifikasi node tengah dalam chain memiliki
// skor betweenness tertinggi: A → B → C (B adalah hub)
func TestComputeBetweenness_LinearChain(t *testing.T) {
	g := NewTopologyGraph()
	g.RecordCall("A", "B")
	g.RecordCall("B", "C")

	scores := ComputeBetweenness(g)

	// B harus memiliki skor tertinggi (hub antara A dan C)
	if len(scores) == 0 {
		t.Fatal("expected non-empty centrality scores")
	}
	if scores["B"] < scores["A"] || scores["B"] < scores["C"] {
		t.Errorf("expected B to have highest centrality: A=%.2f B=%.2f C=%.2f",
			scores["A"], scores["B"], scores["C"])
	}
}

// TestComputeBetweenness_EmptyGraph memverifikasi graph kosong menghasilkan map kosong
func TestComputeBetweenness_EmptyGraph(t *testing.T) {
	g := NewTopologyGraph()
	scores := ComputeBetweenness(g)
	if len(scores) != 0 {
		t.Errorf("expected empty scores, got %d entries", len(scores))
	}
}

// TestComputeBetweenness_SingleEdge memverifikasi graph satu edge menghasilkan skor 0
func TestComputeBetweenness_SingleEdge(t *testing.T) {
	g := NewTopologyGraph()
	g.RecordCall("X", "Y")
	scores := ComputeBetweenness(g)
	// Dengan hanya 2 node, betweenness harus 0 untuk keduanya
	for node, score := range scores {
		if score != 0.0 {
			t.Errorf("expected 0 betweenness for %s with single edge, got %.2f", node, score)
		}
	}
}

// TestComputeBetweenness_Normalized memverifikasi skor dinormalisasi ke 0.0-1.0
func TestComputeBetweenness_Normalized(t *testing.T) {
	g := NewTopologyGraph()
	g.RecordCall("A", "B")
	g.RecordCall("B", "C")
	g.RecordCall("C", "D")
	g.RecordCall("A", "C")

	scores := ComputeBetweenness(g)
	for node, score := range scores {
		if score < 0.0 || score > 1.0 {
			t.Errorf("score for %s out of range [0,1]: %.4f", node, score)
		}
	}
}

// TestRankEdgesByImportance memverifikasi edge diurutkan descending berdasarkan skor gabungan
func TestRankEdgesByImportance(t *testing.T) {
	g := NewTopologyGraph()
	// Edge dengan call count berbeda
	for i := 0; i < 50; i++ {
		g.RecordCall("hot-source", "hot-target")
	}
	for i := 0; i < 5; i++ {
		g.RecordCall("cold-source", "cold-target")
	}

	centrality := map[string]float64{
		"hot-source":  0.9,
		"cold-source": 0.1,
	}

	ranked := RankEdgesByImportance(g, centrality)

	if len(ranked) != 2 {
		t.Fatalf("expected 2 ranked edges, got %d", len(ranked))
	}
	// Hot edge harus di posisi pertama
	if ranked[0].Source != "hot-source" {
		t.Errorf("expected hot-source first, got %s", ranked[0].Source)
	}
}

// TestRankEdgesByImportance_EmptyGraph memverifikasi graph kosong menghasilkan slice kosong
func TestRankEdgesByImportance_EmptyGraph(t *testing.T) {
	g := NewTopologyGraph()
	ranked := RankEdgesByImportance(g, map[string]float64{})
	if len(ranked) != 0 {
		t.Errorf("expected empty result, got %d edges", len(ranked))
	}
}

// TestRankEdgesByImportance_Formula memverifikasi formula 0.7*calls + 0.3*centrality
func TestRankEdgesByImportance_Formula(t *testing.T) {
	g := NewTopologyGraph()
	// Edge A: banyak call, rendah centrality
	for i := 0; i < 100; i++ {
		g.RecordCall("A", "B")
	}
	// Edge C: sedikit call, tinggi centrality
	for i := 0; i < 10; i++ {
		g.RecordCall("C", "D")
	}

	centrality := map[string]float64{
		"A": 0.1, // rendah
		"C": 1.0, // tinggi
	}

	ranked := RankEdgesByImportance(g, centrality)

	if len(ranked) < 2 {
		t.Fatalf("expected at least 2 edges, got %d", len(ranked))
	}
	// Edge A harus menang karena 0.7*1.0 + 0.3*0.1 = 0.73 > 0.7*0.1 + 0.3*1.0 = 0.37
	if ranked[0].Source != "A" {
		t.Errorf("expected A first (high call weight dominates), got %s", ranked[0].Source)
	}
}

// TestRankEdgesByImportance_AfterReset memverifikasi Reset membersihkan graph sehingga tidak ada edge
func TestRankEdgesByImportance_AfterReset(t *testing.T) {
	g := NewTopologyGraph()
	g.RecordCall("A", "B")

	// Reset menghapus semua edge dan node
	g.Reset()

	ranked := RankEdgesByImportance(g, map[string]float64{"A": 0.5})
	if len(ranked) != 0 {
		t.Errorf("expected empty after reset, got %d", len(ranked))
	}
}
