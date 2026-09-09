#!/bin/zsh
# 이 작업 폴더의 별도 시험 DB로만 실행한다.
set -eu
QA_PREVIEW_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
export QA_PORTAL_DB="$QA_PREVIEW_DIR/mvp0-intake-preview.db"
export QA_PORTAL_UPLOADS="$QA_PREVIEW_DIR/uploads"
export QA_PORTAL_PORT=8771
export PYTHONDONTWRITEBYTECODE=1
if [[ ! -f "$QA_PORTAL_DB" ]]; then
  print '이 PC의 시험용 데이터가 없습니다. capture-intake-implementation.md의 실행 안내를 확인해 주세요.'
  exit 1
fi
print '화면 목록: http://127.0.0.1:8771/'
python3 "$QA_PREVIEW_DIR/portal.py"
