# JBNU ORAP — 학술성과 분석 플랫폼

## 프로젝트 개요

전북대학교 연구처(Office of Research Affairs Platform) 학술성과 분석 웹 서비스.
계량서지학 지표(h/g/i10/m), 우수논문 분석, 연구분야/세계대학 분석, AI 분석, 다기관 운영 지원.

- **Backend**: Flask 3.1.2 (단일 파일 `app.py`, ~9k 라인)
- **DB**: SQLite (기관별 분리)
- **Frontend**: Bootstrap 5 + Vanilla JS
- **Deployment**: GCP Cloud Run (2026-04부터)
- **운영 URL**: https://orap.ailibrary.kr

---

## 파일 구조

```
orap/
├── CLAUDE.md                 # 이 파일
├── README.md                 # 사용자 가이드
├── ARCHITECTURE.md           # 시스템 구조
├── app.py                    # 메인 Flask 앱 (~9k 라인)
├── gcs_sync.py               # GCS DB 동기화 (Cloud Run 영속성)
├── Dockerfile                # Cloud Run 컨테이너 정의
├── deploy.sh                 # Cloud Run 배포 스크립트
├── .gcloudignore             # gcloud 빌드 컨텍스트 제외
├── requirements.txt          # Python 의존성
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

## GCP 배포 구조

| 항목 | 값 |
|------|-----|
| **GCP 프로젝트** | `ailibrary-orap` (KISTI와 별도, 동일 결제 계정) |
| **리전** | `asia-northeast1` (도쿄) |
| **Cloud Run 서비스** | `orap` |
| **GCS 버킷** | `gs://ailibrary-orap-data` |
| **운영 URL** | https://orap.ailibrary.kr |
| **임시 URL** | https://orap-692750988631.asia-northeast1.run.app |
| **DNS** | Cafe24 (`orap` CNAME → `ghs.googlehosted.com.`) |
| **Secret Manager** | `orap-flask-secret` (FLASK_SECRET_KEY) |
| **메모리/CPU** | 2Gi RAM, 2 vCPU |
| **인스턴스** | min=1, max=1 (24시간 운영, SQLite 동시쓰기 충돌 방지) |
| **gunicorn** | 1 worker × 4 threads, timeout 600s |

### 배포 명령

```bash
cd /Users/kimsuntae/orap
./deploy.sh
```

빌드/배포 약 5~10분 소요. 첫 배포 후 SSL 인증서 자동 발급은 15분~1시간.

---

## GCS 하이브리드 동기화 (`gcs_sync.py`)

Cloud Run은 stateless 파일시스템이라 SQLite 변경분이 인스턴스 재시작 시 사라짐. 이를 해결하기 위한 자동 동기화:

### 시작 시
- `gs://ailibrary-orap-data/db/`에서 모든 DB 다운로드 → 로컬 `/app/`
- `users.db` 먼저 → `institutions` 테이블에서 기관 DB 목록 → 기관 DB 다운로드

### 런타임 — 하이브리드 전략
| DB 종류 | 폴링 주기 | 업로드 시점 |
|---------|-----------|-------------|
| `users.db` (인증/권한 critical) | 5초 | mtime 변경 즉시 (write-through) |
| 기관 DB (jbnu/korea/sejong 등) | 30초 (mtime 감지) | **마지막 변경 후 60초 안정화** + **5분 일괄 주기** |

기관 DB의 안정화 임계값(60초)은 대용량 CSV 임포트 중 잦은 업로드를 방지.

### 종료 시 (SIGTERM/SIGINT)
- 모든 dirty DB 최종 업로드
- Cloud Run의 graceful timeout 60초 안에 완료 필요

### 안전성
- 핫복사: `sqlite3.Connection.backup()` API로 트랜잭션 일관성 보장
- 단일 인스턴스(max=1) 강제로 다중 워커 간 쓰기 충돌 방지

### 환경변수
- `GCS_BUCKET`: 버킷명 (기본 `ailibrary-orap-data`)
- `GCS_SYNC_DISABLED=1`: 로컬 개발 시 동기화 비활성화

---

## 로컬 개발

```bash
cd /Users/kimsuntae/orap
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# GCS 동기화 끄고 실행 (로컬 DB 그대로 사용)
GCS_SYNC_DISABLED=1 python app.py
# → http://localhost:57769
```

