// wasm-filter/authz/mock_test.go
package authz

import (
	"encoding/json"
	"sync"
	"time"

	"github.com/thyosurya/zta-predictive-cache/wasm-filter/token"
)

// MockLocalCache adalah mock sederhana untuk Cache interface
// yang digunakan oleh decision_test.go
type MockLocalCache struct {
	mu   sync.RWMutex
	data map[string][]byte
}

func NewMockLocalCache() *MockLocalCache {
	return &MockLocalCache{
		data: make(map[string][]byte),
	}
}

func (c *MockLocalCache) Get(key string) ([]byte, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	val, ok := c.data[key]
	return val, ok
}

func (c *MockLocalCache) Set(key string, value []byte) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.data[key] = value
	return nil
}

func (c *MockLocalCache) Delete(key string) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.data, key)
	return nil
}

// MockPDP adalah mock untuk PDPClient interface
type MockPDP struct {
	allow  bool
	called bool
}

func NewMockPDP(allow bool) *MockPDP {
	return &MockPDP{allow: allow}
}

func (p *MockPDP) Evaluate(source, target, action string) bool {
	p.called = true
	return p.allow
}

func (p *MockPDP) WasCalled() bool {
	return p.called
}

// validTokenJSON menghasilkan JSON token yang valid (belum expired, action GET diizinkan)
// Juga mendaftarkan nonce ke engine validator agar validasi lolos
func validTokenJSON() []byte {
	tok := token.CachedToken{
		AllowedActions:  []string{"GET", "POST"},
		ExpiresAt:       time.Now().Add(30 * time.Second).Unix(),
		RevocationNonce: "valid-nonce",
	}
	data, _ := json.Marshal(tok)
	return data
}

// expiredTokenJSON menghasilkan JSON token yang sudah expired
func expiredTokenJSON() []byte {
	tok := token.CachedToken{
		AllowedActions:  []string{"GET"},
		ExpiresAt:       time.Now().Add(-1 * time.Second).Unix(),
		RevocationNonce: "expired-nonce",
	}
	data, _ := json.Marshal(tok)
	return data
}
