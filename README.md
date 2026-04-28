# JBNU ORAP

전북대학교 연구처(Office of Research Affairs Platform)용 학술성과 분석 플랫폼.

## 주요 기능

- **다기관 지원**: 기관별로 분리된 SQLite DB(`jbnu.db`, `korea.db` 등) 운영, 로그인 후 기관 선택
- **연구자 랭킹**: 계량서지학 지표(h/g/i10/m-index) 및 사용자 정의 점수 프리셋
- **분석 모듈**: 잠재 연구자, 고인용 잠재력, 공동연구 분석
- **연구 전략**: 연구 궤적, 사회적 영향, 전략 포트폴리오
- **연구분야 분석**: 일반 분야 및 키워드 기반 전략적 분야 분석
- **세계대학 랭킹 / 대학공시자료 통합**
- **AI 분석 + 캐시**, 다국어(한/영) 설문, 데이터 스냅샷 관리
- **CSV/Excel 다운로드**

## 기술 스택

- **Backend**: Flask 3.1.2 (Python 3.10+)
- **Database**: SQLite (기관별 파일 분리)
- **Frontend**: Bootstrap 5, JavaScript
- **Data**: pandas, openpyxl, xlsxwriter
- **번역**: deep-translator (Google)
- **Production WSGI**: gunicorn

## 로컬 개발 환경 설정

```bash
git clone <repository-url>
cd orap

python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

python app.py
# http://127.0.0.1:57769
```

`.env` 파일에 `PORT` 등 환경 변수 지정 가능.

## 배포

PythonAnywhere로 배포합니다. 자세한 절차는 [`DEPLOY_PYTHONANYWHERE.md`](DEPLOY_PYTHONANYWHERE.md) 참고.

## 환경 변수

- `PORT`: 서버 포트 (기본 57769)
- `PYTHONANYWHERE`: PythonAnywhere 환경에서 1로 설정 (wsgi.py에서 자동 처리)

## 데이터베이스

- 기관별 SQLite 파일 분리 (`jbnu.db`, `korea.db`, `sejong.db` 등)
- 사용자/권한/기관 매핑은 `users.db`의 `institutions` 테이블에서 관리
- 첫 실행 시 필요한 테이블이 자동 생성/마이그레이션됨

## 라이센스

MIT
