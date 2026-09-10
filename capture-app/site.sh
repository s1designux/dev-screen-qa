#!/bin/bash
# 촬영 준비 사이트를 연다 →  http://127.0.0.1:8767
set -euo pipefail
cd "$(dirname "$0")"
exec python3 site/server.py
