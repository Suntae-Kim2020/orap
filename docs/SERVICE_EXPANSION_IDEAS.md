# ORAP 서비스 확장 아이디어

> 작성일: 2026-01-25
> 기반 데이터: rawData 폴더 분석 결과

---

## 1. 현재 서비스 현황

### 기존 ORAP 기능
| 기능 | 설명 |
|------|------|
| 분석방 관리 | 연도/기간별 분석 공간 생성 |
| 데이터 업로드 | CSV/Excel 파일 업로드 (Scopus 데이터) |
| 1단계 분석 | 가중치 기반 우수논문 필터링 (Top 1%, 10%, 25%, SDGs, 국제협력) |
| 2단계 분석 | 정량 지표 기반 분석 (저널 영향력 45%, 논문 성과 45%, 사회적 영향 10%) |
| 주제 분포 분석 | ASJC, QS Subject Area, THE Field 분류 |
| 데이터 다운로드 | CSV/Excel 형식 지원 |

### 기술 스택
- Backend: Flask 3.1.2 (Python 3.9)
- Database: SQLite 3
- Frontend: Bootstrap 5, JavaScript
- Deployment: Google Cloud Run

---

## 2. rawData 분석 결과

### 2.1 데이터 파일 목록

#### 기본 논문 데이터
| 파일명 | 레코드 수 | 설명 |
|--------|-----------|------|
| Publications_at_Jeonbuk_National_University_2020_-_2025.csv | 14,716 | 전체 논문 |
| Publications_..._linked_to_a_Funding_Body_2020_-_2025.csv | 10,864 | 연구비 연계 논문 |

#### 저자 데이터
| 파일명 | 레코드 수 | 설명 |
|--------|-----------|------|
| All_Authors_Jeonbuk+National+University_2015-2026_20260125.csv | 9,437 | 전체 저자 (2015-2026) |
| Top_500_authors,_by_Scholarly_Output.csv | 500 | 상위 500 저자 |

**저자 데이터 컬럼:**
- Name, Scholarly Output, Most recent publication
- Citations, Citations per Publication, Field-Weighted Citation Impact
- h-index, Output in Top 10% Citation Percentiles
- Scopus author ID, ORCID

#### 저널 등급별 논문
| 파일명 | 레코드 수 | 설명 |
|--------|-----------|------|
| ..._top_10__journals_by_CiteScore_2020_-_2025.csv | 4,787 | Top 10% 저널 |
| ..._top_25__journals_by_CiteScore_2020_-_2025.csv | 8,714 | Top 25% 저널 |
| ..._top_26-50__journals_by_CiteScore_2020_-_2025.csv | 3,413 | Top 26-50% 저널 |
| ..._top_51-75__journals_by_CiteScore_2020_-_2025.csv | 1,324 | Top 51-75% 저널 |
| ..._top_76-100%_journals_by_CiteScore_2020_-_2025.csv | ~800 | Top 76-100% 저널 |
| ..._top_10__most_cited_publications_worldwide_2020_-_2025.csv | 1,671 | 세계 상위 10% 인용 논문 |

#### 협력 유형별 논문
| 파일명 | 레코드 수 | 설명 |
|--------|-----------|------|
| ..._with_international_collaboration_2020_-_2025.csv | 4,747 | 국제 협력 |
| ..._with_national_collaboration_2020_-_2025.csv | 6,331 | 국내 협력 |
| ..._with_institutional_collaboration_2020_-_2025.csv | 3,226 | 기관내 협력 |
| ..._with_a_single_author_2020_-_2025.csv | ~400 | 단독 저자 |

#### 소속 유형별 논문
| 파일명 | 레코드 수 | 설명 |
|--------|-----------|------|
| ..._with_academic_only_affiliation_2020_-_2025.csv | 10,230 | 학술 기관만 |
| ..._with_both_academic_and_corporate_affiliation_2020_-_2025.csv | 1,070 | 산학 협력 |
| ..._with_both_academic_and_government_affiliation_2020_-_2025.csv | 3,314 | 관학 협력 |
| ..._with_both_academic_and_medical_affiliation_2020_-_2025.csv | ~900 | 의학 협력 |
| ..._with_both_academic_and_other_affiliation_2020_-_2025.csv | ~600 | 기타 협력 |
| ..._without_academic_and_corporate_affiliation_2020_-_2025.csv | 13,668 | 기업 협력 제외 |

