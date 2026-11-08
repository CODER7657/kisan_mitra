#!/usr/bin/env bash
# Run the CI checks locally (.github/workflows/backend-tests.yml and gitleaks.yml), for when
# GitHub Actions minutes run out. Stops at the first failing step.
#
#   bash scripts/ci-local.sh              backend, frontend and secret scan
#   bash scripts/ci-local.sh backend      only the backend job (also: frontend, gitleaks)
#
# Backend: uses $PYTHON, else backend/.venv, else python3/python on PATH, with
# backend/requirements-dev.txt installed. Frontend: Node 22 and `npm ci` already run (set
# CI_LOCAL_NPM_CI=1 to run it here). Browser tests use an installed Chrome, as locally.
# gitleaks is skipped with a warning if the binary is not on PATH (or in $GITLEAKS).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STEP=0

step() {
	STEP=$((STEP + 1))
	printf '\n==> [%d] %s\n' "$STEP" "$*"
}

run() {
	step "$*"
	"$@"
}

on_exit() {
	local status=$?
	if [ "$status" -ne 0 ]; then
		printf '\nFAILED at step %d (exit %d)\n' "$STEP" "$status"
	fi
}
trap on_exit EXIT

pick_python() {
	if [ -n "${PYTHON:-}" ]; then
		echo "$PYTHON"
	elif [ -x "$ROOT/backend/.venv/bin/python" ]; then
		echo "$ROOT/backend/.venv/bin/python"
	elif [ -x "$ROOT/backend/.venv/Scripts/python.exe" ]; then
		echo "$ROOT/backend/.venv/Scripts/python.exe"
	elif command -v python3 >/dev/null 2>&1; then
		echo python3
	else
		echo python
	fi
}

backend() {
	cd "$ROOT/backend"
	local py
	py="$(pick_python)"
	step "python: $("$py" --version 2>&1) ($py)"
	run "$py" -m ruff check .
	run "$py" -m ruff format --check .
	run "$py" -m bandit -q -r kisan main.py -lll
	local ignores
	mapfile -t ignores < <(sed -n 's/^\([A-Z][A-Za-z0-9-]*\).*/--ignore-vuln\n\1/p' pip-audit-ignore.txt)
	run "$py" -m pip_audit -r requirements.txt "${ignores[@]}"
	run "$py" -m pytest -q -p no:cacheprovider --cov=kisan --cov-report=term --cov-fail-under=96
}

frontend() {
	cd "$ROOT/frontend"
	# CI has no NODE_ENV. NODE_ENV=development (set by some shells and tools) makes
	# `vite build` keep import.meta.env.DEV true, which bundles the localhost fallback.
	unset NODE_ENV
	if [ "${CI_LOCAL_NPM_CI:-0}" = 1 ]; then
		run npm ci
	fi
	run npm audit --omit=dev --audit-level=high
	run npm run check
	run npm test
	step "build without VITE_API_URL fails"
	if VITE_API_URL='' npm run build >build.log 2>&1; then
		echo "the build succeeded without VITE_API_URL" >&2
		return 1
	fi
	grep -q 'VITE_API_URL is not set' build.log
	rm -f build.log
	step "VITE_API_URL=https://kisan-mitra-api.vercel.app npm run build"
	# The production API: e2e/csp.spec.ts checks that vercel.json's CSP allows it.
	VITE_API_URL=https://kisan-mitra-api.vercel.app npm run build
	step "bundle never calls localhost"
	if grep -rq 'localhost:8000' build; then
		echo "the build calls localhost:8000" >&2
		return 1
	fi
	run npm run test:e2e
}

gitleaks_scan() {
	local bin="${GITLEAKS:-gitleaks}"
	if ! command -v "$bin" >/dev/null 2>&1; then
		step "gitleaks: SKIPPED, binary not found (install it or set GITLEAKS=/path/to/gitleaks)"
		return 0
	fi
	cd "$ROOT"
	run "$bin" git --redact --no-banner --exit-code 1 .
}

targets=("$@")
[ ${#targets[@]} -eq 0 ] && targets=(backend frontend gitleaks)
for t in "${targets[@]}"; do
	case "$t" in
	backend) backend ;;
	frontend) frontend ;;
	gitleaks) gitleaks_scan ;;
	*)
		echo "unknown target: $t (use backend, frontend or gitleaks)" >&2
		exit 2
		;;
	esac
done
printf '\nAll %d steps passed.\n' "$STEP"
