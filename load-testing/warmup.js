// load-testing/warmup.js
import http from "k6/http";
import { sleep } from "k6";

export const options = {
    vus: 10,
    duration: "30s",
    thresholds: {},  // Tidak ada threshold saat warmup
};

export default function () {
    http.get("http://frontend.zta-research.svc.cluster.local/api/products");
    sleep(0.5);
}