#### 특정 기관 공동연구
| 파일명 | 설명 |
|--------|------|
| ..._co-authored_by_..._and_Seoul_National_University_2020_-_2025.csv | 서울대 공동연구 |
| ..._co-authored_by_..._and_Yonsei_University_2020_-_2025.csv | 연세대 공동연구 |
| ..._co-authored_by_..._and_Korea_University_2020_-_2025.csv | 고려대 공동연구 |
| ..._co-authored_by_..._and_Sungkyunkwan_University_2020_-_2025.csv | 성균관대 공동연구 |
| ..._co-authored_by_..._and_Pusan_National_University_2020_-_2025.csv | 부산대 공동연구 |
| ..._co-authored_by_..._and_Chonnam_National_University_2020_-_2025.csv | 전남대 공동연구 |
| ..._co-authored_by_..._and_Chungbuk_National_University_2020_-_2025.csv | 충북대 공동연구 |
| ..._co-authored_by_..._and_Kyungpook_National_University_2020_-_2025.csv | 경북대 공동연구 |
| ..._co-authored_by_..._and_Samsung_2020_-_2025.csv | 삼성 공동연구 |

#### 특허 데이터
| 파일명 | 레코드 수 | 설명 |
|--------|-----------|------|
| Patents.csv | 514 | 논문 인용 특허 |

**특허 데이터 컬럼:**
- Title, Inventors, Applicants/Owners
- Publication year of patents, Patent office
- Cited Scholarly Outputs (인용된 논문 수)
- Abstract (특허 링크)

#### 통계/요약 데이터
| 파일명 | 설명 |
|--------|------|
| Publications_by_SDG_-_Jeonbuk_National_University.csv | SDG별 논문 통계 |
| Publications_by_Subject_Area_2020_2025.csv | 분야별 논문 통계 |
| Outputs_in_Top_Citation_Percentiles_2020_2025.csv | 상위 인용 퍼센타일 통계 |

---

### 2.2 SDG 데이터 상세

| SDG | 논문 수 | FWCI | 인용 수 |
|-----|---------|------|---------|
| SDG 3: Good Health and Well-being | 2,735 | 1.19 | 36,170 |
| SDG 7: Affordable and Clean Energy | 1,251 | 1.78 | 30,299 |
| SDG 9: Industry, Innovation and Infrastructure | 423 | 1.29 | 6,399 |
| SDG 6: Clean Water and Sanitation | 326 | 1.45 | 7,483 |
| SDG 13: Climate Action | 273 | 1.50 | 4,909 |
| SDG 12: Responsible Consumption and Production | 231 | 0.99 | 3,554 |
| SDG 2: Zero Hunger | 220 | 1.05 | 2,154 |
| SDG 8: Decent Work and Economic Growth | 169 | 1.41 | 2,068 |
| SDG 11: Sustainable Cities and Communities | 139 | 1.38 | 2,279 |
| SDG 4: Quality Education | 88 | 0.73 | 460 |
| SDG 10: Reduced Inequality | 70 | 1.15 | 696 |
| SDG 5: Gender Equality | 34 | 0.62 | 114 |
| SDG 1: No Poverty | 33 | 0.72 | 163 |

**강점 분야:** SDG 7 (에너지), SDG 3 (건강), SDG 6 (물/위생)

---

### 2.3 Top Citation Percentiles 현황

