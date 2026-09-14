#!/bin/zsh
# 검수 포털 자동 백업 — 하루 한 번, 7일치 보관
SRC=/Users/designgroup_02/dev-screen-qa/mvp0
DST=/Users/designgroup_02/dev-screen-qa-백업
DAY=$(date +%Y%m%d-%H%M)
OUT=$DST/$DAY
mkdir -p "$OUT" || exit 1

# 검수 데이터(열려 있어도 안전하게 복사)
if [ -f "$SRC/mvp0-real.db" ]; then
  /usr/bin/sqlite3 "$SRC/mvp0-real.db" ".backup '$OUT/mvp0-real.db'" || cp "$SRC/mvp0-real.db" "$OUT/mvp0-real.db"
fi

# 업로드 이미지 (바뀐 것만)
if [ -d "$SRC/uploads" ]; then
  /usr/bin/rsync -a --delete "$SRC/uploads/" "$OUT/uploads/"
fi

echo "$(date '+%Y-%m-%d %H:%M') 백업 완료 → $OUT" >> "$DST/백업기록.txt"

# 7일치만 남기고 오래된 것 정리
ls -1d "$DST"/20* 2>/dev/null | sort -r | tail -n +8 | while read old; do rm -rf "$old"; done
