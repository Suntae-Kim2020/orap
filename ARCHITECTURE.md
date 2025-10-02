# JBNU ORAP (Office of Research Affairs Platform) 아키텍처 문서

## 프로젝트 개요

JBNU ORAP는 전북대학교 연구처에서 학술성과, 연구사업 등의 데이터를 업로드하고 분석하기 위한 웹 기반 플랫폼입니다. 연구논문의 우수성을 평가하고 상위 논문을 추출하는 2단계 분석 시스템을 제공합니다.

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
- **Database**: SQLite 3
- **Frontend**: HTML, CSS, JavaScript (Bootstrap)
- **Data Processing**: Pandas 2.3.2, NumPy 2.0.2
- **File Handling**: OpenPyXL 3.1.5, XlsxWriter 3.2.5
- **Deployment**: Gunicorn 21.2.0 (Production)

## 프로젝트 구조

```
ORA/
├── app.py                      # 메인 애플리케이션 서버
├── app_backup.py              # 백업 파일
├── requirements.txt           # Python 의존성
├── jbnu.db                   # SQLite 데이터베이스
├── README.md                 # 프로젝트 설명
├── templates/                # HTML 템플릿
│   ├── base.html            # 기본 레이아웃
│   ├── index.html           # 메인 페이지
│   ├── manage_rooms.html    # 분석방 관리
│   ├── create_room.html     # 분석방 생성
│   ├── analysis.html        # 분석 페이지
│   ├── analysis_run.html    # 분석 실행
│   ├── topic_analysis.html  # 토픽 분석
│   ├── unified_upload.html  # 통합 업로드
│   ├── help_stage1.html     # 1단계 도움말
│   └── help_stage2.html     # 2단계 도움말
├── utility_scripts/          # 유틸리티 스크립트
│   ├── analyze_csv.py       # CSV 분석
│   ├── find_empty_rows.py   # 빈 행 찾기
│   ├── sqlite_to_postgresql.py # DB 마이그레이션
│   └── migrate_to_cloudsql.py   # Cloud SQL 마이그레이션
└── .github/workflows/        # CI/CD 설정
    └── deploy.yml           # GitHub Actions 배포
```

## 데이터베이스 스키마

### 1. room 테이블 (분석방)
```sql
CREATE TABLE room (
    room_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    room_name   TEXT    NOT NULL,
    year_from   INTEGER NOT NULL,
    year_to     INTEGER NOT NULL,
    cutoff_date TEXT    NOT NULL,
    data_category TEXT  NULL,
    data_source   TEXT  NULL,
    is_paper         INTEGER DEFAULT 0,
    is_1             INTEGER DEFAULT 0,
    is_10            INTEGER DEFAULT 0,
    is_25            INTEGER DEFAULT 0,
    is_SDG           INTEGER DEFAULT 0,
    is_international INTEGER DEFAULT 0
);
```

### 2. publication 테이블 (논문 데이터)
```sql
CREATE TABLE publication (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    authors TEXT,
    year TEXT,
    scopus_source_title TEXT,
    -- Scopus 메트릭스
    snip_publication_year TEXT,
    snip_percentile_publication_year TEXT,
    citescore_publication_year TEXT,
    citescore_percentile_publication_year TEXT,
    sjr_publication_year TEXT,
    sjr_percentile_publication_year TEXT,
    field_weighted_citation_impact TEXT,
    field_weighted_view_impact TEXT,
    citations TEXT,
    views TEXT,
    -- 분류 플래그
    room_id INTEGER,
    is_1 INTEGER,           -- Top 1% 논문
    is_10 INTEGER,          -- Top 10% 논문  
    is_25 INTEGER,          -- Top 25% 논문
    is_SDG INTEGER,         -- SDGs 관련 논문
    is_international INTEGER, -- 국제공동연구 논문
    -- 점수 필드 (2단계 분석용)
    j_point REAL DEFAULT 0.0,  -- 저널 영향력 점수
    a_point REAL DEFAULT 0.0,  -- 논문 성과 점수
    s_point REAL DEFAULT 0.0,  -- 사회적 영향 점수
    t_point REAL DEFAULT 0.0   -- 총점
);
```

