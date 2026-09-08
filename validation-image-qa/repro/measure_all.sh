#!/bin/bash
# 화면 10개를 한 번에 잰다. 사용: ./measure_all.sh <ui.html 경로> <결과 접두사>
# 한 번에 한 세션만: MEASURING.lock 이 있으면 기다린다.
UI=$1; P=$2
[ -n "$UI" ] && [ -n "$P" ] || { echo "사용: ./measure_all.sh <ui.html> <접두사>"; exit 1; }
while [ -f MEASURING.lock ]; do echo "다른 세션이 재는 중… 30초 대기"; sleep 30; done
touch MEASURING.lock; trap 'rm -f MEASURING.lock' EXIT
run(){ local name=$1 el=$2 d=$3 v=$4 fty=$5
  if [ -n "$fty" ]; then FORCE_TX=0 FORCE_TY=$fty ELEMENTS_JSON=$el DESIGN_PNG=$d DEV_PNG=$v DESIGN_MAX=4096 node run.js "$UI" ${P}_$name >/dev/null 2>${P}_$name.err || echo "FAIL $name (${P}_$name.err)"
  else ELEMENTS_JSON=$el DESIGN_PNG=$d DEV_PNG=$v DESIGN_MAX=4096 node run.js "$UI" ${P}_$name >/dev/null 2>${P}_$name.err || echo "FAIL $name (${P}_$name.err)"; fi
  echo "done $name"; }
run board   elements_board.json        design_board_1920x1898.png   dev_board_1920x1816.png
run vehicle elements_vehicle.json      design_vehicle_720x1560.png  dev_vehicle_360x780.png
run dash    elements_dash.json         design_dash_360x1071.png     dev_dash_360x1031.png
run door    elements_door.json         design_door_186x400.png      dev_door_196x436.png
run stay    elements_stay_full.json    design_stay_1920x1080.png    dev_stay_1920x1081.png
run findid  elements.json              design_1920x1080.png         dev_1920x934.png
run login   elements_login.json        design_login_1920x1080.png   dev_login_1920x934.png
run table   elements_table.json        design_table_1200x700.png    dev_table_1200x700.png
run codes   elements_codes.json        design_codes_1200x760.png    dev_codes_1200x760.png
run route   elements_route_plugin.json design_route_1920x1080.png   dev_route_1920x1080.png 99