| 지표 | 전체 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|------|------|------|------|------|------|------|------|
| Top 1% 논문 수 | 125 | 13 | 29 | 21 | 26 | 15 | 21 |
| Top 1% 비율 | 0.9% | 0.6% | 1.2% | 0.9% | 1.0% | 0.6% | 0.8% |
| Top 5% 논문 수 | 760 | 119 | 121 | 130 | 140 | 133 | 117 |
| Top 5% 비율 | 5.2% | 5.5% | 5.0% | 5.3% | 5.5% | 5.3% | 4.5% |
| Top 10% 논문 수 | 1,649 | 243 | 265 | 282 | 304 | 284 | 271 |
| Top 10% 비율 | 11.2% | 11.1% | 10.9% | 11.6% | 12.0% | 11.3% | 10.5% |
| Top 25% 논문 수 | 4,299 | 643 | 684 | 714 | 751 | 747 | 760 |
| Top 25% 비율 | 29.3% | 29.5% | 28.0% | 29.3% | 29.7% | 29.6% | 29.5% |

---

## 3. 서비스 확장 아이디어

### 3.1 연구자 분석 모듈 (Author Analytics)

**활용 데이터:**
- All_Authors_Jeonbuk+National+University_2015-2026_20260125.csv
- Top_500_authors,_by_Scholarly_Output.csv

**주요 기능:**

| 기능 | 설명 | 활용 지표 |
|------|------|-----------|
| 연구자 프로필 | 개인별 성과 대시보드 | h-index, FWCI, 논문수, 인용수 |
| 성과 랭킹 | 분야별/학과별 Top 연구자 | Scholarly Output, Citations per Publication |
| 연구 트렌드 | 개인별 연간 성과 추이 | Most recent publication, Output growth |
| 협력 네트워크 | 공동 저자 관계 시각화 | Scopus Author IDs 연계 |
| 벤치마킹 | 동일 분야 타 연구자 비교 | FWCI, Top 10% 비율 |

**예상 화면:**
```
┌─────────────────────────────────────────────────────┐
│ 연구자 분석: 김OO 교수                               │
├─────────────────────────────────────────────────────┤
│ h-index: 78  │  FWCI: 1.78  │  총 논문: 463        │
│ 총 인용: 12,094  │  Top 10% 논문: 143 (30.9%)      │
├─────────────────────────────────────────────────────┤
│ [연간 논문 수 차트]  [인용 추이 차트]                 │
├─────────────────────────────────────────────────────┤
│ 주요 협력 연구자: 이OO, 박OO, ...                    │
└─────────────────────────────────────────────────────┘
```

---

### 3.2 연구 협력 네트워크 분석

**활용 데이터:**
- 국제/국내/기관 협력 파일들
- 특정 기관 공동연구 파일들 (서울대, 연세대, 삼성 등)

**주요 기능:**

| 기능 | 설명 |
|------|------|
| 협력 지도 | 국가별/기관별 공동연구 현황 시각화 |
| 협력 기관 랭킹 | Top 협력 기관 목록 및 성과 비교 |
| 협력 효과 분석 | 협력 유형별 FWCI, 인용수 비교 |
| 협력 트렌드 | 연도별 협력 패턴 변화 |
| 잠재 파트너 추천 | 분야별 협력 확대 가능 기관 |

**협력 유형별 비교 분석:**
```
협력 유형          │ 논문 수 │ 평균 FWCI │ 평균 인용수
──────────────────┼─────────┼───────────┼───────────
국제 협력          │ 4,747   │ TBD       │ TBD
국내 협력          │ 6,331   │ TBD       │ TBD
기관내 협력        │ 3,226   │ TBD       │ TBD
산학 협력          │ 1,070   │ TBD       │ TBD
관학 협력          │ 3,314   │ TBD       │ TBD
```

---

### 3.3 특허 연계 분석 (Patent Impact)

**활용 데이터:**
- Patents.csv (514건)

**주요 기능:**

| 기능 | 설명 |
|------|------|
| 기술이전 성과 | 논문 → 특허 연계 현황 대시보드 |
| 고영향력 논문 | 특허에 가장 많이 인용된 논문 Top 100 |
| 산업 분야 매핑 | 어떤 산업에서 활용되는지 분석 |
| 특허청별 분포 | US, WIPO, KR 등 특허 출원 현황 |
| 시계열 분석 | 연도별 특허 인용 추이 |