### 3. file_uploads 테이블 (파일 업로드 이력)
```sql
CREATE TABLE file_uploads (
    upload_id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    data_category TEXT NOT NULL,
    data_source TEXT,
    upload_date TEXT NOT NULL,
    record_count INTEGER DEFAULT 0,
    data_type TEXT,
    FOREIGN KEY (room_id) REFERENCES room (room_id)
);
```

## 주요 기능 및 API 엔드포인트

### 1. 분석방 관리
- `GET /` - 메인 페이지
- `GET /manage_rooms` - 분석방 목록 및 관리
- `GET /create_room` - 새 분석방 생성 폼
- `POST /save_room` - 분석방 저장
- `POST /update_room` - 분석방 정보 수정
- `POST /delete_room` - 분석방 삭제

### 2. 데이터 업로드
- `GET /unified_upload/<room_id>` - 통합 업로드 페이지
- `POST /upload_file` - 파일 업로드 처리
- `GET /api/progress/<task_id>` - 업로드 진행 상태 확인
- `GET /api/result/<task_id>` - 업로드 결과 조회

### 3. 분석 기능
- `GET /analysis` - 분석 페이지
- `GET /analysis_run/<room_id>` - 분석 실행 페이지
- `POST /api/extract_candidates` - 1단계 후보 추출
- `POST /api/extract_second_stage_candidates` - 2단계 후보 추출
- `POST /topic_distribution_analysis` - 토픽 분포 분석

### 4. 다운로드
- `POST /api/download_first_stage_candidates` - 1단계 결과 다운로드
- `POST /api/download_second_stage_candidates` - 2단계 결과 다운로드
- `POST /api/download_topic_analysis` - 토픽 분석 결과 다운로드

### 5. 도움말
- `GET /help/stage1` - 1단계 분석 도움말
- `GET /help/stage2` - 2단계 분석 도움말

## 분석 알고리즘

### 1단계: 기본 필터링
가중치 기반 점수 계산:
```python
score = (is_1 * weight_1) + (is_10 * weight_10) + (is_25 * weight_25) + 
        (is_SDG * weight_SDG) + (is_international * weight_international)
```

### 2단계: 정량적 분석
최고점을 받은 논문들을 대상으로 세부 메트릭 분석:

#### 저널 영향력 (45%)
- SNIP (15%): 값 정규화 + 퍼센타일 (6:4 비율)
- CiteScore (15%): 값 정규화 + 퍼센타일 (6:4 비율)  
- SJR (15%): 값 정규화 + 퍼센타일 (6:4 비율)

#### 논문 성과 (45%)
- FWCI (20%): Field-Weighted Citation Impact (최대 3.0으로 캡)
- 인용수 (10%): 로그 변환 후 Winsorization 정규화
- 조회수 블록 (10%): 조회수 + FWVI 혼합 (5:5 비율)
- Top Citation Percentiles (5%): 현재 미구현

#### 사회적 영향 (10%)
- 특허 (6%): 현재 데이터 없음
- 정책 인용 (4%): 현재 데이터 없음

### 정규화 방법
- **Winsorization**: 5th-95th 퍼센타일 기준으로 이상치 제거 후 정규화
- **로그 변환**: `log(1 + max(0, value))` 적용
- **퍼센타일 정규화**: 0-100 범위를 0-1로 변환

## 배포 환경

### 로컬 개발
```bash
python app.py
# http://127.0.0.1:5000
```

### 프로덕션 (GCP)
- Google Cloud Platform App Engine
- GitHub Actions를 통한 자동 배포
- SQLite → Cloud SQL PostgreSQL 마이그레이션 고려

## 확장 계획

### 단기
1. Database Lock 이슈 해결
2. 에러 처리 강화
3. 사용자 인증 시스템 추가

### 중기
1. PostgreSQL 마이그레이션
2. 캐싱 시스템 도입
3. API 문서화

### 장기
1. 마이크로서비스 아키텍처 전환
2. 실시간 분석 기능
3. 머신러닝 기반 예측 모델

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