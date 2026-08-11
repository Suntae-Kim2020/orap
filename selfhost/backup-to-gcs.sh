#!/usr/bin/env bash
# ORAP DB 를 GCS 로 백업한다. orap-backup.timer 가 매일 새벽에 부른다.
#
# 자체 서버로 옮기면서 GCS 실시간 동기화(gcs_sync.py)를 껐기 때문에 이 서버의
# 로컬 디스크가 유일한 원본이다. 이 스크립트가 그 안전망 역할을 한다.
#
# 백업 위치는 gs://<버킷>/backup/<날짜>/ 이다. Cloud Run 이 쓰던 db/ 경로를
# 건드리지 않는 이유는, 그쪽을 덮어쓰면 예전 운영본이 사라져 되돌릴 수 없기
# 때문이다.
#
# 복원:
#   gcloud storage cp gs://ailibrary-orap-data/backup/2026-08-11/users.db ./users.db
#   sudo systemctl restart orap
set -euo pipefail

APP_DIR=/home/user/orap
BUCKET=${GCS_BUCKET:-ailibrary-orap-data}
PROJECT=${GCS_PROJECT:-ailibrary-orap}
KEEP_DAYS=${KEEP_DAYS:-14}
GCLOUD=${GCLOUD:-/home/user/google-cloud-sdk/bin/gcloud}

DATE=$(date +%F)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cd "$APP_DIR"

# 서비스가 돌고 있는 중에도 안전하게 뜨려면 파일을 그냥 cp 하면 안 된다.
# 쓰기 도중이면 반쯤 쓰인 페이지가 섞여 깨진 DB 가 나온다. SQLite 의 backup
# API 는 트랜잭션 일관성을 보장한다. gcs_sync.py 가 쓰는 방식과 같다.
for db in *.db; do
	[ -e "$db" ] || continue
	"$APP_DIR/venv/bin/python" - "$db" "$TMP/$db" <<-'PY'
		import sqlite3, sys
		src, dst = sys.argv[1], sys.argv[2]
		s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
		d = sqlite3.connect(dst)
		with d:
		    s.backup(d)
		d.close(); s.close()
	PY
	echo "  스냅샷: $db ($(du -h "$TMP/$db" | cut -f1))"
done

"$GCLOUD" storage cp "$TMP"/*.db "gs://$BUCKET/backup/$DATE/" --project="$PROJECT"
echo "업로드 완료: gs://$BUCKET/backup/$DATE/"

# 오래된 백업 정리. 날짜 폴더명이 YYYY-MM-DD 라 사전순 정렬이 곧 시간순이다.
CUTOFF=$(date -d "$KEEP_DAYS days ago" +%F)
"$GCLOUD" storage ls "gs://$BUCKET/backup/" --project="$PROJECT" 2>/dev/null \
	| sed -n 's#.*/backup/\([0-9-]\{10\}\)/$#\1#p' \
	| while read -r d; do
		if [[ "$d" < "$CUTOFF" ]]; then
			"$GCLOUD" storage rm -r "gs://$BUCKET/backup/$d/" --project="$PROJECT" >/dev/null 2>&1 \
				&& echo "  정리: $d"
		fi
	done

echo "백업 끝 ($KEEP_DAYS 일치 보관)"
