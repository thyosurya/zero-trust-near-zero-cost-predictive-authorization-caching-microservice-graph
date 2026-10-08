// control-plane/graph-analyzer/graph/topology.go
package graph

import (
    "sync"
    "time"

    "gonum.org/v1/gonum/graph/simple"
)

// ServiceEdge merepresentasikan panggilan antar dua service
type ServiceEdge struct {
    Source    string
    Target    string
    CallCount int64
    LastSeen  time.Time
}

// GraphSnapshot adalah salinan seluruh graph untuk endpoint /graph
type GraphSnapshot struct {
    Edges []*ServiceEdge `json:"edges"`
    Nodes []string       `json:"nodes"`
}

// TopologyGraph menyimpan struktur graph service mesh
type TopologyGraph struct {
    mu       sync.RWMutex
    edges    map[string]*ServiceEdge         // key: "source->target"
    graph    *simple.WeightedDirectedGraph
    nodes    map[string]int64               // serviceID -> nodeID
    nextNode int64
}

func NewTopologyGraph() *TopologyGraph {
    return &TopologyGraph{
        edges: make(map[string]*ServiceEdge),
        graph: simple.NewWeightedDirectedGraph(0, 0),
        nodes: make(map[string]int64),
    }
}

// RecordCall mencatat satu panggilan antar service.
// Thread-safe. Dipanggil dari HTTP handler /record.
func (g *TopologyGraph) RecordCall(source, target string) {
    g.mu.Lock()
    defer g.mu.Unlock()

    key := source + "->" + target
    if edge, exists := g.edges[key]; exists {
        edge.CallCount++
        edge.LastSeen = time.Now()
        // Update weight in gonum graph
        if g.graph.HasEdgeFromTo(g.nodeID(source), g.nodeID(target)) {
            g.graph.SetWeightedEdge(simple.WeightedEdge{
                F: simple.Node(g.nodeID(source)),
                T: simple.Node(g.nodeID(target)),
                W: float64(edge.CallCount),
            })
        }
    } else {
        g.edges[key] = &ServiceEdge{
            Source:    source,
            Target:    target,
            CallCount: 1,
            LastSeen:  time.Now(),
        }
        // Add nodes and edge to gonum graph
        srcID := g.ensureNode(source)
        tgtID := g.ensureNode(target)
        g.graph.SetWeightedEdge(simple.WeightedEdge{
            F: simple.Node(srcID),
            T: simple.Node(tgtID),
            W: 1.0,
        })
    }
}

// nodeID returns the gonum node ID for a service, must be called with lock held
func (g *TopologyGraph) nodeID(service string) int64 {
    return g.nodes[service]
}

// ensureNode ensures a node exists in the gonum graph, must be called with lock held
func (g *TopologyGraph) ensureNode(service string) int64 {
    if id, ok := g.nodes[service]; ok {
        return id
    }
    id := g.nextNode
    g.nextNode++
    g.nodes[service] = id
    g.graph.AddNode(simple.Node(id))
    return id
}

// GetHighFrequencyPairs mengembalikan edge dengan CallCount >= threshold
// DAN LastSeen dalam 1 menit terakhir.
// Read-only. Dipanggil oleh CandidateSelector.
func (g *TopologyGraph) GetHighFrequencyPairs(minCallsPerMin int64) []*ServiceEdge {
    g.mu.RLock()
    defer g.mu.RUnlock()

    cutoff := time.Now().Add(-1 * time.Minute)
    var result []*ServiceEdge

    for _, edge := range g.edges {
        if edge.LastSeen.After(cutoff) && edge.CallCount >= minCallsPerMin {
            result = append(result, edge)
        }
    }
    return result
}

// Snapshot mengembalikan salinan seluruh graph untuk endpoint /graph.
// Read-only.
func (g *TopologyGraph) Snapshot() GraphSnapshot {
    g.mu.RLock()
    defer g.mu.RUnlock()

    var edges []*ServiceEdge
    for _, e := range g.edges {
        edges = append(edges, e)
    }

    var nodes []string
    for n := range g.nodes {
        nodes = append(nodes, n)
    }

    return GraphSnapshot{Edges: edges, Nodes: nodes}
}

// Reset menghapus semua edge dan node.
// Dipanggil oleh handler /graph/reset.
// Thread-safe (write lock).
func (g *TopologyGraph) Reset() {
    g.mu.Lock()
    defer g.mu.Unlock()

    g.edges = make(map[string]*ServiceEdge)
    g.graph = simple.NewWeightedDirectedGraph(0, 0)
    g.nodes = make(map[string]int64)
    g.nextNode = 0
}

// PruneStale menghapus edge yang LastSeen lebih lama dari threshold.
// Dipanggil secara periodik oleh analysisLoop di main.go.
func (g *TopologyGraph) PruneStale(olderThan time.Duration) {
    g.mu.Lock()
    defer g.mu.Unlock()

    cutoff := time.Now().Add(-olderThan)
    for key, edge := range g.edges {
        if edge.LastSeen.Before(cutoff) {
            // Remove from gonum graph
            srcID := g.nodes[edge.Source]
            tgtID := g.nodes[edge.Target]
            if g.graph.HasEdgeFromTo(srcID, tgtID) {
                g.graph.RemoveEdge(srcID, tgtID)
            }
            delete(g.edges, key)
        }
    }
}
