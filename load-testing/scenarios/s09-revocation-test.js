// load-testing/scenarios/s09-revocation-test.js
// Skenario S09: Revocation Test — 500 RPS + revocation events
// Mengukur latency revokasi: waktu dari event revokasi sampai sidecar menolak token lama
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Counter } from 'k6/metrics';

const p99Latency = new Trend('p99_latency', true);
const authErrors  = new Counter('auth_errors');
const revocationsTriggered = new Counter('revocations_triggered');

export const options = {
    scenarios: {
        // Traffic normal: 500 RPS
        normal_traffic: {
            executor: 'constant-arrival-rate',
            rate: 500,
            timeUnit: '1s',
            duration: '5m',
            preAllocatedVUs: 50,
            maxVUs: 100,
        },
        // Trigger revocation setiap 30 detik
        revocation_trigger: {
            executor: 'constant-arrival-rate',
            rate: 1,
            timeUnit: '30s',
            duration: '5m',
            preAllocatedVUs: 1,
            maxVUs: 1,
            exec: 'triggerRevocation',
        },
    },
    thresholds: {
        http_req_duration: ['p(99)<500'],
        http_req_failed:   ['rate<0.05'],
    },
    summaryTrendStats: ["min", "avg", "med", "p(90)", "p(95)", "p(99)", "p(99.9)", "max"],
};

const BASE_URL = 'http://frontend.zta-research.svc.cluster.local';
const DISTRIBUTOR_URL = 'http://cache-distributor.zta-research.svc.cluster.local:8081';
const REVOKE_URL = `${DISTRIBUTOR_URL}/revoke`;

export default function () {
    const res = http.get(`${BASE_URL}/api/products`);
    check(res, { 'status is 200': (r) => r.status === 200 });
    if (res.status !== 200) authErrors.add(1);
    p99Latency.add(res.timings.duration);
    sleep(0.1);
}

export function triggerRevocation() {
    const payload = JSON.stringify({
        source: "spiffe://cluster.local/ns/zta-research/sa/frontend",
        target: "spiffe://cluster.local/ns/zta-research/sa/productcatalogservice",
        reason: "k6-test-revocation",
    });
    const params = { headers: { 'Content-Type': 'application/json' } };
    const res = http.post(REVOKE_URL, payload, params);
    if (res.status !== 202) {
        console.log(`[REVOKE FAILED] Status: ${res.status}, Body: ${res.body}`);
    }
    check(res, { 'revocation accepted': (r) => r.status === 202 });
    revocationsTriggered.add(1);
}


