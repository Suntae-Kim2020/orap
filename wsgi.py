# PythonAnywhere WSGI configuration file
# 이 파일의 내용을 PythonAnywhere의 WSGI configuration에 복사하세요

import sys
import os

# 프로젝트 경로 추가 (username을 실제 사용자명으로 변경)
project_home = '/home/USERNAME/orap'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 환경 변수 설정
os.environ['PYTHONANYWHERE'] = '1'

from app import app as application
