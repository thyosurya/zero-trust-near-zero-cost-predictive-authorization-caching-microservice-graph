// wasm-filter/cache/local_cache_test.go
package cache

import (
	"bytes"
	"testing"
)

// TestNewLocalCache memverifikasi inisialisasi cache kosong
func TestNewLocalCache(t *testing.T) {
	c := NewLocalCache(100)
	if c == nil {
		t.Fatal("NewLocalCache() returned nil")
	}
}

// TestSetAndGet memverifikasi data yang disimpan dapat diambil kembali
func TestSetAndGet(t *testing.T) {
	c := NewLocalCache(100)
	value := []byte(`{"allowed_actions":["GET"],"exp":9999999999}`)
	c.Set("service-a->service-b", value)

	got, ok := c.Get("service-a->service-b")
	if !ok {
		t.Fatal("expected key to exist")
	}
	if !bytes.Equal(got, value) {
		t.Errorf("expected %s, got %s", value, got)
	}
}

// TestGet_Miss memverifikasi key yang tidak ada mengembalikan false
func TestGet_Miss(t *testing.T) {
	c := NewLocalCache(100)
	_, ok := c.Get("nonexistent")
	if ok {
		t.Error("expected miss for nonexistent key")
	}
}

// TestDelete memverifikasi entri yang dihapus tidak bisa diambil lagi
func TestDelete(t *testing.T) {
	c := NewLocalCache(100)
	c.Set("key", []byte("value"))
	c.Delete("key")

	_, ok := c.Get("key")
	if ok {
		t.Error("expected key to be deleted")
	}
}

// TestMakeKey memverifikasi format key konsisten
func TestMakeKey(t *testing.T) {
	c := NewLocalCache(100)
	key := c.MakeKey("service-a", "service-b")
	expected := "service-a->service-b"
	if key != expected {
		t.Errorf("expected %q, got %q", expected, key)
	}
}
