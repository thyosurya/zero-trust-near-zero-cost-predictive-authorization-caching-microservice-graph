// control-plane/graph-analyzer/graph/centrality.go
package graph

import (
	"sort"

	"gonum.org/v1/gonum/graph/network"
)

// ComputeBetweenness menghitung betweenness centrality semua node.
// Return: map[SPIFFE_ID]skor (0.0–1.0, sudah dinormalisasi).
// Menggunakan gonum/graph/network.Betweenness().
// Kompleksitas: O(VE) — acceptable untuk graph kecil (< 50 service).
func ComputeBetweenness(g *TopologyGraph) map[string]float64 {
	g.mu.RLock()
	defer g.mu.RUnlock()

	// Hitung betweenness centrality menggunakan gonum
	rawScores := network.Betweenness(g.graph)

	// Konversi nodeID → serviceID dan normalisasi
	scores := make(map[string]float64)
	maxScore := 0.0

	// Buat reverse map nodeID → serviceID
	reverseMap := make(map[int64]string)
	for serviceID, nodeID := range g.nodes {
		reverseMap[nodeID] = serviceID
	}

	for nodeID, score := range rawScores {
		if serviceID, ok := reverseMap[nodeID]; ok {
			scores[serviceID] = score
			if score > maxScore {
				maxScore = score
			}
		}
	}

	// Normalisasi ke 0.0–1.0
	if maxScore > 0 {
		for k := range scores {
			scores[k] /= maxScore
		}
	}

	return scores
}

// RankEdgesByImportance mengurutkan edge berdasarkan gabungan: CallCount + centrality sumber.
// Formula: score = 0.7 * normalized_call_count + 0.3 * centrality[source]
// Return: slice ServiceEdge terurut descending.
func RankEdgesByImportance(g *TopologyGraph, centrality map[string]float64) []*ServiceEdge {
	g.mu.RLock()
	defer g.mu.RUnlock()

	// Cari max call count untuk normalisasi
	var maxCalls int64
	for _, edge := range g.edges {
		if edge.CallCount > maxCalls {
			maxCalls = edge.CallCount
		}
	}

	// Buat slice dengan skor gabungan
	type scoredEdge struct {
		edge  *ServiceEdge
		score float64
	}

	var scored []scoredEdge
	for _, edge := range g.edges {
		normalizedCalls := 0.0
		if maxCalls > 0 {
			normalizedCalls = float64(edge.CallCount) / float64(maxCalls)
		}
		centralityScore := centrality[edge.Source]
		combined := 0.7*normalizedCalls + 0.3*centralityScore

		scored = append(scored, scoredEdge{edge: edge, score: combined})
	}

	// Sort descending
	sort.Slice(scored, func(i, j int) bool {
		return scored[i].score > scored[j].score
	})

	result := make([]*ServiceEdge, len(scored))
	for i, s := range scored {
		result[i] = s.edge
	}
	return result
}
