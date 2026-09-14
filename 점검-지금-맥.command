#!/bin/bash
# 이 맥에서 검수기가 돌 준비가 됐는지 본다. 아무것도 고치지 않는다.
cd "$(dirname "$0")"
python3 scripts/check_env.py
echo
read -n 1 -s -r -p "아무 키나 누르면 창이 닫힙니다"
