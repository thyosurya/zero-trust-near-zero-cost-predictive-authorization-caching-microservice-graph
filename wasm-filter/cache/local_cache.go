// wasm-filter/cache/local_cache.go
package cache

import "sync"

// LocalCache adalah abstraksi untuk operasi baca/tulis/hapus pada cache token lokal.
// Dalam produksi, ini akan membungkus Envoy shared data API (proxywasm.GetSharedData/SetSharedData).
// Implementasi ini menggunakan in-memory map agar logika inti dapat diuji di luar runtime Envoy.
type LocalCache struct {
	mu         sync.RWMutex
	data       map[string][]byte
	maxEntries int
}

// NewLocalCache membuat LocalCache baru dengan batas maksimum entri
func NewLocalCache(maxEntries int) *LocalCache {
	return &LocalCache{
		data:       make(map[string][]byte),
		maxEntries: maxEntries,
	}
}

// Get mengambil data dari cache berdasarkan key.
// Return (data, true) jika ada, (nil, false) jika tidak ada.
// Key format: "source_spiffe_id->target_spiffe_id"
func (c *LocalCache) Get(key string) ([]byte, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	val, ok := c.data[key]
	return val, ok
}

// Set menyimpan data ke cache.
// Return error jika gagal (misal: cache penuh).
func (c *LocalCache) Set(key string, value []byte) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.data[key] = value
	return nil
}

// Delete menghapus entri dari cache.
// Return error jika operasi gagal.
func (c *LocalCache) Delete(key string) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.data, key)
	return nil
}

// MakeKey membuat cache key dari source dan target identity.
// Return: source + "->" + target
// Dipusatkan di sini agar format key konsisten di seluruh codebase.
func (c *LocalCache) MakeKey(source, target string) string {
	return source + "->" + target
}
