#!/bin/bash
# 로그인할 때 저절로 켜지는 것을 거둔다. 지금 켜져 있는 것도 함께 꺼진다.
set -u
AGENTS="$HOME/Library/LaunchAgents"
left=0

boot_off() {
  local name="$1"
  launchctl bootout "gui/$UID/$name" >/dev/null 2>&1 \
    || launchctl unload "$AGENTS/$name.plist" >/dev/null 2>&1
  rm -f "$AGENTS/$name.plist"
  [ -f "$AGENTS/$name.plist" ] && left=1
  return 0
}

boot_off com.s1.qa-portal
boot_off com.s1.capture-site

echo
if [ $left -eq 0 ]; then
  echo "자동 시작을 거뒀습니다. 이제 로그인해도 저절로 켜지지 않습니다."
  echo "필요할 때는 '포털-동료공유-켜기.command' 로 손수 켜면 됩니다."
  exit 0
fi
echo "자동 시작을 다 거두지 못했습니다. 남은 파일: $AGENTS"
exit 1
