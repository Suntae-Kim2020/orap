# JBNU ORAP — 학술성과 분석 플랫폼

## 프로젝트 개요

전북대학교 연구처(Office of Research Affairs Platform) 학술성과 분석 웹 서비스.
계량서지학 지표(h/g/i10/m), 우수논문 분석, 연구분야/세계대학 분석, AI 분석, 다기관 운영 지원.

- **Backend**: Flask 3.1.2 (단일 파일 `app.py`, ~9k 라인)
- **DB**: SQLite (기관별 분리)
- **Frontend**: Bootstrap 5 + Vanilla JS
- **Deployment**: 자체 서버 (Caddy + systemd, 2026-08-11부터) — 그 전에는 GCP Cloud Run
- **운영 URL**: https://orap.ailibrary.kr

---

## 파일 구조

```
orap/
├── CLAUDE.md                 # 이 파일
├── README.md                 # 사용자 가이드
├── ARCHITECTURE.md           # 시스템 구조
├── app.py                    # 메인 Flask 앱 (~9k 라인)
├── requirements.txt          # Python 의존성
│
├── selfhost/                 # 현행 배포 (Caddy + systemd) ★
│   ├── README.md             #   설치·복원·함정
│   ├── install-orap-server.sh
│   ├── orap.service          #   gunicorn → 127.0.0.1:5010
│   ├── orap-caddy-block.txt  #   Caddyfile 에 추가할 블록
│   ├── orap-backup.{service,timer}
│   └── backup-to-gcs.sh      #   매일 04:00 GCS 백업
├── .env.local                # 운영 환경변수 (600, git 제외)
│
├── gcs_sync.py               # (구) GCS DB 동기화 — 현재 비활성
├── Dockerfile                # (구) Cloud Run 컨테이너 정의
├── deploy.sh                 # (구) Cloud Run 배포 스크립트
├── .gcloudignore             # (구) gcloud 빌드 컨텍스트 제외
│
├── *.db                      # SQLite DB (jbnu/korea/sejong, users)
├── snapshots/                # 데이터 스냅샷 (런타임 생성)
├── uploads/                  # 파일 업로드 (런타임 생성)
│
├── templates/                # HTML 템플릿
├── static/                   # JS, CSS, 다국어 (lang/ko.json, lang/en.json)
├── docs/                     # 기능/설계 문서
│
└── 유틸리티 스크립트/
    ├── analyze_csv.py
    ├── find_empty_rows.py
    ├── import_korea.py
    ├── import_rawdata.py
    └── calculate_korea_scores.py
```

---

## 데이터베이스 구조

기관별 SQLite 파일 분리:

| DB 파일 | 용량 | 용도 |
|---------|------|------|
| `users.db` | ~160KB | 사용자 / 권한 / 기관 매핑 (마스터) |
| `jbnu.db` | ~75MB | 전북대학교 |
| `korea.db` | ~190MB | 고려대학교 |
| `sejong.db` | ~70MB | 세종대학교 |
| (확장) | | `users.db`의 `institutions` 테이블에 추가하면 자동 인식 |

**기관 추가 방식**: `users.db`의 `institutions` 테이블에 (`inst_key`, `inst_name`, `affiliation`, `db_file`, `is_active`) 추가 → 새 DB 파일은 첫 접속 시 `init_institution_db()`가 자동 생성. `gcs_sync._list_known_dbs()`도 동적으로 신규 DB 인식.

---

## 배포 구조 (자체 서버, 2026-08-11~)

Cloud Run에서 사내 서버로 이전. 상세는 [`selfhost/README.md`](selfhost/README.md).

| 항목 | 값 |
|------|-----|
| **서버** | 113.198.48.78 (Ubuntu 24.04) — teed / kisti / kistep와 공용 |
| **앱** | `orap.service` → gunicorn 1 worker × 4 threads, timeout 600s, `127.0.0.1:5010` |
| **HTTPS** | Caddy 리버스 프록시 (`/etc/caddy/Caddyfile`) — 인증서 자동 발급/갱신 |
| **운영 URL** | https://orap.ailibrary.kr |
| **DNS** | Cafe24 (`orap` A → `113.198.48.78`) |
| **환경변수** | `.env.local` (600, git 제외) — `FLASK_SECRET_KEY`, `PORT=5010`, `GCS_SYNC_DISABLED=1` |
| **백업** | `orap-backup.timer` 매일 04:00 → `gs://ailibrary-orap-data/backup/<날짜>/`, 14일 보관 |
| **DB/업로드** | 로컬 디스크가 원본. `uploads/`, `snapshots/`도 이제 영속 |

앱은 `127.0.0.1`에만 묶는다. 로그인 이력의 접속자 IP는 Caddy가 넣는 `X-Real-IP`를 쓰는데, 로컬 바인딩이어야 그 헤더를 위조당하지 않는다.

### 배포 (코드 변경 반영)

```bash
cd /home/user/orap
git pull                       # 또는 직접 수정
sudo systemctl restart orap
sudo journalctl -u orap -n 30 --no-pager
```

재시작 1~2초. 컨테이너 빌드가 없어 Cloud Run 때(5~10분)보다 훨씬 빠르다.

---

## (구) Cloud Run + GCS 동기화 — 2026-08-11 종료

이전 방식. `gcs_sync.py`, `Dockerfile`, `deploy.sh`가 그 잔재이며 **현재 동작하지 않는다**(`GCS_SYNC_DISABLED=1`).

