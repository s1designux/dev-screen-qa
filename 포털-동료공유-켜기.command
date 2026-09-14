#!/bin/zsh
# 같은 사무실 네트워크의 동료가 들어올 수 있게 검수 포털과 촬영 준비 사이트를 함께 켠다.
# 이 창을 닫으면 둘 다 꺼진다.
뿌리="$(dirname "$0")"

# 촬영 준비 사이트 (8767) — 이미 켜져 있으면 또 켜지 않는다.
if lsof -nP -iTCP:8767 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "촬영 준비 사이트는 이미 켜져 있습니다."
else
  ( cd "$뿌리/capture-app" && QA_CAPTURE_BIND=0.0.0.0 python3 site/server.py ) &
  촬영=$!
  trap 'kill $촬영 2>/dev/null' EXIT INT TERM
fi

# 검수 포털 (8765)
cd "$뿌리/mvp0" || exit 1
export QA_PORTAL_SHARE=1
python3 portal.py
