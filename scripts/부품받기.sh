#!/usr/bin/env bash
# S-1 정본 부품 CSS(s1-ui.css)를 포털로 받아 둔다.
#
# 손으로 고치지 않는다 — 가이드가 바뀌면 이 스크립트를 다시 돌린다.
# 받아 온 그대로라서 우리가 적은 값이 아니다. 그래서 위아래에 's1-제외' 표시를 붙여
# 토큰 점검기가 이 파일을 우리 화면으로 세지 않게 한다(가이드의 tokens.css 를 이름으로 건너뛰는 것과 같다).
#
#   bash scripts/부품받기.sh
#
# (셸 변수 이름은 ASCII 로 둔다 — bash 는 한글 변수 이름을 받지 않는다.)
set -euo pipefail

guide=${S1_GUIDE_DIR:-$HOME/.claude/s1-design-guide}
src="$guide/ui-library/dist/s1-ui.css"
mani="$guide/ui-library/dist/manifest.json"
dest="$(cd "$(dirname "$0")/.." && pwd)/mvp0/assets/css/s1-ui.css"

[ -f "$src" ] || { echo "부품 CSS 를 찾지 못했습니다 — $src (먼저 가이드받기.sh 를 돌리세요)"; exit 1; }

ver=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['version'],d['releasedAt'])" "$mani" 2>/dev/null || echo "판 모름")

{
  echo "/* s1-제외 시작 — 아래는 S-1 정본 부품 CSS 사본입니다(s1-ui $ver)."
  echo "   손으로 고치지 마세요. 다시 받기: bash scripts/부품받기.sh */"
  cat "$src"
  echo "/* s1-제외 끝 */"
} > "$dest"

echo "받아 둠: mvp0/assets/css/s1-ui.css  (s1-ui $ver)"
