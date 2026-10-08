// control-plane/graph-analyzer/cache/ttl.go
package cache

import "time"

// SensitivityLevel menentukan seberapa ketat TTL dikurangi
type SensitivityLevel int

const (
    SensitivityLow    SensitivityLevel = iota // penalty 0%
    SensitivityMedium                         // penalty 30%
    SensitivityHigh                           // penalty 70%
)

const (
    BaseTTL = 30 * time.Second
    MaxTTL  = 60 * time.Second
    MinTTL  = 5 * time.Second
)

// CalculateTTL menghitung TTL optimal untuk delegation token
// berdasarkan frekuensi panggilan, sensitivitas data, dan validitas sertifikat
func CalculateTTL(
    callsPerMin    int64,
    sensitivity    SensitivityLevel,
    certRemaining  time.Duration,
    certTotal      time.Duration,
) time.Duration {

    // freq_weight: makin tinggi frekuensi, makin panjang TTL (max 1.0)
    freqWeight := float64(callsPerMin) / 100.0
    if freqWeight > 1.0 {
        freqWeight = 1.0
    }

    // sensitivity_penalty: data sensitif dapat TTL lebih pendek
    var sensitivityPenalty float64
    switch sensitivity {
    case SensitivityLow:
        sensitivityPenalty = 0.0
    case SensitivityMedium:
        sensitivityPenalty = 0.3
    case SensitivityHigh:
        sensitivityPenalty = 0.7
    }

    // cert_validity_factor: TTL tidak boleh melebihi sisa validitas sertifikat
    certFactor := float64(certRemaining) / float64(certTotal)
    if certFactor > 1.0 {
        certFactor = 1.0
    }

    ttl := float64(BaseTTL) * freqWeight * (1 - sensitivityPenalty) * certFactor

    result := time.Duration(ttl)
    if result > MaxTTL {
        result = MaxTTL
    }
    if result < MinTTL {
        result = MinTTL
    }
    return result
}

// SensitivityFromString konversi string "low"/"medium"/"high" → SensitivityLevel.
// Return SensitivityMedium jika tidak dikenal (safe default).
func SensitivityFromString(s string) SensitivityLevel {
    switch s {
    case "low":
        return SensitivityLow
    case "medium":
        return SensitivityMedium
    case "high":
        return SensitivityHigh
    default:
        return SensitivityMedium
    }
}
