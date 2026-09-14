#!/bin/bash
# 맥을 켜고 로그인하면 검수 포털과 촬영 준비 사이트가 저절로 켜지게 한다.
cd "$(dirname "$0")" || exit 1
bash scripts/mac-autostart-on.sh "$(pwd)"
rc=$?
echo
read -n 1 -s -r -p "아무 키나 누르면 창이 닫힙니다"
exit $rc
