// Performance budget for the backend, run with k6 against a LOCAL server only.
//
//   python perf/stub_server.py                      # backend with the model provider stubbed
//   k6 run perf/k6-health-analyze.js                # BASE_URL defaults to http://127.0.0.1:8000
//
// Three scenarios at a fixed arrival rate for 30 s each, in parallel:
//   health   GET /health    20 requests/s   liveness, what uptime pings hit
//   ready    GET /ready     10 requests/s   readiness: provider configured, model files present
//   analyze  POST /analyze/  5 requests/s   a typed question through prompt building, the
//                                           (stubbed) model call, the guard and the response
// The budget (k6 exits non-zero if it is missed): p95 under 300 ms for /health and /ready,
// under 1 s for /analyze/ with the stub, and under 1% failed requests overall. These are
// for a laptop; the stub removes the model's own time (seconds), which no budget here covers.
//
// The script refuses any host but localhost: never point load at the live API.
import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const host = BASE_URL.replace(/^https?:\/\//, '').split(/[/:]/)[0];
if (!['127.0.0.1', 'localhost', '[::1]'].includes(host)) {
	throw new Error(`BASE_URL must be a local server (got ${BASE_URL}); never load-test the live API`);
}

const rate = (name, perSecond, exec) => ({
	[name]: {
		executor: 'constant-arrival-rate',
		rate: perSecond,
		timeUnit: '1s',
		duration: __ENV.DURATION || '30s',
		preAllocatedVUs: 10,
		maxVUs: 50,
		exec,
	},
});

export const options = {
	scenarios: {
		...rate('health', 20, 'health'),
		...rate('ready', 10, 'ready'),
		...rate('analyze', 5, 'analyze'),
	},
	thresholds: {
		http_req_failed: ['rate<0.01'],
		'http_req_duration{scenario:health}': ['p(95)<300'],
		'http_req_duration{scenario:ready}': ['p(95)<300'],
		'http_req_duration{scenario:analyze}': ['p(95)<1000'],
		checks: ['rate>0.99'],
	},
	summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export function health() {
	const r = http.get(`${BASE_URL}/health`);
	check(r, { 'health 200': (res) => res.status === 200 });
}

export function ready() {
	const r = http.get(`${BASE_URL}/ready`);
	check(r, { 'ready 200': (res) => res.status === 200 });
}

export function analyze() {
	const r = http.post(`${BASE_URL}/analyze/`, {
		question: 'There are black spots on my tomato leaves. What should I do?',
		language: 'en',
	});
	check(r, {
		'analyze 200': (res) => res.status === 200,
		'analyze guarded': (res) => res.status === 200 && res.json('guard.lines_removed') === 1,
	});
}
