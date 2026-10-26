#!/usr/bin/env bash
set -euo pipefail

repo=$(git rev-parse --show-toplevel)
cd "$repo"

if [[ $(git branch --show-current) != "codex/geo-ai-start" ]]; then
  echo "ERROR: verification is allowed only on codex/geo-ai-start" >&2
  exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
  echo "ERROR: .venv/bin/python is missing" >&2
  exit 1
fi

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
stamp=$(date -u +%Y%m%dT%H%M%SZ)

.venv/bin/python -m pip check

regression_out="/home/geoai/dev-data/geoai-004/harness-verify-$stamp"
mkdir -p "$regression_out"
GEOAI_TEST_REPORT_ROOT=/home/geoai/dev-data/geoai-004 \
timeout 180s .venv/bin/python -I -B tests/geoai_bootstrap.py \
  --output-dir "$regression_out"

if [[ -f tests/geoai_api_bootstrap.py && -f tests/test_api.py ]]; then
  api_out="/home/geoai/dev-data/geoai-007/harness-verify-$stamp"
  mkdir -p "$api_out"
  GEOAI_TEST_REPORT_ROOT=/home/geoai/dev-data/geoai-007 \
  timeout 180s .venv/bin/python -I -B tests/geoai_api_bootstrap.py \
    --output-dir "$api_out"
fi

git diff --check
