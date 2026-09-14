#!/bin/bash
# 로그인할 때 저절로 켜지는 것을 거둔다.
cd "$(dirname "$0")" || exit 1
bash scripts/mac-autostart-off.sh
rc=$?
echo
read -n 1 -s -r -p "아무 키나 누르면 창이 닫힙니다"
exit $rc
