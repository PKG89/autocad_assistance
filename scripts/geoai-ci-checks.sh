#!/usr/bin/env bash
set -euo pipefail

repo=$(git rev-parse --show-toplevel)
cd "$repo"
repo=$(pwd -P)

python_bin=${GEOAI_PYTHON:-python}
report_root=${GEOAI_TEST_REPORT_ROOT:-}
if [[ -z "$report_root" ]]; then
  report_root=$(mktemp -d "${TMPDIR:-/tmp}/geoai-ci.XXXXXX")
else
  if [[ "$report_root" != /* ]]; then
    echo "ERROR: report root must be absolute" >&2
    exit 1
  fi
  report_root=$(realpath -m "$report_root")
  case "$report_root" in
    "$repo"|"$repo"/*)
      echo "ERROR: report root must be outside the checkout" >&2
      exit 1
      ;;
  esac
  mkdir -p "$report_root"
fi
report_root=$(cd "$report_root" && pwd -P)
case "$report_root" in
  "$repo"|"$repo"/*)
    echo "ERROR: report root must be outside the checkout" >&2
    exit 1
    ;;
esac
export GEOAI_TEST_REPORT_ROOT="$report_root"
mkdir -p "$report_root"/{home,tmp,data,cache}
export HOME="$report_root/home"
export TMPDIR="$report_root/tmp"
export XDG_CACHE_HOME="$report_root/cache"
export DATA_DIR="$report_root/data"
export DB_PATH="$report_root/data/test.sqlite3"
export BOT_TOKEN=""
export ADMIN_IDS=""
export PROJ_NETWORK=OFF
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

"$python_bin" -m pip check

mapfile -t focused < <(find tests -maxdepth 1 -type f -name 'test_*.py' \
  ! -name test_regressions.py ! -name test_api.py -printf '%f\n' | sort)
if (( ${#focused[@]} == 0 )); then
  echo "ERROR: no focused test files discovered" >&2
  exit 1
fi
for file in "${focused[@]}"; do
  echo "FOCUSED: $file"
  "$python_bin" -B -m unittest discover -s tests -p "$file" -v
done

regression_out=$(mktemp -d "$report_root/regression.XXXXXX")
"$python_bin" -I -B tests/geoai_bootstrap.py --output-dir "$regression_out"

api_out=$(mktemp -d "$report_root/api.XXXXXX")
"$python_bin" -I -B tests/geoai_api_bootstrap.py --output-dir "$api_out"

echo "GEO AI focused, isolated regression and API checks passed"
