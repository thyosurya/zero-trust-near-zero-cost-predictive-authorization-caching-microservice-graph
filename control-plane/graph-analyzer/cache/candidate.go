// control-plane/graph-analyzer/cache/candidate.go
package cache

import (
	"sort"
	"time"

	"github.com/thyosurya/zta-predictive-cache/control-plane/graph-analyzer/graph"
)

// CacheCandidate merepresentasikan pasangan service yang layak mendapat delegation token
type CacheCandidate struct {
	Source          string
	Target          string
	AllowedActions  []string
	SuggestedTTLMs  int64
	Sensitivity     SensitivityLevel
	CentralityScore float64
	CallsPerMin     int64
}

// CandidateSelector menyeleksi pasangan service untuk cache delegation
type CandidateSelector struct {
	minCallsPerMin int64
	maxCandidates  int
}

// NewCandidateSelector membuat CandidateSelector baru
func NewCandidateSelector(minCallsPerMin int64, maxCandidates int) *CandidateSelector {
	return &CandidateSelector{
		minCallsPerMin: minCallsPerMin,
		maxCandidates:  maxCandidates,
	}
}

// Select menyeleksi kandidat cache dari graph berdasarkan frekuensi dan centrality.
// Alur internal:
//  1. GetHighFrequencyPairs(minCallsPerMin)
//  2. RankEdgesByImportance(centrality)
//  3. Untuk tiap edge teratas: panggil policyFn untuk dapat actions & sensitivity
//  4. CalculateTTL per kandidat
//  5. Return slice CacheCandidate, max maxCandidates entri
//
// policyFn adalah fungsi callback — dipasok dari main.go yang memanggil OPA
// untuk mendapat allowed_actions per pasangan. Ini memisahkan logika policy
// dari logika seleksi.
func (s *CandidateSelector) Select(
	g *graph.TopologyGraph,
	centrality map[string]float64,
	policyFn func(source, target string) ([]string, SensitivityLevel),
) []*CacheCandidate {
	// 1. Ambil edge dengan frekuensi tinggi
	pairs := g.GetHighFrequencyPairs(s.minCallsPerMin)
	if len(pairs) == 0 {
		return nil
	}

	// 2. Rank berdasarkan importance (sudah terurut descending)
	ranked := graph.RankEdgesByImportance(g, centrality)

	// Filter: hanya ambil edge yang ada di high-frequency pairs
	highFreqSet := make(map[string]bool)
	for _, edge := range pairs {
		key := edge.Source + "->" + edge.Target
		highFreqSet[key] = true
	}

	var candidates []*CacheCandidate
	for _, edge := range ranked {
		key := edge.Source + "->" + edge.Target
		if !highFreqSet[key] {
			continue
		}

		// 3. Query policy untuk actions & sensitivity
		actions, sensitivity := policyFn(edge.Source, edge.Target)
		if len(actions) == 0 {
			continue
		}

		// 4. Hitung TTL
		ttl := CalculateTTL(edge.CallCount, sensitivity, 24*time.Hour, 72*time.Hour)

		candidates = append(candidates, &CacheCandidate{
			Source:          edge.Source,
			Target:          edge.Target,
			AllowedActions:  actions,
			SuggestedTTLMs:  ttl.Milliseconds(),
			Sensitivity:     sensitivity,
			CentralityScore: centrality[edge.Source],
			CallsPerMin:     edge.CallCount,
		})

		// 5. Limit ke maxCandidates
		if len(candidates) >= s.maxCandidates {
			break
		}
	}

	// Sort final: descending by CallsPerMin
	sort.Slice(candidates, func(i, j int) bool {
		return candidates[i].CallsPerMin > candidates[j].CallsPerMin
	})

	return candidates
}
