# JBNU Publication Database

전북대학교 논문 데이터베이스 관리 및 2단계 분석 시스템

## 주요 기능

- **논문 데이터 관리**: CSV 파일 업로드를 통한 논문 데이터 관리
- **2단계 우수논문 분석**:
  - 1단계: 가중치 기반 필터링 (상위1%, 상위10%, 상위25%, SDGs, 국제협력)
  - 2단계: 정량적 수학적 분석 (저널 영향력, 논문 성과, 사회적 영향)
- **주제 분포 분석**: ASJC, QS Subject Area, THE Field 분류 시스템
- **데이터 다운로드**: CSV 및 Excel 형식 지원

## 기술 스택

- **Backend**: Flask (Python 3.9)
- **Database**: SQLite
- **Frontend**: Bootstrap 5, JavaScript
- **Deployment**: Google Cloud Run
- **CI/CD**: GitHub Actions

## 로컬 개발 환경 설정

```bash
# 저장소 클론
git clone [repository-url]
cd ORA

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 애플리케이션 실행
python app.py
```

## GCP Cloud Run 배포

### 사전 준비

1. **GCP 프로젝트 설정**
   - Google Cloud Console에서 새 프로젝트 생성
   - Cloud Run API, Artifact Registry API 활성화

2. **Artifact Registry 저장소 생성**
   ```bash
   gcloud artifacts repositories create jbnu-publication-db \
       --repository-format=docker \
       --location=asia-northeast3
   ```

3. **서비스 계정 생성**
   ```bash
   gcloud iam service-accounts create github-actions \
       --description="Service account for GitHub Actions" \
       --display-name="GitHub Actions"
   
   # 필요한 권한 부여
   gcloud projects add-iam-policy-binding PROJECT_ID \
       --member="serviceAccount:github-actions@PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/run.admin"
   
   gcloud projects add-iam-policy-binding PROJECT_ID \
       --member="serviceAccount:github-actions@PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/storage.admin"
   
   gcloud projects add-iam-policy-binding PROJECT_ID \
       --member="serviceAccount:github-actions@PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/artifactregistry.admin"
   
   # 서비스 계정 키 생성
   gcloud iam service-accounts keys create key.json \
       --iam-account=github-actions@PROJECT_ID.iam.gserviceaccount.com
   ```

### GitHub Secrets 설정

GitHub 저장소의 Settings > Secrets and variables > Actions에서 다음 시크릿을 추가:

- `GCP_PROJECT_ID`: GCP 프로젝트 ID
- `GCP_SA_KEY`: 서비스 계정 키 JSON 내용 (key.json 파일의 전체 내용)

### 수동 배포

```bash
# Docker 이미지 빌드
docker build -t gcr.io/PROJECT_ID/jbnu-publication-db .

# 이미지 푸시
docker push gcr.io/PROJECT_ID/jbnu-publication-db

# Cloud Run에 배포
gcloud run deploy jbnu-publication-db \
    --image gcr.io/PROJECT_ID/jbnu-publication-db \
    --platform managed \
    --region asia-northeast3 \
    --allow-unauthenticated
```

## 자동 배포

main 브랜치에 푸시하면 GitHub Actions를 통해 자동으로 Cloud Run에 배포됩니다.

## 환경 변수

필요에 따라 다음 환경 변수를 설정할 수 있습니다:

- `FLASK_ENV`: production (기본값)
- `PORT`: 서버 포트 (Cloud Run에서 자동 설정)

## 데이터베이스 스키마

애플리케이션이 처음 실행될 때 SQLite 데이터베이스가 자동으로 생성되며, 필요한 테이블들이 초기화됩니다.

## 기여하기

1. 이 저장소를 포크합니다
2. 기능 브랜치를 생성합니다 (`git checkout -b feature/AmazingFeature`)
3. 변경사항을 커밋합니다 (`git commit -m 'Add some AmazingFeature'`)
4. 브랜치에 푸시합니다 (`git push origin feature/AmazingFeature`)
5. Pull Request를 생성합니다

## 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다.