`PORT` env로 포트 변경 가능.

---

## 도메인 / DNS

- 루트 도메인 `ailibrary.kr`은 Cafe24에서 관리 (네임서버 `ns1~ns2.cafe24.com`)
- 서브도메인 매핑:
  - `orap.ailibrary.kr` → 본 프로젝트 (`ailibrary-orap`)
  - `kisti.ailibrary.kr`, `dev.kisti.ailibrary.kr` → KISTI Policy 프로젝트 (`ailibrary-kisti`)
- 도메인 소유권은 `kistiman@gmail.com` 계정에서 verified — 동일 계정의 새 GCP 프로젝트는 별도 verification 불필요
- 신규 서브도메인 추가 절차: GCP에 `gcloud beta run domain-mappings create ...` → 출력 CNAME을 Cafe24에 등록 → 15분~1시간 SSL 자동 발급

---

## 운영 명령

```bash
# 배포
./deploy.sh

# 로그 보기
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=orap' \
  --limit=50 --format='value(textPayload)' --project=ailibrary-orap

# Cloud Run 상태
gcloud run services describe orap --region=asia-northeast1 --project=ailibrary-orap

# 도메인 매핑 상태 (SSL 발급 확인)
gcloud beta run domain-mappings describe --domain=orap.ailibrary.kr \
  --region=asia-northeast1 --project=ailibrary-orap

# GCS DB 상태
gcloud storage ls -l gs://ailibrary-orap-data/db/ --project=ailibrary-orap

# DB 수동 다운로드 (백업)
gcloud storage cp gs://ailibrary-orap-data/db/users.db ./users.db.backup --project=ailibrary-orap

# DB 수동 업로드 (강제 덮어쓰기 — 신중)
gcloud storage cp ./users.db gs://ailibrary-orap-data/db/users.db --project=ailibrary-orap
```

---

## 비용 (예상)

| 항목 | 월 비용 |
|------|---------|
| Cloud Run min=1 (CPU 2, RAM 2Gi 상시) | ~$30-50 |
| GCS 스토리지 (~340MB) + 트래픽 | ~$1-3 |
| Secret Manager | ~$0 (free tier) |
| 도메인 매핑 / SSL | $0 |
| **합계** | **~$32-53/월** |

비용 절감 옵션 (사용 시간만 운영):
- `--min-instances=0`으로 변경 → scale-to-zero
- 단점: 첫 요청 시 콜드 스타트 + GCS DB 다운로드 ~10초 대기

---

## 제약사항 / 주의점

1. **단일 인스턴스 강제** (`max-instances=1`): SQLite 동시 쓰기 충돌 방지. 트래픽이 늘면 PostgreSQL(Cloud SQL) 마이그레이션 필요. `migrate_to_cloudsql.py`가 출발점.
2. **GCS 동기화 지연**: 기관 DB 변경은 최대 5분까지 GCS 반영 지연. 인스턴스 강제 종료(crash) 시 마지막 5분 데이터 손실 가능. SIGTERM 정상 종료 시는 안전.
3. **첫 부팅 대기**: Cloud Run 콜드 스타트 + GCS 다운로드 (340MB) 약 10초. min=1 유지로 회피.
4. **`uploads/`, `snapshots/` 영속성 없음**: 현재는 GCS 동기화 대상 아님. 사용자 업로드 파일은 인스턴스 재시작 시 사라짐. 필요하면 `gcs_sync.py`에 폴더 동기화 추가.
5. **Flask SECRET_KEY**: Secret Manager의 `orap-flask-secret`을 환경변수 `FLASK_SECRET_KEY`로 주입. 로컬은 코드 기본값 사용.

---

## 향후 개선 (TODO)

- [ ] `app.py` 단일 파일 → Flask Blueprint 분할
- [ ] PostgreSQL(Cloud SQL) 마이그레이션 → 다중 인스턴스 지원
- [ ] `uploads/`, `snapshots/` GCS 동기화 추가
- [ ] dev/prod 환경 분리 (`orap-dev.ailibrary.kr`)
- [ ] CI/CD (GitHub Actions → Cloud Run 자동 배포)
- [ ] 모니터링 알림 (Cloud Monitoring → 메모리/에러 임계치)
