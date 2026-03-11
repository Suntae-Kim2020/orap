# PythonAnywhere 배포 가이드

## 1. 파일 업로드

### 방법 A: Git 사용 (권장)
```bash
# PythonAnywhere Bash 콘솔에서
cd ~
git clone https://github.com/your-repo/orap.git
```

### 방법 B: 직접 업로드
1. PythonAnywhere Files 탭에서 `/home/USERNAME/orap` 디렉토리 생성
2. 다음 파일들 업로드:
   - `app.py`
   - `requirements.txt`
   - `jbnu.db`
   - `korea.db`
   - `templates/` 폴더 전체
   - `static/` 폴더 전체 (있는 경우)

## 2. 가상환경 설정

PythonAnywhere Bash 콘솔에서:
```bash
cd ~/orap
mkvirtualenv --python=/usr/bin/python3.10 orap-venv
pip install -r requirements.txt
```

## 3. 웹 앱 생성

1. **Web** 탭 클릭
2. **Add a new web app** 클릭
3. **Manual configuration** 선택
4. **Python 3.10** 선택

## 4. WSGI 설정

Web 탭에서 **WSGI configuration file** 링크 클릭 후, 내용을 다음으로 교체:

```python
import sys
import os

# 프로젝트 경로 (USERNAME을 실제 사용자명으로 변경)
project_home = '/home/USERNAME/orap'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 환경 변수 설정
os.environ['PYTHONANYWHERE'] = '1'

from app import app as application
```

## 5. 가상환경 경로 설정

Web 탭에서 **Virtualenv** 섹션:
```
/home/USERNAME/.virtualenvs/orap-venv
```

## 6. 정적 파일 설정 (선택사항)

Web 탭에서 **Static files** 섹션:
- URL: `/static/`
- Directory: `/home/USERNAME/orap/static`

## 7. 웹 앱 리로드

**Reload** 버튼 클릭

## 8. 접속

`https://USERNAME.pythonanywhere.com` 에서 확인

---

## 문제 해결

### DB 권한 오류
```bash
chmod 644 ~/orap/*.db
```

### 로그 확인
Web 탭에서 **Error log** 링크 클릭

### 패키지 설치 오류
```bash
workon orap-venv
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 주의사항

1. **무료 계정 제한**:
   - CPU 시간 제한 있음
   - 3개월마다 재활성화 필요

2. **DB 파일 크기**:
   - jbnu.db: ~75MB
   - korea.db: ~172MB
   - 무료 계정 디스크 할당량 확인 필요 (512MB)

3. **업데이트 시**:
   - 파일 수정 후 반드시 **Reload** 버튼 클릭
