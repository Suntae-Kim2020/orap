# JBNU ORAP (Office of Research Affairs Platform) 아키텍처 문서

## 프로젝트 개요

JBNU ORAP는 전북대학교 연구처에서 학술성과, 연구사업 등의 데이터를 업로드하고 분석하기 위한 웹 기반 플랫폼입니다. 연구논문의 우수성 평가, 연구자 랭킹(계량서지학 지표 포함), 연구분야/세계대학 분석, AI 분석 등을 제공하며, 기관별로 분리된 SQLite DB를 통해 다기관 운영을 지원합니다.

## 시스템 아키텍처

### 전체 구조
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Database      │
│   (HTML/JS)     │◄──►│   (Flask)       │◄──►│   (SQLite)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 기술 스택
- **Backend**: Flask 3.1.2 (Python)
- **Database**: SQLite 3 (기관별 파일 분리) + GCS 영속성 동기화
- **Frontend**: HTML, CSS, JavaScript (Bootstrap 5)
- **Data Processing**: Pandas 2.3.2, NumPy 2.0.2
- **File Handling**: OpenPyXL 3.1.5, XlsxWriter 3.2.5
- **번역**: deep-translator (Google)
- **Deployment**: GCP Cloud Run (asia-northeast1) + Gunicorn 21.2.0
- **Storage**: GCS 버킷 (`ailibrary-orap-data`)
- **Secret**: GCP Secret Manager

## 프로젝트 구조

```
orap/
├── app.py                          # 메인 애플리케이션 서버 (단일 파일, ~9k 라인)
├── gcs_sync.py                     # GCS DB 동기화 (Cloud Run 영속성)
├── Dockerfile                      # Cloud Run 컨테이너 정의
├── deploy.sh                       # Cloud Run 배포 스크립트
├── .gcloudignore                   # gcloud 빌드 컨텍스트 제외
├── requirements.txt                # Python 의존성
├── jbnu.db / korea.db / ...        # 기관별 SQLite DB
├── users.db                        # 사용자/권한/기관 매핑 DB
├── CLAUDE.md                       # 프로젝트/배포 운영 가이드
├── README.md
├── ARCHITECTURE.md
├── templates/                      # HTML 템플릿 (admin_*, analysis_*, field_*, survey 등)
├── static/                         # 정적 리소스 (js/, lang/ko.json, lang/en.json)
├── docs/                           # 기능/설계 문서
└── 유틸리티 스크립트/
    ├── analyze_csv.py
    ├── find_empty_rows.py
    ├── import_korea.py
    ├── import_rawdata.py
    └── calculate_korea_scores.py
```

## 데이터베이스 구성

- **기관별 SQLite 분리**: `jbnu.db`, `korea.db`, `sejong.db` 등 기관마다 별도 파일. 로그인 후 선택한 기관의 DB로 접속.
- **사용자/권한/기관 매핑**: `users.db`의 `institutions` 테이블이 마스터.
- **테이블 초기화/마이그레이션**: `init_institution_db()`, `migrate_database()`가 첫 실행/기동 시 필요한 테이블을 생성·보강.
- 실제 컬럼 정의는 `app.py`의 `init_institution_db()` 및 관련 `_ensure_*` 헬퍼를 참고.

## 주요 라우트 영역

라우트 전체 목록은 `app.py`에서 `@app.route` 그렙으로 확인. 큰 영역은 다음과 같음:

- **인증/기관**: `/login`, `/logout`, `/select_institution`, `/switch_institution`
- **연구자 랭킹**: `/researcher_ranking`, `/api/bibliometric_ranking`, `/api/researcher_score/<id>`
- **분석 모듈**: `/analysis_modules`, `/api/potential_researchers`, `/api/high_citation_potential`, `/api/collaboration_analysis`
- **연구 전략**: `/research_strategy`, `/api/research_trajectory`, `/api/societal_impact`, `/api/strategic_portfolio`
- **연구분야 분석**: `/field_analysis`, `/strategic_field_analysis`, `/api/strategic_field_*`
- **세계대학 랭킹**: `/world_ranking`, `/api/world_ranking_metrics`
- **AI 분석**: `/api/ai_analysis`, `/api/ai_analysis_cache`
- **점수 프리셋**: `/api/scoring_presets` (CRUD)
- **설문**: `/survey`, `/survey/analysis`
- **관리자**: `/admin`, `/admin/dashboard`, `/admin/settings`, `/admin/researchers`, `/admin/research_fields`, `/admin/institutions`, `/admin/snapshots`

## 배포 환경

### 로컬 개발
```bash
GCS_SYNC_DISABLED=1 python app.py
# http://127.0.0.1:57769  (PORT 환경변수로 변경 가능)
```

### 프로덕션 (GCP Cloud Run, 2026-04 도입)
- **운영 URL**: https://orap.ailibrary.kr
- **GCP 프로젝트**: `ailibrary-orap` (asia-northeast1)
- **컨테이너**: `Dockerfile` 기반, gunicorn 1 worker × 4 threads
- **인스턴스**: min=1 / max=1 (24시간 운영, SQLite 동시쓰기 충돌 방지)
- **메모리**: 2Gi RAM, 2 vCPU
- **DB 영속성**: `gcs_sync.py`가 GCS 버킷 `ailibrary-orap-data`와 동기화
  - 시작 시: 모든 DB 다운로드
  - `users.db`: 5초 폴링 + 즉시 업로드 (write-through)
  - 기관 DB: 60초 안정화 + 5분 일괄 업로드
  - SIGTERM 시: 최종 업로드
- **배포**: `./deploy.sh`
- 운영 명령·비용 등은 [`CLAUDE.md`](CLAUDE.md) 참고

## 확장 계획

### 단기
1. Database Lock 이슈 해결
2. 에러 처리 강화
3. `app.py` 단일 파일을 Blueprint로 분할

### 중기
1. PostgreSQL 마이그레이션
2. 캐싱 시스템 도입
3. API 문서화

## 보안 고려사항

1. **입력 검증**: 파일 업로드 시 확장자 및 크기 제한
2. **SQL 인젝션 방지**: 파라미터화된 쿼리 사용
3. **세션 관리**: Flask 세션 보안 설정
4. **파일 권한**: 업로드 파일의 적절한 권한 설정

## 모니터링 및 로깅

1. **애플리케이션 로그**: Flask 기본 로깅
2. **에러 추적**: 예외 발생 시 상세 로그 기록
3. **성능 모니터링**: 쿼리 실행 시간 추적
4. **사용자 활동**: 업로드 및 분석 이력 기록