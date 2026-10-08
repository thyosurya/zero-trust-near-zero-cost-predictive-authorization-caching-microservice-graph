// wasm-filter/main.go
// Entry point Envoy WASM filter.
// Menginisialisasi plugin dan menghubungkan Envoy HTTP lifecycle
// (OnHttpRequestHeaders) ke DecisionEngine.
//
// Batasan:
// - Tidak boleh mengandung logika otorisasi
// - Tidak boleh mengandung logika cache
// - Hanya boleh mendelegasikan ke authz/decision.go
// - Harus menggunakan proxy-wasm-go-sdk API
package main

import (
	"github.com/tetratelabs/proxy-wasm-go-sdk/proxywasm"
	"github.com/tetratelabs/proxy-wasm-go-sdk/proxywasm/types"

	"github.com/thyosurya/zta-predictive-cache/wasm-filter/authz"
	localcache "github.com/thyosurya/zta-predictive-cache/wasm-filter/cache"
)

func main() {
	proxywasm.SetVMContext(&vmContext{})
}

type vmContext struct {
	types.DefaultVMContext
}

func (*vmContext) OnVMStart(vmConfigurationSize int) types.OnVMStartStatus {
	proxywasm.LogInfo("ZTA Authorization Cache WASM filter loaded")
	return types.OnVMStartStatusOK
}

func (*vmContext) NewPluginContext(contextID uint32) types.PluginContext {
	return &pluginContext{}
}

type pluginContext struct {
	types.DefaultPluginContext
	engine *authz.DecisionEngine
}

func (p *pluginContext) OnPluginStart(pluginConfigurationSize int) types.OnPluginStartStatus {
	// Baca konfigurasi plugin (PDP URL, dll.)
	// Inisialisasi DecisionEngine
	lc := localcache.NewLocalCache(1000)
	p.engine = authz.NewDecisionEngine(lc, nil) // PDP fallback via ext_authz, not inline
	proxywasm.LogInfo("Plugin initialized with local cache (max 1000 entries)")
	return types.OnPluginStartStatusOK
}

func (p *pluginContext) NewHttpContext(contextID uint32) types.HttpContext {
	return &httpContext{
		contextID: contextID,
		engine:    p.engine,
	}
}

type httpContext struct {
	types.DefaultHttpContext
	contextID uint32
	engine    *authz.DecisionEngine
}

func (ctx *httpContext) OnHttpRequestHeaders(numHeaders int, endOfStream bool) types.Action {
	// Ambil identitas source dari header mTLS (di-set oleh Istio)
	sourceID, _ := proxywasm.GetHttpRequestHeader("x-forwarded-client-cert")
	// Ambil target identity
	targetID, _ := proxywasm.GetHttpRequestHeader(":authority")
	// Ambil method
	method, _ := proxywasm.GetHttpRequestHeader(":method")

	// Delegasikan keputusan ke DecisionEngine
	result := ctx.engine.Decide(sourceID, targetID, method)

	switch result.Decision {
	case authz.Allow:
		proxywasm.LogInfof("Cache hit: authorized %s -> %s [%s]", sourceID, targetID, method)
		return types.ActionContinue

	case authz.Miss:
		// Cache miss — forward ke PDP central via ext_authz
		proxywasm.LogInfof("Cache miss for %s -> %s, forwarding to PDP", sourceID, targetID)
		return types.ActionContinue

	case authz.Expired:
		proxywasm.LogInfof("Token expired for %s -> %s", sourceID, targetID)
		return types.ActionContinue

	case authz.Revoked:
		proxywasm.LogInfof("Token revoked for %s -> %s", sourceID, targetID)
		proxywasm.SendHttpResponse(403, nil, []byte("Forbidden: token revoked"), -1)
		return types.ActionPause

	case authz.Deny:
		proxywasm.LogInfof("Action denied: %s -> %s [%s]", sourceID, targetID, method)
		proxywasm.SendHttpResponse(403, nil, []byte("Forbidden"), -1)
		return types.ActionPause

	default:
		return types.ActionContinue
	}
}
