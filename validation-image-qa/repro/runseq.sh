#!/bin/zsh
UI=$1; P=$2
cd /Users/designgroup_02/dev-screen-qa-color/validation-image-qa/repro
r(){ pkill -f "headless=new" 2>/dev/null; sleep 1; ELEMENTS_JSON=$2 DESIGN_PNG=$3 DEV_PNG=$4 DESIGN_MAX=4096 node run.js "$UI" "${P}_$1" >/dev/null 2>&1 || echo "FAIL $1"; }
r board   elements_board.json     design_board_1920x1898.png  dev_board_1920x1816.png
r vehicle elements_vehicle.json   design_vehicle_720x1560.png dev_vehicle_360x780.png
r dash    elements_dash.json      design_dash_360x1071.png    dev_dash_360x1031.png
r door    elements_door.json      design_door_186x400.png     dev_door_196x436.png
r stay    elements_stay_full.json design_stay_1920x1080.png   dev_stay_1920x1081.png
r findid  elements.json           design_1920x1080.png        dev_1920x934.png
r login   elements_login.json     design_login_1920x1080.png  dev_login_1920x934.png
r table   elements_table.json     design_table_1200x700.png   dev_table_1200x700.png
r codes   elements_codes.json     design_codes_1200x760.png   dev_codes_1200x760.png
ELEMENTS_JSON=elements_route_plugin.json DESIGN_PNG=design_route_1920x1080.png DEV_PNG=dev_route_1920x1080.png FORCE_TY=99 DESIGN_MAX=4096 node run.js "$UI" "${P}_route" >/dev/null 2>&1 || echo "FAIL route"
echo "DONE $P"
