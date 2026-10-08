// control-plane/cache-distributor/revocation/broadcaster.go
package revocation

import (
	"fmt"
	"log"
	"sync"
)

// RevocationEvent merepresentasikan event revokasi yang dikirim ke sidecar
type RevocationEvent struct {
	SourceIdentity string
	TargetIdentity string
	NewNonce       string
	Timestamp      int64
}

// StreamClient merepresentasikan koneksi stream ke satu sidecar
type StreamClient struct {
	sidecarID string
	eventCh   chan *RevocationEvent
	done      chan struct{}
}

// Broadcaster mengelola koneksi ke semua sidecar dan mem-push RevocationEvent
type Broadcaster struct {
	mu      sync.RWMutex
	clients map[string]*StreamClient // sidecarID → stream
}

// NewBroadcaster membuat Broadcaster baru
func NewBroadcaster() *Broadcaster {
	return &Broadcaster{
		clients: make(map[string]*StreamClient),
	}
}

// Register mendaftarkan koneksi stream baru dari sidecar.
// Jika sidecarID sudah ada, ganti dengan koneksi baru (reconnect).
func (b *Broadcaster) Register(sidecarID string) {
	b.mu.Lock()
	defer b.mu.Unlock()

	// Jika sudah ada, close yang lama
	if old, exists := b.clients[sidecarID]; exists {
		close(old.done)
	}

	b.clients[sidecarID] = &StreamClient{
		sidecarID: sidecarID,
		eventCh:   make(chan *RevocationEvent, 100),
		done:      make(chan struct{}),
	}
	log.Printf("Registered sidecar stream: %s", sidecarID)
}

// Unregister menghapus koneksi saat stream terputus.
func (b *Broadcaster) Unregister(sidecarID string) {
	b.mu.Lock()
	defer b.mu.Unlock()

	if client, exists := b.clients[sidecarID]; exists {
		close(client.done)
		delete(b.clients, sidecarID)
		log.Printf("Unregistered sidecar stream: %s", sidecarID)
	}
}

// Broadcast mengirim event ke SEMUA sidecar yang terdaftar.
// Lanjutkan ke sidecar berikutnya meski satu gagal (best-effort).
// Log sidecar mana yang gagal menerima.
// Return error hanya jika SEMUA gagal.
func (b *Broadcaster) Broadcast(source, target, nonce string) error {
	b.mu.RLock()
	defer b.mu.RUnlock()

	event := &RevocationEvent{
		SourceIdentity: source,
		TargetIdentity: target,
		NewNonce:       nonce,
	}

	if len(b.clients) == 0 {
		log.Printf("Broadcasting revocation for %s -> %s (no connected sidecars)", source, target)
		return nil
	}

	failCount := 0
	for id, client := range b.clients {
		select {
		case client.eventCh <- event:
			log.Printf("Sent revocation to sidecar %s: %s -> %s", id, source, target)
		default:
			log.Printf("Failed to send revocation to sidecar %s (channel full)", id)
			failCount++
		}
	}

	if failCount == len(b.clients) {
		return fmt.Errorf("broadcast failed: all %d sidecars failed to receive", failCount)
	}
	return nil
}

// ConnectedCount return jumlah sidecar yang sedang terkoneksi.
// Digunakan oleh /health endpoint.
func (b *Broadcaster) ConnectedCount() int {
	b.mu.RLock()
	defer b.mu.RUnlock()
	return len(b.clients)
}
