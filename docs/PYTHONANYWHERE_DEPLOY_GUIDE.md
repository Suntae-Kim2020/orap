# JBNU ORAP PythonAnywhere 배포 가이드

## 사전 준비

- PythonAnywhere 계정 (무료 가입: https://www.pythonanywhere.com)
- 이 프로젝트 파일들 (ZIP으로 압축)

---

## Step 1. 프로젝트 파일 압축

로컬에서 터미널을 열고 다음 명령어 실행:

```bash
cd /Users/kimsuntae/orap
zip -r orap_deploy.zip app.py jbnu.db requirements.txt templates/
```

생성된 `orap_deploy.zip` 파일을 준비합니다.

---

## Step 2. PythonAnywhere 가입/로그인

1. https://www.pythonanywhere.com 접속
2. **Pricing & signup** 클릭
3. **Create a Beginner account** (무료) 선택
4. 계정 생성 후 로그인

---

## Step 3. 파일 업로드

1. 상단 메뉴에서 **Files** 클릭
2. **Upload a file** 버튼 클릭
3. `orap_deploy.zip` 파일 선택하여 업로드
4. 업로드 완료 확인

---

## Step 4. 콘솔에서 압축 해제

1. 상단 메뉴에서 **Consoles** 클릭
2. **Start a new console** 섹션에서 **Bash** 클릭
3. 다음 명령어 입력:

```bash
# 홈 디렉토리로 이동
cd ~

# 압축 해제
unzip orap_deploy.zip -d orap

# 확인
ls orap/
```

결과로 `app.py`, `jbnu.db`, `requirements.txt`, `templates/` 가 보여야 합니다.

---

## Step 5. 가상환경 생성 및 패키지 설치

같은 Bash 콘솔에서 계속:

```bash
# 가상환경 생성
mkvirtualenv --python=/usr/bin/python3.10 orapenv

# 가상환경 활성화 (자동으로 활성화됨)
# 프롬프트가 (orapenv) 로 시작하면 성공

# 프로젝트 폴더로 이동
cd ~/orap

# 패키지 설치
pip install flask pandas numpy openpyxl xlsxwriter
```

---

## Step 6. WSGI 파일 확인용 경로 메모

다음 정보를 메모해두세요:

| 항목 | 값 |
|------|-----|
| 사용자명 | (본인의 PythonAnywhere 사용자명) |
| 프로젝트 경로 | `/home/사용자명/orap` |
| 가상환경 경로 | `/home/사용자명/.virtualenvs/orapenv` |

---

## Step 7. 웹 앱 생성

1. 상단 메뉴에서 **Web** 클릭
2. **Add a new web app** 클릭
3. **Next** 클릭 (무료 계정은 도메인이 `사용자명.pythonanywhere.com`으로 고정)
4. **Manual configuration** 선택 (Flask 선택하지 마세요!)
5. **Python 3.10** 선택
6. **Next** 클릭

---

## Step 8. 가상환경 경로 설정

Web 설정 페이지에서:

1. **Virtualenv** 섹션 찾기
2. **Enter path to a virtualenv** 클릭
3. 다음 경로 입력:
   ```
   /home/사용자명/.virtualenvs/orapenv
   ```
   (사용자명을 본인 것으로 변경)

---

## Step 9. WSGI 파일 수정

1. **Code** 섹션에서 **WSGI configuration file** 링크 클릭
   - 경로: `/var/www/사용자명_pythonanywhere_com_wsgi.py`

2. 파일 내용을 **전체 삭제**하고 다음으로 교체:

```python
import sys
import os

# 프로젝트 경로 추가 (사용자명을 본인 것으로 변경)
project_home = '/home/사용자명/orap'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 작업 디렉토리 변경
os.chdir(project_home)

# Flask 앱 import
from app import app as application
```

3. **Save** 버튼 클릭

---

## Step 10. 소스 코드 경로 설정

Web 설정 페이지로 돌아가서:

1. **Code** 섹션에서 **Source code** 경로 설정
2. 다음 경로 입력:
   ```
   /home/사용자명/orap
   ```

3. **Working directory** 도 같은 경로로 설정:
   ```
   /home/사용자명/orap
   ```

---

## Step 11. app.py 수정 (중요!)

1. **Files** 메뉴로 이동
2. `orap/app.py` 파일 클릭하여 편집
3. 파일 상단 근처에서 다음 코드를 찾아 수정:

**수정 전:**
```python
def get_db_connection():
    import os
    import shutil

    # Cloud Run에서는 /tmp에 DB를 복사해서 사용
    if os.getenv('PORT'):  # Cloud Run 환경
        db_path = '/tmp/jbnu.db'
        if not os.path.exists(db_path):
            shutil.copy2('jbnu.db', db_path)
    else:  # 로컬 환경
        db_path = 'jbnu.db'
```

**수정 후:**
```python
def get_db_connection():
    import os
    import shutil

    # PythonAnywhere 환경
    # 프로젝트 디렉토리 내의 jbnu.db 사용
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'jbnu.db')
```

4. **Save** 클릭

---

## Step 12. 웹 앱 리로드

1. **Web** 메뉴로 이동
2. 페이지 상단의 초록색 **Reload** 버튼 클릭

---

## Step 13. 접속 확인

브라우저에서 접속:
```
https://사용자명.pythonanywhere.com
```

연구자 랭킹 페이지가 나타나면 성공!

---

## 문제 해결

### 에러 발생 시

1. **Web** 메뉴에서 **Error log** 링크 클릭
2. 에러 메시지 확인
3. 흔한 문제:
   - 경로 오타: 사용자명 확인
   - 패키지 누락: Bash에서 `pip install 패키지명`
   - DB 경로 문제: app.py의 get_db_connection() 확인

### 500 Internal Server Error

Bash 콘솔에서 직접 테스트:
```bash
cd ~/orap
python app.py
```
에러 메시지가 나타나면 해당 문제 해결

---

## 무료 계정 제한사항

| 항목 | 제한 |
|------|------|
| 도메인 | `사용자명.pythonanywhere.com` 고정 |
| CPU | 일일 제한 있음 |
| 저장 용량 | 512MB |
| 웹 앱 | 1개 |
| 콘솔 | 동시 2개 |

논문 시연 용도로는 충분합니다.

---

## 배포 완료 후 URL

```
https://사용자명.pythonanywhere.com
```

이 URL을 논문이나 발표 자료에 포함할 수 있습니다.
