// wasm-filter/token/validator_test.go
package token

import (
    "testing"
    "time"
)

// TestValidate_ValidToken memverifikasi token valid melewati semua pemeriksaan
func TestValidate_ValidToken(t *testing.T) {
    v := NewValidator("valid-nonce-registry")
    tok := &CachedToken{
        AllowedActions:  []string{"GET", "POST"},
        ExpiresAt:       time.Now().Add(30 * time.Second).Unix(),
        RevocationNonce: "valid-nonce",
    }
    v.RegisterNonce("valid-nonce")

    result := v.Validate(tok, "GET")
    if result != DecisionAllow {
        t.Errorf("expected Allow, got %v", result)
    }
}

// TestValidate_ExpiredToken memverifikasi token kedaluwarsa ditolak
func TestValidate_ExpiredToken(t *testing.T) {
    v := NewValidator("")
    tok := &CachedToken{
        AllowedActions:  []string{"GET"},
        ExpiresAt:       time.Now().Add(-1 * time.Second).Unix(), // sudah expired
        RevocationNonce: "nonce-abc",
    }
    v.RegisterNonce("nonce-abc")

    result := v.Validate(tok, "GET")
    if result != DecisionExpired {
        t.Errorf("expected Expired, got %v", result)
    }
}

// TestValidate_RevokedNonce memverifikasi nonce yang dicabut menghasilkan Deny
func TestValidate_RevokedNonce(t *testing.T) {
    v := NewValidator("")
    tok := &CachedToken{
        AllowedActions:  []string{"GET"},
        ExpiresAt:       time.Now().Add(30 * time.Second).Unix(),
        RevocationNonce: "old-nonce", // nonce ini tidak terdaftar = sudah dicabut
    }
    // Tidak register nonce — simulasi setelah revokasi

    result := v.Validate(tok, "GET")
    if result != DecisionRevoked {
        t.Errorf("expected Revoked, got %v", result)
    }
}

// TestValidate_DisallowedAction memverifikasi action di luar allowed_actions ditolak
func TestValidate_DisallowedAction(t *testing.T) {
    v := NewValidator("")
    tok := &CachedToken{
        AllowedActions:  []string{"GET"},           // hanya GET
        ExpiresAt:       time.Now().Add(30 * time.Second).Unix(),
        RevocationNonce: "nonce-ok",
    }
    v.RegisterNonce("nonce-ok")

    result := v.Validate(tok, "DELETE")             // coba DELETE
    if result != DecisionDeny {
        t.Errorf("expected Deny for disallowed action, got %v", result)
    }
}

// TestValidate_MultipleActions memverifikasi semua action yang diizinkan diterima
func TestValidate_MultipleActions(t *testing.T) {
    v := NewValidator("")
    tok := &CachedToken{
        AllowedActions:  []string{"GET", "POST", "PUT"},
        ExpiresAt:       time.Now().Add(30 * time.Second).Unix(),
        RevocationNonce: "nonce-multi",
    }
    v.RegisterNonce("nonce-multi")

    for _, action := range []string{"GET", "POST", "PUT"} {
        result := v.Validate(tok, action)
        if result != DecisionAllow {
            t.Errorf("expected Allow for action %s, got %v", action, result)
        }
    }
}
