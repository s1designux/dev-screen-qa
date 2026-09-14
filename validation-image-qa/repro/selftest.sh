#!/bin/bash
# 검수기 자체 검사. 사용: ./selftest.sh [ui.html]
UI=${1:-../../engine/ui.html}
ABS="$(cd "$(dirname "$UI")" && pwd)/$(basename "$UI")"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --no-sandbox --disable-gpu --virtual-time-budget=60000 --dump-dom "file://$ABS?selftest=1" 2>/dev/null > /tmp/selftest_dump.html
echo "$(grep -o 'SELFTEST [A-Z]*' /tmp/selftest_dump.html | head -1) 통과 $(grep -c '✓' /tmp/selftest_dump.html) 실패 $(grep -c '✗' /tmp/selftest_dump.html)"
grep '✗' /tmp/selftest_dump.html | sed 's/<[^>]*>//g' | head -20
