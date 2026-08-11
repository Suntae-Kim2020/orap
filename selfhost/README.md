# 자체 서버 운영 (Caddy + systemd)

2026-08-11 에 Cloud Run 에서 사내 서버(113.198.48.78)로 옮겼다. 이 폴더는 그
서버를 다시 세울 때 필요한 것 전부다.

| 파일 | 설치 위치 | 역할 |
|------|-----------|------|
| `orap.service` | `/etc/systemd/system/` | gunicorn 으로 앱 기동 (127.0.0.1:5010) |
| `orap-caddy-block.txt` | `/etc/caddy/Caddyfile` 끝에 추가 | HTTPS 리버스 프록시 |
| `orap-backup.service` / `.timer` | `/etc/systemd/system/` | 매일 04:00 디스크 백업 (30일 보관) |
| `backup-db.sh` | 이 폴더에서 실행 | 백업 본체 |
| `install-orap-server.sh` | — | 위 셋을 한 번에 설치 (idempotent) |

## 설치

```bash
sudo bash selfhost/install-orap-server.sh
```

앱 환경변수는 `../.env.local` (systemd `EnvironmentFile`, 권한 600, git 제외):

```
GCS_SYNC_DISABLED=1
PORT=5010
FLASK_SECRET_KEY=<Secret Manager 의 orap-flask-secret>
```

## 왜 이렇게 했나

- **왜 gunicorn 1 worker**: SQLite 를 여러 프로세스가 동시에 쓰면 잠금 충돌이
  난다. Cloud Run 때와 같은 제약이라 구성도 같다 (1 worker × 4 threads).
- **왜 127.0.0.1 바인딩**: 외부에 직접 노출하지 않는다. 로그인 이력에 남는
  접속자 IP 는 Caddy 가 넣어 주는 `X-Real-IP` 를 쓰는데, 앱이 로컬에만 묶여
  있어야 그 헤더를 위조당하지 않는다.
- **왜 Caddy 블록에 `bind 113.198.48.78`**: 그냥 두면 Caddy 가 `:443` 을
  와일드카드로 잡는데, 태일넷 주소(100.x)의 443 은 다른 프로젝트가 이미 쓰고
  있어 충돌한다. teed·kisti 블록도 같은 이유로 공인 IP 에 묶여 있다.
- **왜 GCS 실시간 동기화(`gcs_sync.py`)를 껐나**: 그건 파일시스템이 휘발하는
  Cloud Run 때문에 있던 장치다. 이 서버는 디스크가 남으므로 필요 없다. GCS
  버킷도 없앴으므로 다시 켜면 기동조차 안 된다.
- **왜 백업을 `/media/user/df9db4f3-.../` 에**: 시스템 디스크(NVMe)와 물리적으로
  다른 15TB HDD 다. 같은 디스크에 두면 디스크가 죽을 때 원본과 백업이 함께
  사라져 백업이 아니게 된다.
- **왜 백업 스크립트가 `mountpoint` 를 검사하나**: 외장 디스크가 안 붙어 있으면
  마운트 지점은 그냥 빈 디렉터리다. 모르고 쓰면 시스템 디스크에 백업이 쌓이면서
  "백업이 되고 있다" 고 착각하게 된다. 그래서 마운트가 없으면 즉시 실패한다.

## 복원

```bash
sudo systemctl stop orap
cp /media/user/df9db4f3-386b-4bd4-b1bf-fcebb530b180/orap-backups/2026-08-12/users.db \
   /home/user/orap/users.db
sudo systemctl start orap
```

## 자주 쓰는 명령

```bash
sudo systemctl status orap            # 상태
sudo systemctl restart orap           # 코드 배포 후 재시작
sudo journalctl -u orap -f            # 앱 로그
sudo tail -f /var/log/caddy/orap.log  # 접속 로그
sudo systemctl start orap-backup      # 백업 즉시 실행
systemctl list-timers orap-backup.timer
```

## 함정

`sudo caddy validate` 는 root 권한으로 로그 파일을 먼저 만들어 버린다. 그러면
`caddy` 사용자로 도는 데몬이 그 파일을 열지 못해 reload 가 `permission denied`
로 실패한다. 설치 스크립트가 validate 직후 `chown caddy:caddy` 로 바로잡는다.