**현재 데이터 하이라이트:**
- 총 514건의 특허가 전북대 논문 인용
- 최다 인용 특허: COVID-19 관련 바이오센서 (1,712회 인용)
- 주요 특허청: US, WIPO, KR

---

### 3.4 SDG 대시보드 (UN 지속가능발전목표)

**활용 데이터:**
- Publications_by_SDG_-_Jeonbuk_National_University.csv
- SDG 태그된 개별 논문들

**주요 기능:**

| 기능 | 설명 |
|------|------|
| SDG 기여도 | 17개 목표별 논문 수, FWCI, 인용수 |
| 강점 분야 | 상위 SDG 하이라이트 |
| 연간 트렌드 | SDG별 연구 성장 추이 |
| 세부 분석 | SDG별 Top 논문, Top 연구자 |
| 벤치마킹 | 타 대학 대비 SDG 성과 비교 |

**예상 대시보드:**
```
┌─────────────────────────────────────────────────────┐
│ SDG 연구 기여도 대시보드                             │
├─────────────────────────────────────────────────────┤
│ [SDG 17개 목표 아이콘 + 논문수 표시]                 │
├─────────────────────────────────────────────────────┤
│ 강점 분야 Top 3:                                    │
│ 1. SDG 3 (건강) - 2,735편, FWCI 1.19               │
│ 2. SDG 7 (에너지) - 1,251편, FWCI 1.78             │
│ 3. SDG 6 (물/위생) - 326편, FWCI 1.45              │
└─────────────────────────────────────────────────────┘
```

---

### 3.5 연구비 성과 분석

**활용 데이터:**
- Publications_at_Jeonbuk_National_University_linked_to_a_Funding_Body_2020_-_2025.csv (10,864건)

**주요 기능:**

| 기능 | 설명 |
|------|------|
| 연구비 대비 성과 | Funding → 논문 → 인용 흐름 분석 |
| 지원 기관별 분석 | NRF, 산업부 등 지원 기관별 성과 |
| 분야별 펀딩 현황 | 어떤 분야에 연구비 집중? |
| ROI 지표 | 연구비 투입 대비 논문/특허 산출 |
| 미지원 논문 비교 | 연구비 지원 vs 미지원 논문 성과 비교 |

**주요 지표:**
- 연구비 연계 논문: 10,864건 (전체의 약 74%)
- 연구비 연계 논문 평균 FWCI: TBD
- 연구비 연계 논문 평균 인용수: TBD

---

### 3.6 산학관 협력 분석

**활용 데이터:**
- academic+corporate, academic+government, academic+medical 파일들

**주요 기능:**

| 기능 | 설명 |
|------|------|
| 협력 유형별 성과 | 산학, 관학, 의학 협력 비교 |
| 기업 협력 현황 | 어떤 기업과 공동연구? (삼성 등) |
| 정부 협력 현황 | 정부 출연연 협력 성과 |
| 기술사업화 잠재력 | 산학 논문 중 특허 연계 비율 |
| 협력 추천 | 분야별 산학협력 확대 가능 기업 |

---

### 3.7 Top Citation Percentiles 분석

**활용 데이터:**
- Outputs_in_Top_Citation_Percentiles_2020_2025.csv

**주요 기능:**

| 기능 | 설명 |
|------|------|
| 연도별 추이 | Top 1%, 5%, 10%, 25% 논문 비율 변화 |
| 목표 설정 | "Top 10% 논문 비율 15% 달성" 등 KPI |
| 분야별 비교 | 어느 분야가 상위 인용 비율 높은지 |
| FWCI 임계값 | 각 퍼센타일 진입 FWCI 기준 |
| 예측 모델 | 논문별 상위 퍼센타일 진입 가능성 |

---

## 4. 구현 우선순위

