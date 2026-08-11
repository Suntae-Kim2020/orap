#!/usr/bin/env bash
# ORAP DB 를 별도 디스크에 백업한다. orap-backup.timer 가 매일 새벽에 부른다.
#
# 자체 서버로 옮기면서 GCS 동기화를 껐고 버킷도 없앴다. 그래서 이 서버의 로컬
# 디스크가 유일한 원본이고, 이 스크립트가 그 안전망이다.
#
# 백업 대상 디스크는 시스템 디스크(NVMe)와 물리적으로 다른 15TB HDD 다. 같은
# 디스크에 두면 디스크가 죽을 때 원본과 백업이 함께 사라져 백업이 아니게 된다.
#
# 복원:
#   sudo systemctl stop orap
#   cp /media/user/df9db4f3-.../orap-backups/2026-08-12/users.db /home/user/orap/
#   sudo systemctl start orap
set -euo pipefail

APP_DIR=/home/user/orap
DEST_DISK=${DEST_DISK:-/media/user/df9db4f3-386b-4bd4-b1bf-fcebb530b180}
DEST=${DEST:-$DEST_DISK/orap-backups}
KEEP_DAYS=${KEEP_DAYS:-30}

# 외장 디스크가 안 붙어 있으면 마운트 지점은 그냥 빈 디렉터리다. 그대로 쓰면
# 시스템 디스크에 백업이 쌓이면서 "백업이 되고 있다"고 착각하게 된다.
mountpoint -q "$DEST_DISK" || {
	echo "백업 디스크가 마운트돼 있지 않습니다: $DEST_DISK" >&2
	exit 1
}

DATE=$(date +%F)
OUT="$DEST/$DATE"
mkdir -p "$OUT"
cd "$APP_DIR"

# 서비스가 돌고 있는 중에도 안전하게 뜨려면 파일을 그냥 cp 하면 안 된다. 쓰기
# 도중이면 반쯤 쓰인 페이지가 섞여 깨진 DB 가 나온다. SQLite 의 backup API 는
# 트랜잭션 일관성을 보장한다.
for db in *.db; do
	[ -e "$db" ] || continue
	"$APP_DIR/venv/bin/python" - "$db" "$OUT/$db" <<-'PY'
		import sqlite3, sys
		src, dst = sys.argv[1], sys.argv[2]
		s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
		d = sqlite3.connect(dst)
		with d:
		    s.backup(d)
		d.close(); s.close()
	PY
	echo "  $db → $(du -h "$OUT/$db" | cut -f1)"
done

# 백업이 깨진 채 쌓이면 정작 복원할 때 알게 된다. 뜨자마자 검사한다.
for f in "$OUT"/*.db; do
	res=$("$APP_DIR/venv/bin/python" -c "
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
print(c.execute('pragma quick_check').fetchone()[0])" "$f")
	[ "$res" = "ok" ] || { echo "무결성 검사 실패: $f ($res)" >&2; exit 1; }
done
echo "무결성 검사 통과"

# 오래된 백업 정리. 폴더명이 YYYY-MM-DD 라 사전순 정렬이 곧 시간순이다.
CUTOFF=$(date -d "$KEEP_DAYS days ago" +%F)
for d in "$DEST"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]; do
	[ -d "$d" ] || continue
	name=$(basename "$d")
	if [[ "$name" < "$CUTOFF" ]]; then
		rm -rf "$d" && echo "  정리: $name"
	fi
done

echo "백업 끝: $OUT ($KEEP_DAYS 일치 보관, 남은 용량 $(df -h --output=avail "$DEST_DISK" | tail -1 | tr -d ' '))"
