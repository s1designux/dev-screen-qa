#!/bin/zsh
# 화면 14개(기존 10 + 세로로 긴 홈 4)를 한 엔진으로 돌린다. 쓰기: ./잰다.sh <붙일이름> [ui.html]
P=$1; UI=${2:-../../engine/ui.html}
run(){ ELEMENTS_JSON=$2 DESIGN_PNG=$3 DEV_PNG=$4 FORCE_TY=$5 DESIGN_MAX=4096 node run.js $UI $1 > /dev/null 2>&1; }
run ${P}_board   elements_board.json        design_board_1920x1898.png  dev_board_1920x1816.png  ""
run ${P}_vehicle elements_vehicle.json      design_vehicle_720x1560.png dev_vehicle_360x780.png  ""
run ${P}_dash    elements_dash.json         design_dash_360x1071.png    dev_dash_360x1031.png    ""
run ${P}_door    elements_door.json         design_door_186x400.png     dev_door_196x436.png     ""
run ${P}_stay    elements_stay_full.json    design_stay_1920x1080.png   dev_stay_1920x1081.png   ""
run ${P}_findid  elements.json              design_1920x1080.png        dev_1920x934.png         ""
run ${P}_login   elements_login.json        design_login_1920x1080.png  dev_login_1920x934.png   ""
run ${P}_table   elements_table.json        design_table_1200x700.png   dev_table_1200x700.png   ""
run ${P}_codes   elements_codes.json        design_codes_1200x760.png   dev_codes_1200x760.png   ""
run ${P}_route   elements_route_plugin.json design_route_1920x1080.png  dev_route_1920x1080.png  99
run ${P}_home1   home1_elements.json        design_home1_1920x1938.png  dev_home1_1920x1730.png  ""
run ${P}_home2   home2_elements.json        design_home2_1920x1080.png  dev_home2_1920x1730.png  ""
run ${P}_home3   home3_elements.json        design_home3_1920x1495.png  dev_home3_1920x1730.png  ""
run ${P}_home4   home4_elements.json        design_home4_1920x1080.png  dev_home4_1920x1730.png  ""