| 순위 | 모듈 | 난이도 | 기대 효과 | 이유 |
|------|------|--------|-----------|------|
| 1 | **연구자 분석** | 중 | 높음 | 교수 성과 평가에 즉시 활용 가능 |
| 2 | **SDG 대시보드** | 하 | 높음 | 대학 평가/홍보에 필수, 데이터 정리됨 |
| 3 | **Top Citation 분석** | 하 | 중 | 요약 데이터 활용, 빠른 구현 가능 |
| 4 | **협력 네트워크** | 상 | 높음 | 연구 전략 수립에 핵심, 시각화 필요 |
| 5 | **특허 연계** | 중 | 중 | 기술사업화 성과 측정, 차별화 요소 |
| 6 | **연구비 성과** | 중 | 높음 | 연구처 핵심 관심사 |
| 7 | **산학관 협력** | 중 | 중 | 산학협력 전략 수립 |

---

## 5. 기술 고려사항

### 5.1 데이터베이스 스키마 확장

```sql
-- 저자 테이블
CREATE TABLE author (
    author_id INTEGER PRIMARY KEY,
    scopus_author_id TEXT UNIQUE,
    name TEXT,
    orcid TEXT,
    h_index INTEGER,
    fwci REAL,
    total_citations INTEGER,
    scholarly_output INTEGER,
    affiliation TEXT
);

-- 특허 테이블
CREATE TABLE patent (
    patent_id INTEGER PRIMARY KEY,
    title TEXT,
    inventors TEXT,
    applicants TEXT,
    publication_year INTEGER,
    patent_office TEXT,
    cited_outputs INTEGER,
    abstract_url TEXT
);

-- 논문-특허 연계 테이블
CREATE TABLE publication_patent (
    publication_id INTEGER,
    patent_id INTEGER,
    FOREIGN KEY (publication_id) REFERENCES publication(record_id),
    FOREIGN KEY (patent_id) REFERENCES patent(patent_id)
);

-- SDG 통계 테이블
CREATE TABLE sdg_stats (
    sdg_id INTEGER PRIMARY KEY,
    sdg_name TEXT,
    scholarly_output INTEGER,
    fwci REAL,
    citation_count INTEGER,
    year INTEGER
);
```

### 5.2 프론트엔드 고려사항

- 차트 라이브러리: Chart.js 또는 ECharts
- 네트워크 시각화: D3.js 또는 vis.js
- 지도 시각화: Leaflet.js
- 대시보드 레이아웃: Bootstrap Grid + Card 컴포넌트

### 5.3 성능 고려사항

- 대용량 데이터 처리: Pandas chunking
- 캐싱: Redis 또는 Flask-Caching
- 비동기 처리: Celery (대용량 분석)
- 인덱싱: SQLite → PostgreSQL 마이그레이션 권장

---

## 6. 다음 단계

1. **우선순위 확정**: 어떤 모듈부터 개발할지 결정
2. **데이터 업로드**: rawData 파일들을 DB에 적재
3. **스키마 설계**: 확장 테이블 설계 및 생성
4. **UI/UX 설계**: 와이어프레임 작성
5. **개발 시작**: 단계별 구현

---

## 7. 데이터 관리 화면 개발 (향후 과제)

> 현재는 Python 스크립트로 수동 적재. 운영 환경에서는 웹 UI 필요.

### 7.1 필요한 업로드/업데이트 화면

| 화면 | 대상 테이블 | 기능 | 우선순위 |
|------|-------------|------|----------|
| 저자 데이터 관리 | `author` | Scopus 저자 CSV 업로드/갱신 | 높음 |
| 특허 데이터 관리 | `patent` | 특허 CSV 업로드/갱신 | 중간 |
| SDG 통계 관리 | `sdg_summary` | SDG 요약 데이터 업로드 | 중간 |
| 분야별 통계 관리 | `subject_area_summary` | Subject Area 데이터 업로드 | 중간 |
| 협력 기관 관리 | `collaboration_institution` | 기관별 통계 업로드 | 낮음 |
| 인용 퍼센타일 관리 | `citation_percentile_summary` | 연도별 퍼센타일 데이터 업로드 | 낮음 |
| 논문 플래그 업데이트 | `publication` | 협력 유형별 CSV로 플래그 일괄 업데이트 | 높음 |

