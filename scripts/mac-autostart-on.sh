#!/bin/bash
# 맥을 켜고 로그인하면 검수 포털과 촬영 준비 사이트가 저절로 켜지게 등록한다.
# 맥의 기본 방식(launchd 로그인 항목)을 쓴다. 관리자 권한이 필요 없다.
# 꺼지면 저절로 다시 켜진다. 창은 뜨지 않는다(뒤에서 조용히 돈다).
set -u

ROOT="$(cd "${1:?뿌리 폴더를 넘겨 주세요}" && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
PY="/usr/bin/python3"
mkdir -p "$AGENTS"

if [ ! -f "$ROOT/mvp0/portal.py" ] || [ ! -f "$ROOT/capture-app/site/server.py" ]; then
  echo
  echo "자동 시작을 걸지 못했습니다."
  echo "이 폴더에서 포털·촬영 준비 사이트 파일을 찾지 못했습니다: $ROOT"
  exit 1
fi

# 한 벌 만들기: 이름, 일하는 폴더, 실행할 파일, 기록 남길 곳
write_plist() {
  local name="$1" dir="$2" prog="$3" log="$4"
  cat > "$AGENTS/$name.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$name</string>

  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$prog</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$dir</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>

  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>

  <key>StandardOutPath</key>
  <string>$log</string>
  <key>StandardErrorPath</key>
  <string>$log</string>
</dict>
</plist>
PLIST
}

# 이미 손으로 켜 둔 것이 있으면 자리를 비운다(바로 다시 켜진다).
free_port() {
  local port="$1" pids i
  pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null)"
  [ -z "$pids" ] && return 0
  for i in $pids; do kill "$i" 2>/dev/null; done
  for i in $(seq 1 10); do
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 || return 0
    sleep 0.3
  done
  return 0
}

boot_on() {
  local name="$1"
  launchctl bootout "gui/$UID/$name" >/dev/null 2>&1
  launchctl bootstrap "gui/$UID" "$AGENTS/$name.plist" 2>/dev/null \
    || launchctl load "$AGENTS/$name.plist" 2>/dev/null
}

# 최대 15초 기다리며 정말 떴는지 본다
wait_port() {
  local port="$1" i
  for i in $(seq 1 30); do
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  return 1
}

write_plist com.s1.qa-portal    "$ROOT/mvp0"        "portal.py"      "$ROOT/mvp0/자동실행기록.txt"
write_plist com.s1.capture-site "$ROOT/capture-app" "site/server.py" "$ROOT/capture-app/site/자동실행기록.txt"

free_port 8765
free_port 8767
boot_on com.s1.qa-portal
boot_on com.s1.capture-site

portal_ok=1; capture_ok=1
wait_port 8765 && portal_ok=0
wait_port 8767 && capture_ok=0

echo
if [ $portal_ok -eq 0 ] && [ $capture_ok -eq 0 ]; then
  echo "자동 시작을 등록했습니다. 지금 둘 다 켜져 있습니다."
  echo
  echo "  검수 포털         http://localhost:8765"
  echo "  촬영 준비 사이트   http://localhost:8767"
  echo
  echo "이제 맥을 껐다 켜도 로그인하면 저절로 켜집니다. 창은 뜨지 않습니다."
  exit 0
fi

echo "자동 시작은 등록했지만 지금 켜지지 않은 것이 있습니다."
[ $portal_ok -ne 0 ]  && echo "  · 검수 포털(8765) — 기록: $ROOT/mvp0/자동실행기록.txt"
[ $capture_ok -ne 0 ] && echo "  · 촬영 준비 사이트(8767) — 기록: $ROOT/capture-app/site/자동실행기록.txt"
exit 1
