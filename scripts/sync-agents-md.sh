#!/bin/bash
# AGENTS.md 와 CLAUDE.md 를 항상 같은 파일로 유지한다.
# river님이 Claude(CLAUDE.md)와 GPT/Codex(AGENTS.md)를 오가며 쓰기 때문에 두 이름이 모두 필요하고,
# 어떤 도구가 AGENTS.md 를 통째로 덮어써서 링크가 풀리는 일이 생길 수 있다.
# 세션이 시작될 때마다 이 스크립트가 상태를 살펴 스스로 되돌린다. 내용은 절대 버리지 않는다.

set -u
cd "$(dirname "$0")/.." || exit 0
[ -f CLAUDE.md ] || exit 0

msg=""
if [ -L AGENTS.md ]; then
  exit 0                                   # 이미 링크 — 할 일 없음
elif [ ! -e AGENTS.md ]; then
  ln -s CLAUDE.md AGENTS.md
  msg="AGENTS.md 가 없어서 CLAUDE.md 를 가리키는 링크로 다시 만들었어요."
elif cmp -s AGENTS.md CLAUDE.md; then
  rm -f AGENTS.md && ln -s CLAUDE.md AGENTS.md
  msg="AGENTS.md 가 사본으로 바뀌어 있었어요. 내용이 같아서 다시 링크로 되돌렸습니다."
else
  # 내용이 다르다 = 어느 한쪽이 따로 고쳐졌다. 최근에 고친 쪽을 살리고, 반대쪽은 백업해 둔다.
  ts=$(date +%Y%m%d-%H%M%S); mkdir -p .agents-md-backup
  if [ AGENTS.md -nt CLAUDE.md ]; then
    cp CLAUDE.md ".agents-md-backup/CLAUDE.md.$ts"
    cp AGENTS.md CLAUDE.md
    msg="AGENTS.md 가 따로 수정돼 있었어요(더 최근). 그 내용을 CLAUDE.md 로 옮기고 링크로 되돌렸습니다. 이전 CLAUDE.md 는 .agents-md-backup/CLAUDE.md.$ts 에 보관했어요."
  else
    cp AGENTS.md ".agents-md-backup/AGENTS.md.$ts"
    msg="AGENTS.md 가 사본으로 바뀌어 CLAUDE.md 와 내용이 달랐어요. 더 최근인 CLAUDE.md 를 살리고 링크로 되돌렸습니다. 떼어낸 AGENTS.md 는 .agents-md-backup/AGENTS.md.$ts 에 보관했어요."
  fi
  rm -f AGENTS.md && ln -s CLAUDE.md AGENTS.md
fi

printf '{"systemMessage":"%s"}\n' "$msg"