### 7.2 공통 기능 요구사항

#### 업로드 기능
- [ ] 파일 선택 및 드래그앤드롭 지원
- [ ] 파일 형식 검증 (CSV, Excel)
- [ ] 파일 크기 제한 (100MB)
- [ ] 인코딩 자동 감지 (UTF-8, CP949)

#### 미리보기 기능
- [ ] 업로드 전 데이터 미리보기 (상위 10행)
- [ ] 컬럼 매핑 확인/수정
- [ ] 헤더 행 위치 자동 감지
- [ ] 데이터 유효성 검사 결과 표시

#### 적재 옵션
- [ ] 기존 데이터 처리 방식 선택
  - 전체 교체 (REPLACE)
  - 병합 (UPSERT)
  - 추가만 (INSERT)
- [ ] 중복 키 처리 방식 설정
- [ ] 배치 크기 설정

#### 진행 상태
- [ ] 실시간 진행률 표시
- [ ] 처리된 레코드 수 표시
- [ ] 오류 발생 시 상세 로그
- [ ] 취소 기능

#### 이력 관리
- [ ] 업로드 이력 테이블 (`data_upload_history`)
- [ ] 업로드 일시, 파일명, 레코드 수, 사용자 기록
- [ ] 이전 버전 데이터 백업
- [ ] 롤백 기능 (최근 N회)

### 7.3 화면별 상세 설계

#### 저자 데이터 관리 화면
```
┌─────────────────────────────────────────────────────────────┐
│ 저자 데이터 관리                                             │
├─────────────────────────────────────────────────────────────┤
│ 현재 상태: 9,391명 등록 | 최종 업데이트: 2026-01-25         │
├─────────────────────────────────────────────────────────────┤
│ [파일 선택] [업로드]                                         │
│                                                             │
│ ┌─ 미리보기 ─────────────────────────────────────────────┐ │
│ │ Name          | Scholarly Output | h-index | FWCI     │ │
│ │ Kim, Eun-joo  | 463              | 78      | 1.78     │ │
│ │ Lee, Joonghee | 380              | 103     | 2.77     │ │
│ │ ...                                                    │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                             │
│ 적재 옵션: ○ 전체 교체  ● 병합  ○ 추가만                     │
│                                                             │
│ [적재 시작]                                                  │
├─────────────────────────────────────────────────────────────┤
│ 업로드 이력                                                  │
│ 2026-01-25 14:30 | All_Authors_...csv | 9,391건 | 성공     │
│ 2026-01-20 10:15 | All_Authors_...csv | 9,200건 | 성공     │
└─────────────────────────────────────────────────────────────┘
```

#### 논문 플래그 일괄 업데이트 화면
```
┌─────────────────────────────────────────────────────────────┐
│ 논문 플래그 일괄 업데이트                                     │
├─────────────────────────────────────────────────────────────┤
│ 플래그 선택: [▼ is_funded - 연구비 지원 연계]                │
│                                                             │
│ [파일 선택] Publications_linked_to_Funding_Body.csv         │
│                                                             │
│ 매칭 컬럼: EID                                               │
│ 파일 내 EID 수: 10,842                                       │
│ DB 매칭 예상: 10,500 (97%)                                   │
│                                                             │
│ [플래그 업데이트 실행]                                        │
│                                                             │
│ ┌─ 현재 플래그 현황 ─────────────────────────────────────┐ │
│ │ is_funded: 20,660건                                    │ │
│ │ is_top_cited: 3,268건                                  │ │
│ │ is_national_collab: 11,918건                           │ │
│ │ ...                                                    │ │
│ └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 7.4 데이터베이스 스키마 추가 (이력 관리용)

```sql
-- 데이터 업로드 이력 테이블
CREATE TABLE data_upload_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,           -- 대상 테이블명
    file_name TEXT NOT NULL,            -- 업로드 파일명
    file_size INTEGER,                  -- 파일 크기 (bytes)
    record_count INTEGER DEFAULT 0,     -- 처리된 레코드 수
    insert_count INTEGER DEFAULT 0,     -- 신규 삽입 수
    update_count INTEGER DEFAULT 0,     -- 업데이트 수
    error_count INTEGER DEFAULT 0,      -- 오류 수
    upload_mode TEXT,                   -- 'replace', 'upsert', 'insert'
    status TEXT DEFAULT 'pending',      -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,                 -- 오류 메시지
    started_at TEXT,                    -- 시작 시간
    completed_at TEXT,                  -- 완료 시간
    created_at TEXT DEFAULT (datetime('now'))
);

