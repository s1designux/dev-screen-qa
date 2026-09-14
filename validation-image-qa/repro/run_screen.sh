#!/bin/bash
# 화면 하나를 통째로 돌린다: 검수기 → 로컬 AI 읽기 → 어긋난 것 세기.
# 사용: ./run_screen.sh <이름> <디자인PNG> <개발PNG> [FORCE_TY]
#   예) ./run_screen.sh route design_route_1920x1080.png dev_route_1920x1080.png 99
# FORCE_TY를 주면 겹치기를 그 값으로 고정한다(자동 겹치기가 실패하는 화면의 계측용).
set -e
NAME=$1; DESIGN=$2; DEV=$3; FTY=$4
UI=../../engine/ui.html
EL=elements_${NAME}.json
[ -f "$EL" ] || { echo "요소 목록이 없습니다: $EL"; exit 1; }

echo "① 검수기 — 겹치기·자 재기"
if [ -n "$FTY" ]; then
  FORCE_TX=0 FORCE_TY=$FTY ELEMENTS_JSON=$EL DESIGN_PNG=$DESIGN DEV_PNG=$DEV DESIGN_MAX=4096 \
    node run.js $UI $NAME 2>/dev/null | grep -E "^model|^notices" | head -2
else
  ELEMENTS_JSON=$EL DESIGN_PNG=$DESIGN DEV_PNG=$DEV DESIGN_MAX=4096 \
    node run.js $UI $NAME 2>/dev/null | grep -E "^model|^notices" | head -2
fi

echo
echo "② 읽을 구역과 예상 시간 (AI 안 부름)"
python3 vlm_read.py --elements $EL --dev $DEV --align ${NAME}.json --out vlm_read_${NAME}.json --dry-run | head -3

echo
echo "③ 로컬 AI 읽기 — 백그라운드로 시작"
nohup python3 -u vlm_read.py --elements $EL --dev $DEV --align ${NAME}.json \
      --out vlm_read_${NAME}.json > vlm_read_${NAME}.log 2>&1 &
echo "   진행: tail -f vlm_read_${NAME}.log"
echo
echo "④ 끝나면 이걸 돌리세요:"
echo "   python3 rule_gap.py --engine ${NAME}.json --read vlm_read_${NAME}.json --elements $EL --out gap_${NAME}.json"
