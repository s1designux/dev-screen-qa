#!/bin/bash
# '찍는 손' — 안드로이드. 대본 한 장을 실제 폰에서 실행하고 사진 한 장을 남긴다.
# 나중에 웹을 붙일 때는 같은 자리에 web.sh만 채우면 된다.
#
# 쓰는 법: android.sh <대본> <앱주소> <누를것> <사진이름(확장자 없이)> <임시폴더>
set -euo pipefail

flow="$1"; app_id="$2"; tap_text="$3"; shot_name="$4"; out_dir="$5"

# 도구 자리 잡기 — 어느 PC에서든 찾아 쓴다.
export PATH="$HOME/.maestro/bin:$HOME/Library/Android/sdk/platform-tools:$PATH"
if [ -z "${JAVA_HOME:-}" ] && [ -d /opt/homebrew/opt/openjdk@21 ]; then
  export JAVA_HOME="/opt/homebrew/opt/openjdk@21"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

# 폐쇄망 원칙 — 바깥으로 사용기록을 보내지 않는다.
export MAESTRO_CLI_NO_ANALYTICS=1

exec maestro test "$flow" \
  --test-output-dir="$out_dir" \
  -e APP_ID="$app_id" \
  -e TAP_TEXT="$tap_text" \
  -e SHOT_PATH="$shot_name"
