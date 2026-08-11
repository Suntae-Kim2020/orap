#!/usr/bin/env bash
# ORAP 를 이 서버에서 서비스하기 위한 설치 스크립트 (sudo 필요).
#
#   sudo bash install-orap-server.sh
#
# 하는 일:
#   1. orap.service 설치 후 기동 (gunicorn → 127.0.0.1:5010)
#   2. Caddyfile 에 orap.ailibrary.kr 블록 추가 후 reload
#   3. 매일 새벽 백업 타이머 설치 (별도 디스크)
# 이미 설치돼 있으면 건너뛰므로 여러 번 실행해도 안전하다.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CADDYFILE=/etc/caddy/Caddyfile

[ "$(id -u)" -eq 0 ] || { echo "sudo 로 실행해야 합니다: sudo bash $0"; exit 1; }

echo "── 1/3  orap.service 설치"
install -m 644 "$SRC/orap.service" /etc/systemd/system/orap.service
systemctl daemon-reload
systemctl enable --now orap.service
sleep 3
systemctl is-active --quiet orap.service || { systemctl status orap.service --no-pager -l | tail -20; exit 1; }
curl -fsS -o /dev/null -m 10 http://127.0.0.1:5010/login
echo "   앱 응답 정상 (127.0.0.1:5010)"

echo "── 2/3  Caddy 설정"
if grep -q '^orap\.ailibrary\.kr' "$CADDYFILE"; then
	echo "   orap 블록이 이미 있어 건너뜁니다"
else
	cp "$CADDYFILE" "$CADDYFILE.bak.$(date +%s)"
	cat "$SRC/orap-caddy-block.txt" >> "$CADDYFILE"
	echo "   블록 추가 완료 (원본은 .bak 로 보관)"
fi
caddy validate --config "$CADDYFILE" >/dev/null
# validate 는 root 로 돌면서 로그 파일을 root 소유로 만들어 버린다. 데몬은 caddy
# 사용자라 그 파일을 열지 못해 reload 가 "permission denied" 로 실패한다.
chown caddy:caddy /var/log/caddy/orap.log 2>/dev/null || true
systemctl reload caddy
echo "   Caddy reload 완료"

echo "── 3/3  백업 타이머 설치"
install -m 644 "$SRC/orap-backup.service" /etc/systemd/system/orap-backup.service
install -m 644 "$SRC/orap-backup.timer" /etc/systemd/system/orap-backup.timer
systemctl daemon-reload
systemctl enable --now orap-backup.timer
systemctl list-timers orap-backup.timer --no-pager | sed -n 2p

cat <<'EOS'

설치 끝.

DNS 가 아직 이 서버를 가리키지 않는다면 (새 서버에 처음 까는 경우) Cafe24 에서
orap 레코드를 A 113.198.48.78 로 맞춰야 Caddy 가 인증서를 발급합니다 (1~10 분).

확인:
  dig +short orap.ailibrary.kr
  curl -I https://orap.ailibrary.kr/
  systemctl status orap --no-pager
  systemctl list-timers orap-backup.timer --no-pager
EOS
