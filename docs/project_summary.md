# JBNU ORAP 프로젝트 요약

## 프로젝트 개요

**JBNU ORAP (Jeonbuk National University - Office of Research Analytics Platform)**는 전북대학교의 연구 성과를 분석하고 전략적 의사결정을 지원하는 웹 기반 플랫폼입니다.

- **기술 스택**: Python Flask + SQLite + Bootstrap 5 + Jinja2
- **데이터 소스**: Scopus 등재 논문 및 저자 데이터 (jbnu.db)
- **대상**: 전북대학교 소속 연구자 및 연구 관리자

---

## 주요 메뉴 구성

| 메뉴 | 설명 |
|------|------|
| Home | 메인 대시보드 |
| 분석방 관리 | 분석 프로젝트(Room) 생성 및 관리 |
| 분석 | 기본 논문/연구자 분석 |
| 연구자 랭킹 | 전북대 연구자 순위 |
| 분석 모듈 | 잠재연구자 발굴, 고인용유도대상, 공동연구분석 |
| 연구 전략 | 연구궤적, 사회적영향력, 전략포트폴리오 분석 |
| **학문분야분석** | ASJC 분야별 비교 분석 (신규) |
| 도움말 | 우수논문 후보추출방법 안내 |

---

## 학문분야분석 기능 (신규 구현)

### 목적
ASJC(All Science Journal Classification) 학문분야를 **복수 선택**하여 분야 간 연구 성과를 비교 분석

### 주요 기능

#### 1. 분야 선택 인터페이스
- 검색형 체크박스 목록 (분야명 + 논문수 표시)
- 선택된 분야 뱃지 표시 (클릭 시 해제)
- 최소 5편 이상 논문이 있는 분야만 표시

#### 2. 기간 필터
- 전체 / 최근 3년 / 최근 5년 프리셋
- 직접 입력 (시작~종료 연도)

#### 3. 종합 현황 탭
| 지표 | 설명 |
|------|------|
| 논문수 | 해당 분야 논문 총 수 |
| 총 인용수 | 피인용 횟수 합계 |
| 평균 FWCI | Field-Weighted Citation Impact |
| 국제협력(%) | 국제 공저 논문 비율 |
| Top 저널(%) | 상위 10% 저널 논문 비율 |
| Top 피인용(%) | 상위 피인용 논문 비율 |
| SDG(%) | UN SDG 관련 논문 비율 |
| 산학협력(%) | 기업 공저 논문 비율 |
| 특허인용(%) | 특허에 인용된 논문 비율 |
| 전략 등급 | 핵심강점/성장분야/규모우위/육성필요 |

**전략 등급 기준:**
- 핵심 강점: FWCI ≥ 1.5 AND 국제비율 ≥ 40%
- 성장 분야: FWCI ≥ 1.0
- 규모 우위: 논문수 ≥ 50편
- 육성 필요: 그 외

#### 4. 주요 연구자 탭
- 선택된 분야에 논문을 발표한 전북대 연구자 목록
- 분야별 필터 지원
- 연구자별 분야 논문수, FWCI, h-index, 국제협력 수 표시

#### 5. 연도 추이 탭
- 분야별 연도별 논문수 및 평균 FWCI 추이
- Canvas 기반 바 차트 시각화 (논문수/FWCI 전환 가능)
- 테이블 + 차트 동시 제공

#### 6. 공통 기능
- 컬럼 클릭 정렬 (오름/내림차순)
- CSV 다운로드 (각 탭별)

---

## 파일 구조

```
/Users/kimsuntae/orap/
├── app.py                          # Flask 메인 애플리케이션 (4900+ lines)
├── jbnu.db                         # SQLite 데이터베이스
├── templates/
│   ├── base.html                   # 공통 레이아웃 (네비게이션)
│   ├── field_analysis.html         # 학문분야분석 페이지 (신규)
│   ├── research_strategy.html      # 연구 전략 페이지
│   ├── analysis_modules.html       # 분석 모듈 페이지
│   └── ...                         # 기타 템플릿
└── docs/
    └── project_summary.md          # 이 문서
```

---

## API 엔드포인트

### 학문분야분석 API

| 엔드포인트 | 설명 |
|------------|------|
| `GET /field_analysis` | 페이지 렌더링 |
| `GET /api/field_list` | 분야 목록 (이름, 논문수) |
| `GET /api/field_analysis/overview` | 분야별 종합 지표 |
| `GET /api/field_analysis/researchers` | 분야별 주요 연구자 |
| `GET /api/field_analysis/trend` | 분야별 연도 추이 |

**공통 파라미터:**
- `fields`: 분야명 (|||로 구분)
- `year_from`, `year_to`: 기간 필터

---

## 데이터베이스 주요 테이블

### publication
| 컬럼 | 설명 |
|------|------|
| all_science_journal_classification_asjc_field_name | ASJC 분야명 (|나 ,로 구분) |
| field_weighted_citation_impact | FWCI |
| is_international | 국제 협력 여부 |
| is_top_cited | 상위 피인용 여부 |
| is_1 | 상위 10% 저널 여부 |
| is_SDG | UN SDG 관련 여부 |
| is_patent_cited | 특허 인용 여부 |
| is_academic_corporate | 산학 협력 여부 |
| scopus_author_ids | 저자 Scopus ID 목록 |
| year | 발표 연도 |
| citations | 인용 수 |

### author
| 컬럼 | 설명 |
|------|------|
| scopus_author_id | Scopus 저자 ID |
| name | 저자명 |
| scholarly_output | 총 논문수 |
| citations | 총 인용수 |
| field_weighted_citation_impact | FWCI |
| h_index | h-지수 |
| primary_affiliation | 소속 기관 |

---

## 실행 방법

```bash
# 로컬 개발 서버 실행
cd /Users/kimsuntae/orap
python3 app.py

# 기본 포트: 57769
# 접속: http://localhost:57769
```

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-01-29 | 학문분야분석 메뉴 및 기능 추가 |
| - | 분석모듈, 연구전략 메뉴 구현 및 CSV 다운로드, 상세 정보 패널 추가 |
| - | Docker 배포 설정 및 최적화 |

---

*이 문서는 JBNU ORAP 프로젝트의 개요와 최근 추가된 학문분야분석 기능을 설명합니다.*
