#!/bin/bash
# 실행 버튼 — 이름표 한 장을 골라 실행하면 사진이 shots/ 에 쌓인다.
#   ./run.sh apps/galaxy-settings.yaml
set -euo pipefail
cd "$(dirname "$0")"
exec python3 lib/runner.py "$@"