- GCP 프로젝트 `ailibrary-orap` / 리전 `asia-northeast1` / 버킷 `gs://ailibrary-orap-data`
- Secret Manager `orap-flask-secret`은 **지금도 사용** — 자체 서버의 `.env.local`에 그 값을 넣어 두었다(세션 쿠키 호환 유지).
- `gs://ailibrary-orap-data/db/`에 마지막 운영본이 그대로 남아 있다. 롤백 대비용이라 덮어쓰지 않는다.
- `gcs_sync.py`는 stateless 파일시스템 대응 장치였다. 디스크가 남는 서버에서는 필요 없을 뿐 아니라, 켜 두면 두 곳에서 같은 DB를 덮어써 데이터가 갈린다.

---

## 로컬 개발

```bash
cd /home/user/orap
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 개발 서버 (디버그 모드). 운영 포트 5010과 겹치지 않게 기본 57769를 쓴다.
GCS_SYNC_DISABLED=1 python app.py
# → http://localhost:57769
```

`PORT` env로 포트 변경 가능. 운영 중인 서버와 **같은 DB 파일을 쓰므로** 주의 —
데이터를 건드릴 실험이라면 DB를 복사해 별도 디렉터리에서 돌릴 것.

---

## 도메인 / DNS

- 루트 도메인 `ailibrary.kr`은 Cafe24에서 관리 (네임서버 `ns1~ns2.cafe24.com`)
- 서브도메인 매핑:
  - `orap.ailibrary.kr` → A `113.198.48.78` (이 서버, 2026-08-11 전환)
  - `teed`, `kisti`, `kistep`, `humanoidrobot` → 같은 서버의 Caddy가 함께 처리
- 도메인 소유권은 `kistiman@gmail.com` 계정에서 verified
- 신규 서브도메인 추가: Cafe24에 A 레코드(`113.198.48.78`) 등록 → `/etc/caddy/Caddyfile`에 블록 추가 → `sudo systemctl reload caddy`. 인증서는 Caddy가 1~10분 안에 발급

---

## 운영 명령

```bash
# 배포 (코드 변경 반영)
sudo systemctl restart orap

# 상태 / 앱 로그
sudo systemctl status orap --no-pager
sudo journalctl -u orap -f

# 접속 로그
sudo tail -f /var/log/caddy/orap.log

# Caddy 설정 변경 후 (검증 → 반영)
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy

# 백업 즉시 실행 / 스케줄 확인
sudo systemctl start orap-backup
systemctl list-timers orap-backup.timer

# 백업 목록
gcloud storage ls gs://ailibrary-orap-data/backup/ --project=ailibrary-orap

# 복원 (예: 2026-08-11 시점 users.db)
gcloud storage cp gs://ailibrary-orap-data/backup/2026-08-11/users.db ./users.db --project=ailibrary-orap
sudo systemctl restart orap
```

---

## 비용

자체 서버 이전으로 Cloud Run 비용(월 $30-50)이 사라졌다. 남는 것은 GCS 백업 스토리지뿐:

| 항목 | 월 비용 |
|------|---------|
| GCS 백업 (~340MB × 14일치 = ~4.7GB) | ~$0.1 |
| GCS 구 운영본 `db/` (~340MB, 롤백 대비 보관) | ~$0.01 |
| Secret Manager | ~$0 (free tier) |
| 서버 / 전기 / 회선 | 기존 공용 서버 |

---

## 제약사항 / 주의점

1. **단일 워커 강제** (gunicorn `--workers 1`): SQLite 동시 쓰기 충돌 방지. 트래픽이 늘면 PostgreSQL 마이그레이션 필요. `migrate_to_cloudsql.py`가 출발점.
2. **백업은 하루 한 번**: 마지막 백업 이후 변경분은 디스크 장애 시 잃는다. 대량 임포트 직후에는 `sudo systemctl start orap-backup`으로 수동 백업 권장.
3. **서버 공용**: teed / kisti / kistep와 같은 장비, 같은 Caddy를 쓴다. Caddyfile을 고칠 때 다른 사이트 블록을 건드리지 않게 주의. reload 실패 시 Caddy는 **기존 설정으로 계속 동작**하므로 다른 사이트가 즉시 죽지는 않는다.
4. **Caddy 로그 파일 소유권**: `sudo caddy validate`가 로그 파일을 root 소유로 만들어 두면 데몬(`caddy` 사용자)이 열지 못해 reload가 실패한다. `sudo chown caddy:caddy /var/log/caddy/orap.log`로 해결.
5. **Flask SECRET_KEY**: Secret Manager의 `orap-flask-secret`을 `.env.local`에 넣어 주입. 이 값이 바뀌면 전체 로그인 세션이 끊긴다.

---

## 향후 개선 (TODO)

- [ ] `app.py` 단일 파일 → Flask Blueprint 분할
- [ ] PostgreSQL 마이그레이션 → 다중 인스턴스 지원
- [ ] `uploads/`, `snapshots/` 백업 대상에 추가 (현재 DB만 백업)
- [ ] dev/prod 환경 분리 (`orap-dev.ailibrary.kr`)
- [ ] 백업 실패 알림 (`orap-backup.service`의 `OnFailure=`)
- [ ] 모니터링 (서비스 다운 / 디스크 사용률)