-- 백업 테이블 (롤백용)
CREATE TABLE data_backup (
    backup_id INTEGER PRIMARY KEY AUTOINCREMENT,
    history_id INTEGER,                 -- 연관 업로드 이력
    table_name TEXT NOT NULL,           -- 백업 대상 테이블
    backup_data BLOB,                   -- 백업 데이터 (JSON 또는 압축)
    record_count INTEGER,               -- 백업 레코드 수
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (history_id) REFERENCES data_upload_history(history_id)
);
```

### 7.5 API 엔드포인트 설계

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/admin/data-management` | 데이터 관리 메인 화면 |
| GET | `/admin/data-management/<table_name>` | 테이블별 관리 화면 |
| POST | `/api/admin/upload/<table_name>` | 데이터 업로드 |
| GET | `/api/admin/upload/preview` | 업로드 미리보기 |
| POST | `/api/admin/upload/execute` | 업로드 실행 |
| GET | `/api/admin/upload/progress/<task_id>` | 진행 상태 조회 |
| GET | `/api/admin/upload/history/<table_name>` | 업로드 이력 조회 |
| POST | `/api/admin/upload/rollback/<history_id>` | 롤백 실행 |
| POST | `/api/admin/flags/update` | 논문 플래그 일괄 업데이트 |

### 7.6 개발 우선순위

1. **1단계**: 저자 데이터 관리 + 논문 플래그 업데이트 (핵심 기능)
2. **2단계**: 특허/SDG/분야별 통계 관리 (보조 데이터)
3. **3단계**: 이력 관리 + 롤백 기능 (안정성 강화)
4. **4단계**: 권한 관리 + 감사 로그 (보안 강화)

---

## 8. 완료된 작업 (2026-01-25)

### 8.1 DB 스키마 확장
- [x] `publication` 테이블에 9개 플래그 컬럼 추가
- [x] `author` 테이블 생성 (16개 컬럼)
- [x] `patent` 테이블 생성 (10개 컬럼)
- [x] `sdg_summary` 테이블 생성 (8개 컬럼)
- [x] `subject_area_summary` 테이블 생성 (13개 컬럼)
- [x] `citation_percentile_summary` 테이블 생성 (7개 컬럼)
- [x] `collaboration_institution` 테이블 생성 (10개 컬럼)
- [x] `publication_author` 테이블 생성 (4개 컬럼)

### 8.2 데이터 적재 완료
| 테이블 | 레코드 수 |
|--------|-----------|
| author | 9,391 |
| patent | 515 |
| sdg_summary | 16 |
| subject_area_summary | 345 |
| citation_percentile_summary | 28 |
| collaboration_institution | 9 |

### 8.3 플래그 업데이트 완료
| 플래그 | 레코드 수 |
|--------|-----------|
| is_top_cited | 3,268 |
| is_funded | 20,660 |
| is_national_collab | 11,918 |
| is_institutional_collab | 6,068 |
| is_academic_only | 19,220 |
| is_academic_government | 6,188 |
| is_academic_corporate | 1,978 |
| is_single_author | 842 |
| is_academic_medical | 702 |

---

*이 문서는 ORAP 서비스 확장을 위한 초기 기획 문서입니다.*
*최종 업데이트: 2026-01-25*
