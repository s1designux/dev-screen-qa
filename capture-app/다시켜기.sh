#!/bin/bash
# 촬영 준비 사이트를 다시 켠다 (코드를 고친 뒤에는 꼭 한 번).
# 맥을 켜면 저절로 뜨게 해 두었으므로(launchd), 여기서는 껐다 켜기만 한다.
set -euo pipefail
LABEL="com.s1.capture-site"
if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  launchctl kickstart -k "gui/$(id -u)/$LABEL"
  echo "촬영 준비 사이트를 다시 켰습니다 → http://127.0.0.1:8767"
else
  echo "저절로 뜨게 하는 설정이 없습니다. ./site.sh 로 직접 켜세요."
  exit 1
fi
