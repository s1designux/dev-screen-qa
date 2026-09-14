#!/bin/zsh
# 같은 사무실 네트워크의 동료가 들어올 수 있게 검수 포털을 켠다.
cd "$(dirname "$0")/mvp0" || exit 1
export QA_PORTAL_SHARE=1
exec python3 portal.py
