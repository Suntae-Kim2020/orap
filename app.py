from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
import sqlite3
import psycopg2
import psycopg2.extras
import os
import pandas as pd
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import csv
import json
import time
import threading

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 컬럼 매핑 로드
def load_column_mapping():
    mapping = {}
    mapping_file = '/Users/suntaekim/Downloads/publication_column_mapping.csv'
    if os.path.exists(mapping_file):
        with open(mapping_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['excel_header'].strip():  # 빈 값이 아닌 경우만
                    mapping[row['excel_header']] = row['db_column']
    return mapping

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    # Cloud SQL PostgreSQL connection
    # Check if running on Cloud Run (production)
    if os.getenv('GAE_ENV', '').startswith('standard') or os.getenv('GOOGLE_CLOUD_PROJECT'):
        # Production: Cloud SQL via Unix socket
        host = '/cloudsql/orap-471814:asia-northeast3:jbnu-db'
        conn = psycopg2.connect(
            host=host,
            database='jbnu',
            user='jbnu-user',
            password='JBNUorap2025!'
        )
    else:
        # Development: Direct connection to Cloud SQL public IP
        conn = psycopg2.connect(
            host='35.216.126.143',
            database='jbnu',
            user='jbnu-user',
            password='JBNUorap2025!',
            port=5432
        )
    return conn

# PostgreSQL 호환 헬퍼 함수들
def execute_query(conn, query, params=None):
    """Execute query and return cursor for fetching results"""
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if params:
        # PostgreSQL uses %s for parameters, convert from SQLite ? style
        pg_query = query.replace('?', '%s')
        cursor.execute(pg_query, params)
    else:
        cursor.execute(query)
    return cursor

def execute_and_fetchone(conn, query, params=None):
    """Execute query and return one result as dict"""
    cursor = execute_query(conn, query, params)
    result = cursor.fetchone()
    cursor.close()
    return result

def execute_and_fetchall(conn, query, params=None):
    """Execute query and return all results as list of dicts"""
    cursor = execute_query(conn, query, params)
    results = cursor.fetchall()
    cursor.close()
    return results

# 업로드 진행 상태 관리
def update_progress(task_id, current, total, message=""):
    progress_data = {
        'current': current,
        'total': total,
        'percentage': int((current / total) * 100) if total > 0 else 0,
        'message': message
    }
    with open(f'progress_{task_id}.json', 'w') as f:
        json.dump(progress_data, f)

def get_progress(task_id):
    try:
        with open(f'progress_{task_id}.json', 'r') as f:
            return json.load(f)
    except:
        return {'current': 0, 'total': 0, 'percentage': 0, 'message': ''}

def cleanup_progress(task_id):
    try:
        os.remove(f'progress_{task_id}.json')
    except:
        pass

def safe_remove_file(filepath):
    """파일을 안전하게 삭제"""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except:
        pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/room_manager')
def room_manager():
    return render_template('room_manager.html')

# 분석방 만들기 / 수정
@app.route('/create_room')
@app.route('/create_room/<int:room_id>')
def create_room(room_id=None):
    room = None
    if room_id:
        conn = get_db_connection()
        room = execute_and_fetchone(conn, 'SELECT * FROM room WHERE room_id = ?', (room_id,))
        conn.close()
        
        if not room:
            flash('존재하지 않는 분석방입니다.')
            return redirect(url_for('manage_rooms'))
    
    return render_template('create_room.html', room=room)

@app.route('/save_room', methods=['POST'])
def save_room():
    room_name = request.form.get('room_name')
    year_from = request.form.get('year_from')
    year_to = request.form.get('year_to')
    cutoff_date = request.form.get('cutoff_date')
    existing_room_id = request.form.get('existing_room_id')  # 수정 모드에서 사용
    
    if not all([room_name, year_from, year_to, cutoff_date]):
        flash('모든 필드를 입력해주세요.')
        redirect_url = url_for('create_room', room_id=existing_room_id) if existing_room_id else url_for('create_room')
        return redirect(redirect_url)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if existing_room_id:
            # 수정 모드
            existing_room_id = int(existing_room_id)
            
            # 다른 분석방에 동일한 이름이 있는지 체크 (자기 자신 제외)
            existing = conn.execute('SELECT room_id FROM room WHERE room_name = ? AND room_id != ?', 
                                  (room_name, existing_room_id)).fetchone()
            if existing:
                conn.close()
                flash('이미 존재하는 분석방명입니다.')
                return redirect(url_for('create_room', room_id=existing_room_id))
            
            # 분석방 정보 업데이트
            cursor.execute('''
                UPDATE room 
                SET room_name = ?, year_from = ?, year_to = ?, cutoff_date = ?
                WHERE room_id = ?
            ''', (room_name, int(year_from), int(year_to), cutoff_date, existing_room_id))
            
            room_id = existing_room_id
            flash(f'분석방 "{room_name}" 정보가 수정되었습니다.')
            
        else:
            # 새로 생성 모드
            cursor.execute('''
                INSERT INTO room (room_name, year_from, year_to, cutoff_date)
                VALUES (?, ?, ?, ?)
            ''', (room_name, int(year_from), int(year_to), cutoff_date))
            
            room_id = cursor.lastrowid
            flash(f'분석방 "{room_name}"이 생성되었습니다.')
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('unified_upload', room_id=room_id))
        
    except Exception as e:
        flash(f'분석방 {"수정" if existing_room_id else "생성"} 중 오류가 발생했습니다: {str(e)}')
        redirect_url = url_for('create_room', room_id=existing_room_id) if existing_room_id else url_for('create_room')
        return redirect(redirect_url)

@app.route('/update_room', methods=['POST'])
def update_room():
    try:
        room_id = int(request.form['room_id'])
        room_name = request.form['room_name']
        year_from = int(request.form['year_from'])
        year_to = int(request.form['year_to'])
        cutoff_date = request.form['cutoff_date']
        
        conn = get_db_connection()
        
        # 다른 분석방에 동일한 이름이 있는지 체크 (자기 자신 제외)
        existing = conn.execute('SELECT room_id FROM room WHERE room_name = ? AND room_id != ?', 
                              (room_name, room_id)).fetchone()
        if existing:
            conn.close()
            return jsonify({'success': False, 'error': '이미 존재하는 분석방명입니다.'})
        
        # 분석방 정보 업데이트
        conn.execute('''
            UPDATE room 
            SET room_name = ?, year_from = ?, year_to = ?, cutoff_date = ?
            WHERE room_id = ?
        ''', (room_name, year_from, year_to, cutoff_date, room_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 데이터 업로드
@app.route('/upload_data/<int:room_id>')
def upload_data(room_id):
    conn = get_db_connection()
    room = conn.execute('SELECT * FROM room WHERE room_id = ?', (room_id,)).fetchone()
    conn.close()
    
    if not room:
        flash('존재하지 않는 분석방입니다.')
        return redirect(url_for('index'))
    
    return render_template('upload_data.html', room=room)

# 통합 업로드 인터페이스
@app.route('/unified_upload/<int:room_id>')
def unified_upload(room_id):
    conn = get_db_connection()
    room = conn.execute('SELECT * FROM room WHERE room_id = ?', (room_id,)).fetchone()
    conn.close()
    
    if not room:
        flash('존재하지 않는 분석방입니다.')
        return redirect(url_for('index'))
    
    return render_template('unified_upload.html', room=room)

# 업로드 진행 상태 확인 API
@app.route('/api/progress/<task_id>')
def get_upload_progress(task_id):
    progress = get_progress(task_id)
    return jsonify(progress)

@app.route('/update_room_settings', methods=['POST'])
def update_room_settings():
    room_id = request.form.get('room_id')
    data_category = request.form.get('data_category')
    data_source = request.form.get('data_source')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 불리언 플래그 초기화
        is_paper = is_1 = is_10 = is_25 = is_SDG = is_international = 0
        
        # 데이터 종류에 따른 플래그 설정
        if data_type == '전체논문데이터':
            is_paper = 1
        elif data_type == '1%':
            is_1 = 1
        elif data_type == '10%':
            is_10 = 1
        elif data_type == '25%':
            is_25 = 1
        elif data_type == 'SDGs':
            is_SDG = 1
        elif data_type == 'International':
            is_international = 1
        
        cursor.execute('''
            UPDATE room SET 
                data_category = ?, 
                data_source = ?,
                is_paper = ?, 
                is_1 = ?, 
                is_10 = ?, 
                is_25 = ?, 
                is_SDG = ?, 
                is_international = ?
            WHERE room_id = ?
        ''', (data_category, data_source, is_paper, is_1, is_10, is_25, is_SDG, is_international, room_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.errorhandler(413)
def too_large(e):
    return jsonify({'success': False, 'error': '파일이 너무 큽니다. 100MB 이하의 파일을 업로드해주세요.'}), 413

def process_file_upload(room_id, data_category, data_source, data_type, filepath, filename, task_id):
    """백그라운드에서 파일 업로드를 처리하는 함수"""
    try:
        update_progress(task_id, 0, 100, "파일을 읽고 있습니다...")
        
        # 컬럼 매핑 로드
        column_mapping = load_column_mapping()
        
        # 파일 읽기
        if filename.endswith('.csv'):
            # CSV 파일을 더 유연하게 읽기 (20행이 헤더, 21행부터 데이터)
            try:
                df = pd.read_csv(filepath, encoding='utf-8-sig', header=19, skiprows=None, keep_default_na=False)
                # 빈 행 제거
                df = df.dropna(how='all').reset_index(drop=True)
            except Exception as e:
                try:
                    df = pd.read_csv(filepath, encoding='cp949', header=19, skiprows=None, keep_default_na=False)
                    df = df.dropna(how='all').reset_index(drop=True)
                except Exception as e:
                    try:
                        df = pd.read_csv(filepath, encoding='utf-8-sig', header=19, on_bad_lines='skip', keep_default_na=False)
                        df = df.dropna(how='all').reset_index(drop=True)
                    except Exception as e:
                        df = pd.read_csv(filepath, encoding='utf-8-sig', header=19, sep=None, engine='python', keep_default_na=False)
                        df = df.dropna(how='all').reset_index(drop=True)
        else:
            df = pd.read_excel(filepath, header=19, keep_default_na=False)
            df = df.dropna(how='all').reset_index(drop=True)
        
        update_progress(task_id, 5, 100, f"총 {len(df)}개 레코드를 처리합니다...")
        
        # DB 연결 및 room 정보 확인
        conn = get_db_connection()
        room = execute_and_fetchone(conn, 'SELECT * FROM room WHERE room_id = ?', (room_id,))
        
        if not room:
            cleanup_progress(task_id)
            return {'success': False, 'error': '존재하지 않는 분석방입니다.'}
        
        cursor = conn.cursor()
        
        # 불리언 플래그 설정 (이전 코드와 동일)
        boolean_flags = {
            'is_paper': 0, 'is_1': 0, 'is_10': 0, 
            'is_25': 0, 'is_SDG': 0, 'is_international': 0
        }
        
        # 데이터 타입에 따른 플래그 설정
        if data_type == '전체논문데이터':
            boolean_flags['is_paper'] = 1
        elif data_type == '1%':
            boolean_flags['is_1'] = 1
        elif data_type == '10%':
            boolean_flags['is_10'] = 1
        elif data_type == '25%':
            boolean_flags['is_25'] = 1
        elif data_type == 'SDGs':
            boolean_flags['is_SDG'] = 1
        elif data_type == 'International':
            boolean_flags['is_international'] = 1
        
        total_records = len(df)
        insert_count = 0
        update_count = 0
        error_count = 0
        
        # 컬럼 순서 (이전과 동일)
        column_order = [
            'title', 'authors', 'number_of_authors', 'scopus_author_ids', 
            'year', 'full_date', 'scopus_source_title', 'volume', 'issue', 'pages',
            'article_number', 'issn', 'source_id', 'source_type', 'language',
            'snip_publication_year', 'snip_percentile_publication_year', 
            'citescore_publication_year', 'citescore_percentile_publication_year',
            'sjr_publication_year', 'sjr_percentile_publication_year',
            'field_weighted_view_impact', 'views', 'citations', 
            'field_weighted_citation_impact', 'field_citation_average',
            'outputs_in_top_citation_percentiles_per_percentile',
            'field_weighted_outputs_in_top_citation_percentiles_per_percentile',
            'main_patent_families', 'policy_citations', 'reference', 'abstract',
            'doi', 'publication_type', 'open_access', 'eid', 'pubmed_id',
            'institutions', 'number_of_institutions', 'scopus_affiliation_ids',
            'scopus_affiliation_names', 'scopus_author_id_first_author',
            'scopus_author_id_last_author', 'scopus_author_id_corresponding_author',
            'scopus_author_id_single_author', 'country_region', 
            'number_of_countries_regions', 'all_science_journal_classification_asjc_code',
            'all_science_journal_classification_asjc_field_name',
            'quacquarelli_symonds_qs_subject_area_code',
            'quacquarelli_symonds_qs_subject_area_field_name',
            'quacquarelli_symonds_qs_subject_code',
            'quacquarelli_symonds_qs_subject_field_name',
            'times_higher_education_the_code', 'times_higher_education_the_field_name',
            'anzsrc_for_2020_parent_code', 'anzsrc_for_2020_parent_name',
            'anzsrc_for_2020_code', 'anzsrc_for_2020_name',
            'sustainable_development_goals_2025', 'topic_cluster_name',
            'topic_cluster_number', 'topic_cluster_prominence_percentile',
            'topic_name', 'topic_number', 'topic_prominence_percentile',
            'publication_link_to_topic_strength'
        ]
        
        # 각 행 처리
        for idx, (_, row) in enumerate(df.iterrows()):
            try:
                # 진행 상태 업데이트 (10% ~ 90%)
                progress_percentage = 10 + int((idx / total_records) * 80)
                update_progress(task_id, progress_percentage, 100, f"{idx + 1}/{total_records} 레코드 처리 중...")
                
                # 매핑된 데이터 준비 (이전 코드와 동일)
                mapped_data = {}
                for i, db_col in enumerate(column_order):
                    if i < len(df.columns):
                        value = row.iloc[i] if i < len(row) else None
                        if pd.isna(value):
                            value = None
                        elif isinstance(value, str):
                            value = value.strip() if value else None
                        mapped_data[db_col] = value
                
                # room_id와 불리언 플래그 추가
                mapped_data['room_id'] = room_id
                for flag, value in boolean_flags.items():
                    mapped_data[flag] = value
                
                # 빈 매핑 데이터 건너뛰기
                if not any(v for k, v in mapped_data.items() if k not in ['room_id', 'is_paper', 'is_1', 'is_10', 'is_25', 'is_SDG', 'is_international']):
                    continue
                
                # 기존 레코드 확인 (EID 기반 매핑)
                eid = mapped_data.get('eid', '')
                
                # EID로 중복 확인 (EID가 가장 정확한 식별자)
                if eid and eid.strip():
                    existing = cursor.execute('''
                        SELECT record_id FROM publication 
                        WHERE room_id = ? AND eid = ?
                    ''', (room_id, eid)).fetchone()
                else:
                    # EID가 없으면 DOI로 확인
                    doi = mapped_data.get('doi', '')
                    if doi and doi.strip():
                        existing = cursor.execute('''
                            SELECT record_id FROM publication 
                            WHERE room_id = ? AND doi = ?
                        ''', (room_id, doi)).fetchone()
                    else:
                        existing = None
                
                if existing:
                    # 업데이트: 기존 불리언 플래그를 OR 연산으로 업데이트
                    record_id = existing[0]
                    update_parts = []
                    
                    # 새로운 불리언 플래그가 1인 경우만 업데이트
                    needs_update = False
                    for flag, new_value in boolean_flags.items():
                        if new_value == 1:
                            update_parts.append(f"{flag} = 1")
                            needs_update = True
                    
                    if needs_update and update_parts:
                        cursor.execute(f'''
                            UPDATE publication SET {', '.join(update_parts)}
                            WHERE record_id = ?
                        ''', (record_id,))
                        update_count += 1
                else:
                    # 삽입: 새 레코드 생성
                    columns = list(mapped_data.keys())
                    values = list(mapped_data.values())
                    
                    placeholders = ', '.join(['?' for _ in columns])
                    column_names = ', '.join(columns)
                    
                    cursor.execute(f'''
                        INSERT INTO publication ({column_names})
                        VALUES ({placeholders})
                    ''', values)
                    insert_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"Row error: {str(e)}")
                continue
        
        update_progress(task_id, 95, 100, "업로드 기록을 저장하고 있습니다...")
        
        # 파일 업로드 기록 저장
        cursor.execute('''
            INSERT INTO file_uploads (room_id, filename, data_category, data_source, data_type, upload_date, record_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (room_id, filename, data_category, data_source or '', data_type or '', datetime.now().isoformat(), insert_count + update_count))
        
        conn.commit()
        conn.close()
        
        # 업로드된 파일 삭제
        os.remove(filepath)
        
        update_progress(task_id, 100, 100, "업로드가 완료되었습니다!")
        
        result = {
            'success': True,
            'total_records': total_records,
            'insert_count': insert_count,
            'update_count': update_count,
            'error_count': error_count,
            'success_count': insert_count + update_count
        }
        
        # 잠시 기다린 후 진행 상태 파일 정리
        time.sleep(2)
        cleanup_progress(task_id)
        
        return result
        
    except Exception as e:
        cleanup_progress(task_id)
        return {'success': False, 'error': f'파일 처리 중 오류: {str(e)}'}

@app.route('/upload_file', methods=['POST'])
def upload_file():
    try:
        room_id = request.form.get('room_id')
        data_category = request.form.get('data_category', '').strip()
        data_source = request.form.get('data_source', '').strip()
        data_type = request.form.get('data_type', '').strip()
        
        
        if not data_category:
            return jsonify({'success': False, 'error': '데이터 카테고리를 선택해주세요.'})
        
        if data_category == '학술성과':
            if not data_source:
                return jsonify({'success': False, 'error': '학술성과의 경우 데이터 소스를 선택해주세요.'})
            if not data_type:
                return jsonify({'success': False, 'error': '학술성과의 경우 데이터 종류를 선택해주세요.'})
        
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '파일이 선택되지 않았습니다.'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '파일이 선택되지 않았습니다.'})
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # 고유한 작업 ID 생성
            task_id = f"{room_id}_{int(time.time())}"
            
            # 백그라운드에서 파일 처리
            def background_process():
                result = process_file_upload(room_id, data_category, data_source, data_type, filepath, filename, task_id)
                # 결과를 파일에 저장
                with open(f'result_{task_id}.json', 'w') as f:
                    json.dump(result, f)
            
            thread = threading.Thread(target=background_process)
            thread.start()
            
            return jsonify({
                'success': True,
                'task_id': task_id,
                'message': '업로드가 시작되었습니다.'
            })
            
        else:
            return jsonify({'success': False, 'error': '지원하지 않는 파일 형식입니다.'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'업로드 중 오류: {str(e)}'})

# 업로드 결과 확인 API
@app.route('/api/result/<task_id>')
def get_upload_result(task_id):
    try:
        result_file = f'result_{task_id}.json'
        if os.path.exists(result_file):
            with open(result_file, 'r') as f:
                result = json.load(f)
            
            # 첫 번째 호출에서만 파일을 삭제하도록 플래그 추가
            if not hasattr(get_upload_result, '_accessed_files'):
                get_upload_result._accessed_files = set()
            
            if task_id not in get_upload_result._accessed_files:
                get_upload_result._accessed_files.add(task_id)
                # 30초 후에 파일 삭제 (충분한 시간을 두어 폴링 완료 보장)
                threading.Timer(30.0, lambda: safe_remove_file(result_file)).start()
            
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': '결과를 찾을 수 없습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'결과를 읽는 중 오류가 발생했습니다: {str(e)}'})

# 분석
@app.route('/analysis')
def analysis():
    conn = get_db_connection()
    rooms = execute_and_fetchall(conn, 'SELECT * FROM room ORDER BY room_id DESC')
    conn.close()
    return render_template('analysis.html', rooms=rooms)

# 분석 실행
@app.route('/analysis_run')
@app.route('/analysis_run/<int:room_id>')
def analysis_run(room_id=None):
    conn = get_db_connection()
    rooms = execute_and_fetchall(conn, 'SELECT * FROM room ORDER BY room_id DESC')
    selected_room = None
    if room_id:
        selected_room = conn.execute('SELECT * FROM room WHERE room_id = ?', (room_id,)).fetchone()
    conn.close()
    return render_template('analysis_run.html', rooms=rooms, selected_room=selected_room)

# 분석방 관리 페이지
@app.route('/manage_rooms')
def manage_rooms():
    conn = get_db_connection()
    # 분석방 정보와 파일/데이터 개수 조회 (정확한 카운트)
    rooms = conn.execute('''
        SELECT r.*,
               COALESCE(fu_count.file_count, 0) as file_count,
               COALESCE(p_count.data_count, 0) as data_count
        FROM room r
        LEFT JOIN (
            SELECT room_id, COUNT(*) as file_count 
            FROM file_uploads 
            GROUP BY room_id
        ) fu_count ON r.room_id = fu_count.room_id
        LEFT JOIN (
            SELECT room_id, COUNT(*) as data_count 
            FROM publication 
            GROUP BY room_id
        ) p_count ON r.room_id = p_count.room_id
        ORDER BY r.room_id DESC
    ''').fetchall()
    conn.close()
    return render_template('manage_rooms.html', rooms=rooms)

# 분석방 수정 페이지
@app.route('/edit_room/<int:room_id>')
def edit_room(room_id):
    conn = get_db_connection()
    room = conn.execute('SELECT * FROM room WHERE room_id = ?', (room_id,)).fetchone()
    conn.close()
    
    if not room:
        flash('존재하지 않는 분석방입니다.')
        return redirect(url_for('manage_rooms'))
    
    return render_template('edit_room.html', room=room)

# 분석방 삭제
@app.route('/delete_room', methods=['POST'])
def delete_room():
    try:
        room_id = request.json.get('room_id')
        
        conn = get_db_connection()
        
        # 관련된 모든 데이터 삭제
        conn.execute('DELETE FROM publication WHERE room_id = ?', (room_id,))
        conn.execute('DELETE FROM file_uploads WHERE room_id = ?', (room_id,))
        conn.execute('DELETE FROM room WHERE room_id = ?', (room_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 분석방 정보 업데이트 (폼 제출)
@app.route('/update_room_info', methods=['POST'])
def update_room_info():
    try:
        room_id = int(request.form['room_id'])
        room_name = request.form['room_name']
        year_from = int(request.form['year_from'])
        year_to = int(request.form['year_to'])
        cutoff_date = request.form['cutoff_date']
        
        conn = get_db_connection()
        
        # 다른 분석방에 동일한 이름이 있는지 체크 (자기 자신 제외)
        existing = conn.execute('SELECT room_id FROM room WHERE room_name = ? AND room_id != ?', 
                              (room_name, room_id)).fetchone()
        if existing:
            conn.close()
            flash('이미 존재하는 분석방명입니다.')
            return redirect(url_for('edit_room', room_id=room_id))
        
        # 분석방 정보 업데이트
        conn.execute('''
            UPDATE room 
            SET room_name = ?, year_from = ?, year_to = ?, cutoff_date = ?
            WHERE room_id = ?
        ''', (room_name, year_from, year_to, cutoff_date, room_id))
        
        conn.commit()
        conn.close()
        
        flash(f'분석방 "{room_name}" 정보가 수정되었습니다.')
        return redirect(url_for('manage_rooms'))
        
    except Exception as e:
        flash(f'분석방 수정 중 오류가 발생했습니다: {str(e)}')
        return redirect(url_for('edit_room', room_id=request.form.get('room_id', 0)))

# API 엔드포인트
@app.route('/api/rooms')
def api_rooms():
    conn = get_db_connection()
    rooms = execute_and_fetchall(conn, 'SELECT * FROM room ORDER BY room_id DESC')
    conn.close()
    
    data = []
    for room in rooms:
        data.append(dict(room))
    
    return jsonify({'rooms': data})


@app.route('/api/room_uploads/<int:room_id>')
def api_room_uploads(room_id):
    conn = get_db_connection()
    uploads = conn.execute('''
        SELECT * FROM file_uploads 
        WHERE room_id = ? 
        ORDER BY upload_date DESC
    ''', (room_id,)).fetchall()
    conn.close()
    
    data = []
    for upload in uploads:
        data.append(dict(upload))
    
    return jsonify({'uploads': data})

@app.route('/api/room_stats/<int:room_id>')
def api_room_stats(room_id):
    conn = get_db_connection()
    
    # publication 테이블에서 해당 room_id의 총 레코드 수 조회
    result = execute_and_fetchone(conn, 'SELECT COUNT(*) as count FROM publication WHERE room_id = ?', (room_id,))
    total_records = result['count']
    
    conn.close()
    
    return jsonify({'total_records': total_records})

@app.route('/delete_upload', methods=['POST'])
def delete_upload():
    try:
        data = request.get_json()
        upload_id = data.get('upload_id')
        
        if not upload_id:
            return jsonify({'success': False, 'error': '업로드 ID가 필요합니다.'})
        
        conn = get_db_connection()
        
        # 업로드 정보 조회
        upload_info = conn.execute('''
            SELECT room_id, data_type FROM file_uploads 
            WHERE upload_id = ?
        ''', (upload_id,)).fetchone()
        
        if not upload_info:
            return jsonify({'success': False, 'error': '업로드 파일을 찾을 수 없습니다.'})
        
        room_id = upload_info['room_id']
        data_type = upload_info['data_type']
        
        # 데이터 타입에 따른 처리
        if data_type == '전체논문데이터':
            # 전체논문데이터인 경우: 같은 room_id의 모든 publication 레코드와 file_uploads 삭제
            conn.execute('DELETE FROM publication WHERE room_id = ?', (room_id,))
            conn.execute('DELETE FROM file_uploads WHERE room_id = ?', (room_id,))
        else:
            # 다른 타입인 경우: 해당 플래그를 0으로 업데이트
            flag_column = None
            if data_type == '1%':
                flag_column = 'is_1'
            elif data_type == '10%':
                flag_column = 'is_10'
            elif data_type == '25%':
                flag_column = 'is_25'
            elif data_type == 'SDGs':
                flag_column = 'is_SDG'
            elif data_type == 'International':
                flag_column = 'is_international'
            
            if flag_column:
                conn.execute(f'UPDATE publication SET {flag_column} = 0 WHERE room_id = ?', (room_id,))
            
            # 전체논문데이터가 아닌 경우에만 개별 파일 삭제
            conn.execute('DELETE FROM file_uploads WHERE upload_id = ?', (upload_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '파일이 성공적으로 삭제되었습니다.'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'삭제 중 오류가 발생했습니다: {str(e)}'})

# 우수논문 후보 추출 API
@app.route('/api/extract_candidates', methods=['POST'])
def extract_candidates():
    try:
        data = request.get_json()
        room_id = data.get('room_id')
        weights = data.get('weights')
        
        if not room_id or not weights:
            return jsonify({'success': False, 'error': '분석방 ID와 가중치가 필요합니다.'})
        
        conn = get_db_connection()
        
        # 전체 논문 수 조회
        result = execute_and_fetchone(conn, 'SELECT COUNT(*) as count FROM publication WHERE room_id = ?', (room_id,))
        total_papers = result['count']
        
        # 가중치가 적용된 논문들을 점수 계산하여 조회
        query = '''
            SELECT eid, title, is_10, is_25, is_SDG, is_international,
                   CAST((is_10 * ? + is_25 * ? + is_SDG * ? + is_international * ?) AS REAL) as total_score
            FROM publication 
            WHERE room_id = ? 
            AND (
                (is_10 = 1 AND ? > 0) OR 
                (is_25 = 1 AND ? > 0) OR 
                (is_SDG = 1 AND ? > 0) OR 
                (is_international = 1 AND ? > 0)
            )
            ORDER BY total_score DESC
            LIMIT 5
        '''
        
        weight_10 = float(weights.get('10%', 0))
        weight_25 = float(weights.get('25%', 0))
        weight_sdg = float(weights.get('SDGs', 0))
        weight_international = float(weights.get('International', 0))
        
        results = conn.execute(query, (
            weight_10, weight_25, weight_sdg, weight_international, room_id,
            weight_10, weight_25, weight_sdg, weight_international
        )).fetchall()
        
        # 최고점 논문의 개수 계산
        max_score_query = '''
            SELECT COUNT(*) as count
            FROM (
                SELECT CAST((is_10 * ? + is_25 * ? + is_SDG * ? + is_international * ?) AS REAL) as total_score
                FROM publication 
                WHERE room_id = ? 
                AND (
                    (is_10 = 1 AND ? > 0) OR 
                    (is_25 = 1 AND ? > 0) OR 
                    (is_SDG = 1 AND ? > 0) OR 
                    (is_international = 1 AND ? > 0)
                )
                ORDER BY total_score DESC
                LIMIT 1
            ) max_score_subquery
            JOIN (
                SELECT CAST((is_10 * ? + is_25 * ? + is_SDG * ? + is_international * ?) AS REAL) as total_score
                FROM publication 
                WHERE room_id = ? 
                AND (
                    (is_10 = 1 AND ? > 0) OR 
                    (is_25 = 1 AND ? > 0) OR 
                    (is_SDG = 1 AND ? > 0) OR 
                    (is_international = 1 AND ? > 0)
                )
            ) all_scores ON max_score_subquery.total_score = all_scores.total_score
        '''
        
        max_score_count = conn.execute(max_score_query, (
            weight_10, weight_25, weight_sdg, weight_international, room_id,
            weight_10, weight_25, weight_sdg, weight_international,
            weight_10, weight_25, weight_sdg, weight_international, room_id,
            weight_10, weight_25, weight_sdg, weight_international
        )).fetchone()['count']
        
        candidates = []
        for row in results:
            candidates.append({
                'eid': row['eid'] or '',
                'title': row['title'] or '',
                'is_10': bool(row['is_10']),
                'is_25': bool(row['is_25']),
                'is_SDG': bool(row['is_SDG']),
                'is_international': bool(row['is_international']),
                'total_score': round(row['total_score'], 2)
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'candidates': candidates,
            'total_count': max_score_count,
            'total_papers': total_papers,
            'weights': weights
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'후보 추출 중 오류가 발생했습니다: {str(e)}'})

# 2단계 정량 지표 기반 우수논문 후보 추출 API
@app.route('/api/extract_second_stage_candidates', methods=['POST'])
def extract_second_stage_candidates():
    try:
        import math
        import numpy as np
        
        data = request.get_json()
        room_id = data.get('room_id')
        stage1_weights = data.get('stage1_weights')
        stage2_weights = data.get('stage2_weights')
        
        if not room_id or not stage1_weights or not stage2_weights:
            return jsonify({'success': False, 'error': '분석방 ID, 1단계 가중치, 2단계 가중치가 필요합니다.'})
        
        conn = get_db_connection()
        
        # 1단계 가중치 추출
        weight_1 = float(stage1_weights.get('1%', 0))
        weight_10 = float(stage1_weights.get('10%', 0))
        weight_25 = float(stage1_weights.get('25%', 0))
        weight_sdg = float(stage1_weights.get('SDGs', 0))
        weight_international = float(stage1_weights.get('International', 0))
        
        # 먼저 1단계 최고점 계산
        max_score_query = '''
            SELECT MAX(CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL)) as max_score
            FROM publication 
            WHERE room_id = ? 
            AND (
                (COALESCE(is_1, 0) = 1 AND ? > 0) OR 
                (COALESCE(is_10, 0) = 1 AND ? > 0) OR 
                (COALESCE(is_25, 0) = 1 AND ? > 0) OR 
                (COALESCE(is_SDG, 0) = 1 AND ? > 0) OR 
                (COALESCE(is_international, 0) = 1 AND ? > 0)
            )
        '''
        
        max_score_result = conn.execute(max_score_query, (
            weight_1, weight_10, weight_25, weight_sdg, weight_international, room_id,
            weight_1, weight_10, weight_25, weight_sdg, weight_international
        )).fetchone()
        
        max_score = max_score_result['max_score'] if max_score_result and max_score_result['max_score'] is not None else 0
        
        # 1단계에서 최고점을 받은 논문들만 조회 (1단계 진짜 후보)
        first_stage_query = '''
            SELECT record_id, eid, title, 
                   field_weighted_citation_impact, citations, views, field_weighted_view_impact,
                   snip_publication_year, snip_percentile_publication_year,
                   citescore_publication_year, citescore_percentile_publication_year,
                   sjr_publication_year, sjr_percentile_publication_year,
                   is_1, is_10, is_25, is_SDG, is_international,
                   CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL) as stage1_score
            FROM publication 
            WHERE room_id = ? 
            AND (
                (COALESCE(is_1, 0) = 1 AND ? > 0) OR 
                (COALESCE(is_10, 0) = 1 AND ? > 0) OR 
                (COALESCE(is_25, 0) = 1 AND ? > 0) OR 
                (COALESCE(is_SDG, 0) = 1 AND ? > 0) OR 
                (COALESCE(is_international, 0) = 1 AND ? > 0)
            )
            AND CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL) = ?
            ORDER BY stage1_score DESC
        '''
        
        papers = conn.execute(first_stage_query, (
            weight_1, weight_10, weight_25, weight_sdg, weight_international, room_id,
            weight_1, weight_10, weight_25, weight_sdg, weight_international,
            weight_1, weight_10, weight_25, weight_sdg, weight_international, max_score
        )).fetchall()
        conn.close()
        
        if not papers:
            return jsonify({'success': False, 'error': '1단계에서 추출된 논문이 없습니다.'})
        
        # 데이터를 리스트로 변환하여 계산용으로 준비
        paper_data = []
        for paper in papers:
            paper_dict = dict(paper)
            # None 값과 문자열을 적절히 처리
            for key in paper_dict:
                if paper_dict[key] is None and key not in ['title', 'record_id', 'eid']:
                    paper_dict[key] = 0.0
                elif key not in ['title', 'record_id', 'eid', 'is_1', 'is_10', 'is_25', 'is_SDG', 'is_international']:
                    # 숫자가 아닌 값들을 0.0으로 변환
                    try:
                        paper_dict[key] = float(paper_dict[key]) if paper_dict[key] is not None else 0.0
                    except (ValueError, TypeError):
                        paper_dict[key] = 0.0
            paper_data.append(paper_dict)
        
        # 정규화 함수들
        def safe_log(x):
            try:
                val = float(x) if x is not None else 0.0
                return math.log(1 + max(0, val))
            except (ValueError, TypeError):
                return 0.0
        
        def percentile(data, p):
            if not data:
                return 0
            sorted_data = sorted(data)
            k = (len(sorted_data) - 1) * p / 100
            f = int(k)
            c = k - f
            if f == len(sorted_data) - 1:
                return sorted_data[f]
            return sorted_data[f] * (1 - c) + sorted_data[f + 1] * c
        
        def winsorize_normalize(values, p5=5, p95=95):
            try:
                # 숫자 값만 필터링
                numeric_values = []
                for v in values:
                    try:
                        numeric_values.append(float(v) if v is not None else 0.0)
                    except (ValueError, TypeError):
                        numeric_values.append(0.0)
                
                if not numeric_values or all(v == 0 for v in numeric_values):
                    return [0.0] * len(values)
                
                p5_val = percentile(numeric_values, p5)
                p95_val = percentile(numeric_values, p95)
                
                if p95_val == p5_val:
                    return [0.5] * len(values)
                
                return [(min(v, p95_val) - p5_val) / (p95_val - p5_val) for v in numeric_values]
            except Exception:
                return [0.0] * len(values)
        
        # 각 지표별 값 추출
        fwci_values = [p['field_weighted_citation_impact'] for p in paper_data]
        citation_values = [safe_log(p['citations']) for p in paper_data]
        view_values = [safe_log(p['views']) for p in paper_data]
        fwvi_values = [p['field_weighted_view_impact'] for p in paper_data]
        
        # SNIP, CiteScore, SJR 정규화 (값 + 퍼센타일 혼합)
        snip_raw = [p['snip_publication_year'] for p in paper_data]
        snip_log = [safe_log(v) for v in snip_raw]
        snip_val_norm = winsorize_normalize(snip_log)
        snip_pct_norm = []
        for p in paper_data:
            try:
                val = float(p['snip_percentile_publication_year']) if p['snip_percentile_publication_year'] is not None else 0.0
                snip_pct_norm.append(val / 100)
            except (ValueError, TypeError):
                snip_pct_norm.append(0.0)
        snip_combined = [0.6 * val + 0.4 * pct for val, pct in zip(snip_val_norm, snip_pct_norm)]
        
        citescore_raw = [p['citescore_publication_year'] for p in paper_data]
        citescore_log = [safe_log(v) for v in citescore_raw]
        citescore_val_norm = winsorize_normalize(citescore_log)
        citescore_pct_norm = []
        for p in paper_data:
            try:
                val = float(p['citescore_percentile_publication_year']) if p['citescore_percentile_publication_year'] is not None else 0.0
                citescore_pct_norm.append(val / 100)
            except (ValueError, TypeError):
                citescore_pct_norm.append(0.0)
        citescore_combined = [0.6 * val + 0.4 * pct for val, pct in zip(citescore_val_norm, citescore_pct_norm)]
        
        sjr_raw = [p['sjr_publication_year'] for p in paper_data]
        sjr_log = [safe_log(v) for v in sjr_raw]
        sjr_val_norm = winsorize_normalize(sjr_log)
        sjr_pct_norm = []
        for p in paper_data:
            try:
                val = float(p['sjr_percentile_publication_year']) if p['sjr_percentile_publication_year'] is not None else 0.0
                sjr_pct_norm.append(val / 100)
            except (ValueError, TypeError):
                sjr_pct_norm.append(0.0)
        sjr_combined = [0.6 * val + 0.4 * pct for val, pct in zip(sjr_val_norm, sjr_pct_norm)]
        
        # 논문 성과 지표 정규화
        fwci_normalized = []
        for v in fwci_values:
            try:
                val = float(v) if v is not None else 0.0
                fwci_normalized.append(min(val, 3) / 3)
            except (ValueError, TypeError):
                fwci_normalized.append(0.0)
                
        citation_normalized = winsorize_normalize(citation_values)
        view_normalized = winsorize_normalize(view_values)
        
        fwvi_normalized = []
        for v in fwvi_values:
            try:
                val = float(v) if v is not None else 0.0
                fwvi_normalized.append(min(val, 3) / 3)
            except (ValueError, TypeError):
                fwvi_normalized.append(0.0)
                
        views_block = [0.5 * v + 0.5 * f for v, f in zip(view_normalized, fwvi_normalized)]
        
        # 최종 점수 계산
        candidates_with_scores = []
        for i, paper in enumerate(paper_data):
            # 저널 영향력 점수 (45%)
            journal_score = (
                0.15 * snip_combined[i] +
                0.15 * citescore_combined[i] +
                0.15 * sjr_combined[i]
            )
            
            # 논문 성과 점수 (45%)
            paper_score = (
                0.20 * fwci_normalized[i] +
                0.10 * citation_normalized[i] +
                0.10 * views_block[i] +
                0.05 * 0  # Top Citation Percentiles 데이터 없음
            )
            
            # 사회적 영향 점수 (10%) - 데이터 없어서 0
            social_score = 0.0
            
            # 최종 점수
            final_score = journal_score + paper_score + social_score
            
            candidates_with_scores.append({
                'record_id': paper['record_id'],
                'eid': paper['eid'] or '',
                'title': paper['title'] or '',
                'journal_score': round(journal_score, 4),
                'paper_score': round(paper_score, 4),
                'social_score': round(social_score, 4),
                'final_score': round(final_score, 4),
                'fwci': paper['field_weighted_citation_impact'],
                'citations': paper['citations'],
                'views': paper['views'],
                'snip': paper['snip_publication_year'],
                'citescore': paper['citescore_publication_year'],
                'sjr': paper['sjr_publication_year']
            })
        
        # 최종 점수로 정렬하여 상위 10개 선택
        candidates_with_scores.sort(key=lambda x: x['final_score'], reverse=True)
        top_10_candidates = candidates_with_scores[:10]
        
        return jsonify({
            'success': True,
            'candidates': top_10_candidates,
            'total_analyzed': len(candidates_with_scores),
            'stage2_weights': stage2_weights
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'2단계 후보 추출 중 오류가 발생했습니다: {str(e)}'})

@app.route('/api/download_first_stage_candidates', methods=['POST'])
def download_first_stage_candidates():
    try:
        room_id = request.form.get('room_id')
        weight_1 = float(request.form.get('weight_1', 0))
        weight_10 = float(request.form.get('weight_10', 3))
        weight_25 = float(request.form.get('weight_25', 2))
        weight_sdg = float(request.form.get('weight_sdg', 1.5))
        weight_international = float(request.form.get('weight_international', 1.5))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Stage 1 query to get EIDs of candidates with maximum score
        query = '''
        SELECT eid,
               CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL) as total_score
        FROM publication 
        WHERE room_id = ? 
        AND (COALESCE(is_1, 0) = 1 OR COALESCE(is_10, 0) = 1 OR COALESCE(is_25, 0) = 1 OR COALESCE(is_SDG, 0) = 1 OR COALESCE(is_international, 0) = 1)
        ORDER BY total_score DESC
        '''
        
        cursor.execute(query, (weight_1, weight_10, weight_25, weight_sdg, weight_international, room_id))
        results = cursor.fetchall()
        
        if not results:
            conn.close()
            return "No candidates found", 404
            
        # Find maximum score and get EIDs of top candidates
        max_score = max(row[1] for row in results)  # total_score is at index 1
        candidate_eids = [row[0] for row in results if row[1] == max_score]
        
        # Get full publication records for these EIDs (전체 컬럼)
        eid_placeholders = ','.join(['?' for _ in candidate_eids])
        full_query = f'''
        SELECT *,
               CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL) as total_score
        FROM publication 
        WHERE room_id = ? AND eid IN ({eid_placeholders})
        ORDER BY total_score DESC, eid
        '''
        
        params = [weight_1, weight_10, weight_25, weight_sdg, weight_international, room_id] + candidate_eids
        cursor.execute(full_query, params)
        full_records = cursor.fetchall()
        
        if not full_records:
            conn.close()
            return "No records found", 404
        
        # Get column names from cursor description
        column_names = [description[0] for description in cursor.description]
        conn.close()
        
        # Create CSV content
        import io
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header with all column names
        writer.writerow(column_names)
        
        # Write data
        for row in full_records:
            writer.writerow([cell or '' for cell in row])
        
        # Prepare response
        csv_content = output.getvalue()
        output.close()
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
        response.headers['Content-Disposition'] = f'attachment; filename=stage1_candidates_full_data_{room_id}.csv'
        
        return response
        
    except Exception as e:
        return f"CSV 다운로드 중 오류가 발생했습니다: {str(e)}", 500

@app.route('/topic_distribution_analysis', methods=['POST'])
def topic_distribution_analysis():
    try:
        room_id = request.form.get('room_id')
        weight_1 = float(request.form.get('weight_1', 0))
        weight_10 = float(request.form.get('weight_10', 3))
        weight_25 = float(request.form.get('weight_25', 2))
        weight_sdg = float(request.form.get('weight_sdg', 1.5))
        weight_international = float(request.form.get('weight_international', 1.5))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get room information
        cursor.execute('SELECT room_name FROM room WHERE room_id = ?', (room_id,))
        room = cursor.fetchone()
        if not room:
            conn.close()
            return "분석방을 찾을 수 없습니다.", 404
            
        # Stage 1 query to get candidates with maximum score
        query = '''
        SELECT eid, title, is_1, is_10, is_25, is_SDG, is_international,
               CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL) as total_score
        FROM publication 
        WHERE room_id = ? 
        AND (COALESCE(is_1, 0) = 1 OR COALESCE(is_10, 0) = 1 OR COALESCE(is_25, 0) = 1 OR COALESCE(is_SDG, 0) = 1 OR COALESCE(is_international, 0) = 1)
        ORDER BY total_score DESC
        '''
        
        cursor.execute(query, (weight_1, weight_10, weight_25, weight_sdg, weight_international, room_id))
        results = cursor.fetchall()
        
        if not results:
            conn.close()
            return "추출된 후보가 없습니다.", 404
            
        # Find maximum score candidates
        max_score = max(row[7] for row in results)
        max_score_candidates = [row for row in results if row[7] == max_score]
        
        conn.close()
        
        # For now, return a simple analysis page
        # In a real implementation, you would analyze topics/keywords
        analysis_data = {
            'room_name': room['room_name'],
            'room_id': room_id,
            'total_candidates': len(max_score_candidates),
            'max_score': max_score,
            'weights': {
                '상위1%': weight_1,
                '상위10%': weight_10,
                '상위25%': weight_25,
                'SDGs': weight_sdg,
                '국제협력': weight_international
            }
        }
        
        return render_template('topic_analysis.html', **analysis_data)
        
    except Exception as e:
        return f"주제 분포 분석 중 오류가 발생했습니다: {str(e)}", 500

@app.route('/api/topic_distribution_data', methods=['POST'])
def get_topic_distribution_data():
    try:
        room_id = request.form.get('room_id')
        weight_1 = float(request.form.get('weight_1', 0))
        weight_10 = float(request.form.get('weight_10', 3))
        weight_25 = float(request.form.get('weight_25', 2))
        weight_sdg = float(request.form.get('weight_sdg', 1.5))
        weight_international = float(request.form.get('weight_international', 1.5))
        analysis_type = request.form.get('analysis_type')
        
        # 컬럼 매핑
        column_mapping = {
            'asjc': 'all_science_journal_classification_asjc_field_name',
            'qs': 'quacquarelli_symonds_qs_subject_area_field_name',
            'the': 'times_higher_education_the_field_name'
        }
        
        if analysis_type not in column_mapping:
            return jsonify({'success': False, 'error': '잘못된 분석 유형입니다.'})
        
        target_column = column_mapping[analysis_type]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1단계 최고점 후보들의 주제 분포 분석
        query = f'''
        SELECT {target_column} as field, COUNT(*) as count
        FROM publication 
        WHERE room_id = ? 
        AND (COALESCE(is_1, 0) = 1 OR COALESCE(is_10, 0) = 1 OR COALESCE(is_25, 0) = 1 OR COALESCE(is_SDG, 0) = 1 OR COALESCE(is_international, 0) = 1)
        AND CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL) = (
            SELECT MAX(CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL))
            FROM publication 
            WHERE room_id = ? 
            AND (COALESCE(is_1, 0) = 1 OR COALESCE(is_10, 0) = 1 OR COALESCE(is_25, 0) = 1 OR COALESCE(is_SDG, 0) = 1 OR COALESCE(is_international, 0) = 1)
        )
        GROUP BY {target_column}
        ORDER BY count DESC
        '''
        
        params = [
            room_id,
            weight_1, weight_10, weight_25, weight_sdg, weight_international,
            weight_1, weight_10, weight_25, weight_sdg, weight_international,
            room_id
        ]
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        topics = []
        for row in results:
            field_value = row[0]
            count = row[1]
            
            # 여러 분야가 세미콜론으로 구분된 경우 처리
            if field_value and ';' in str(field_value):
                fields = [f.strip() for f in str(field_value).split(';') if f.strip()]
                # 첫 번째 분야만 사용하거나, 모든 분야를 개별적으로 처리할 수 있음
                for field in fields:
                    topics.append({'field': field, 'count': count})
            else:
                topics.append({'field': field_value, 'count': count})
        
        # 동일한 분야가 중복된 경우 합치기
        field_counts = {}
        for topic in topics:
            field = topic['field'] or '미분류'
            if field in field_counts:
                field_counts[field] += topic['count']
            else:
                field_counts[field] = topic['count']
        
        # 정렬된 결과 생성
        final_topics = [{'field': field, 'count': count} for field, count in sorted(field_counts.items(), key=lambda x: x[1], reverse=True)]
        
        return jsonify({'success': True, 'topics': final_topics})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'주제 분포 데이터 조회 중 오류가 발생했습니다: {str(e)}'})

@app.route('/api/download_topic_analysis', methods=['POST'])
def download_topic_analysis():
    try:
        room_id = request.form.get('room_id')
        weight_1 = float(request.form.get('weight_1', 0))
        weight_10 = float(request.form.get('weight_10', 3))
        weight_25 = float(request.form.get('weight_25', 2))
        weight_sdg = float(request.form.get('weight_sdg', 1.5))
        weight_international = float(request.form.get('weight_international', 1.5))
        analysis_type = request.form.get('analysis_type')
        
        # 컬럼 매핑
        column_mapping = {
            'asjc': 'all_science_journal_classification_asjc_field_name',
            'qs': 'quacquarelli_symonds_qs_subject_area_field_name',
            'the': 'times_higher_education_the_field_name'
        }
        
        if analysis_type not in column_mapping:
            return "잘못된 분석 유형입니다.", 400
        
        target_column = column_mapping[analysis_type]
        
        # Type names for file naming
        type_names = {
            'asjc': 'ASJC',
            'qs': 'QS', 
            'the': 'THE'
        }
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1단계 최고점 후보들을 주제별로 그룹화하여 전체 데이터 가져오기
        query = f'''
        SELECT {target_column} as topic_field, *, 
               CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL) as total_score
        FROM publication 
        WHERE room_id = ? 
        AND (COALESCE(is_1, 0) = 1 OR COALESCE(is_10, 0) = 1 OR COALESCE(is_25, 0) = 1 OR COALESCE(is_SDG, 0) = 1 OR COALESCE(is_international, 0) = 1)
        AND CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL) = (
            SELECT MAX(CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL))
            FROM publication 
            WHERE room_id = ? 
            AND (COALESCE(is_1, 0) = 1 OR COALESCE(is_10, 0) = 1 OR COALESCE(is_25, 0) = 1 OR COALESCE(is_SDG, 0) = 1 OR COALESCE(is_international, 0) = 1)
        )
        ORDER BY {target_column}, total_score DESC
        '''
        
        params = [
            weight_1, weight_10, weight_25, weight_sdg, weight_international, room_id,
            weight_1, weight_10, weight_25, weight_sdg, weight_international,
            weight_1, weight_10, weight_25, weight_sdg, weight_international, room_id
        ]
        
        cursor.execute(query, params)
        records = cursor.fetchall()
        
        if not records:
            conn.close()
            return "분석할 데이터가 없습니다.", 404
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        conn.close()
        
        # Create Excel file with colored cells for better topic visualization
        import io
        try:
            import xlsxwriter
            # Create Excel file with colors
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet('Topic Analysis')
            
            # Define colors for different topics
            topic_colors = [
                '#FFE6E6',  # Light Red
                '#E6F3FF',  # Light Blue  
                '#E6FFE6',  # Light Green
                '#FFF0E6',  # Light Orange
                '#F0E6FF',  # Light Purple
                '#FFFFCC',  # Light Yellow
                '#FFE6F0',  # Light Pink
                '#E6FFF0',  # Light Mint
                '#F0F0FF',  # Light Lavender
                '#FFE6CC',  # Light Peach
            ]
            
            # Create formats for different topics
            topic_formats = {}
            unique_topics = []
            current_topic = None
            
            # Get unique topics for coloring
            for row in records:
                topic = row[0] or '미분류'
                if topic not in unique_topics:
                    unique_topics.append(topic)
            
            # Create format for each topic
            for i, topic in enumerate(unique_topics):
                color = topic_colors[i % len(topic_colors)]
                topic_formats[topic] = workbook.add_format({
                    'bg_color': color,
                    'border': 1
                })
            
            # Header format
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D9D9D9',
                'border': 1,
                'align': 'center'
            })
            
            # Write headers
            for col, header in enumerate(column_names):
                worksheet.write(0, col, header, header_format)
            
            # Write data with colors
            for row_idx, row in enumerate(records, start=1):
                topic = row[0] or '미분류'
                cell_format = topic_formats.get(topic, None)
                
                for col_idx, cell_value in enumerate(row):
                    worksheet.write(row_idx, col_idx, cell_value or '', cell_format)
            
            # Auto-adjust column widths
            for col_idx, header in enumerate(column_names):
                if col_idx == 0:  # Topic column
                    worksheet.set_column(col_idx, col_idx, 40)
                elif 'title' in header.lower():
                    worksheet.set_column(col_idx, col_idx, 50)
                elif 'author' in header.lower():
                    worksheet.set_column(col_idx, col_idx, 30)
                else:
                    worksheet.set_column(col_idx, col_idx, 15)
            
            workbook.close()
            excel_content = output.getvalue()
            output.close()
            
            # Return Excel file
            response = make_response(excel_content)
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            response.headers['Content-Disposition'] = f'attachment; filename=topic_analysis_{type_names[analysis_type]}_{room_id}.xlsx'
            
            return response
            
        except ImportError:
            # Fallback to CSV if xlsxwriter is not available
            import csv
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(column_names)
            
            # Write data grouped by topic with topic separators
            current_topic = None
            for row in records:
                topic = row[0] or '미분류'
                
                # Add separator row for new topic
                if current_topic != topic:
                    if current_topic is not None:
                        # Add empty row between topics
                        writer.writerow([''] * len(column_names))
                    # Add topic header row
                    topic_row = [f'=== {topic} ==='] + [''] * (len(column_names) - 1)
                    writer.writerow(topic_row)
                    current_topic = topic
                
                writer.writerow([cell or '' for cell in row])
            
            # Prepare CSV response
            csv_content = output.getvalue()
            output.close()
            
            response = make_response(csv_content)
            response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
            response.headers['Content-Disposition'] = f'attachment; filename=topic_analysis_{type_names[analysis_type]}_{room_id}.csv'
            
            return response
        
    except Exception as e:
        return f"주제 분포 분석 다운로드 중 오류가 발생했습니다: {str(e)}", 500

@app.route('/api/download_second_stage_candidates', methods=['POST'])
def download_second_stage_candidates():
    try:
        room_id = request.form.get('room_id')
        weight_1 = float(request.form.get('weight_1', 0))
        weight_10 = float(request.form.get('weight_10', 3))
        weight_25 = float(request.form.get('weight_25', 2))
        weight_sdg = float(request.form.get('weight_sdg', 1.5))
        weight_international = float(request.form.get('weight_international', 1.5))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 2단계 가중치 설정 (기존 Stage 2 분석과 동일)
        stage2_weights = {
            'journal_indicators': 0.45,
            'paper_performance': 0.45,
            'social_impact': 0.10
        }
        
        # 2단계용 세부 가중치
        journal_weights = {'snip': 0.35, 'citescore': 0.35, 'sjr': 0.30}
        paper_weights = {'fwci': 0.35, 'citations': 0.25, 'views': 0.25, 'fwvi': 0.15}
        social_weights = {'patents': 0.6, 'policy': 0.4}
        
        # 1단계 최고점을 받은 논문들을 대상으로 2단계 분석 수행
        query = '''
        SELECT *, 
               CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL) as stage1_score
        FROM publication 
        WHERE room_id = ? 
        AND (
            (COALESCE(is_1, 0) = 1 AND ? > 0) OR 
            (COALESCE(is_10, 0) = 1 AND ? > 0) OR 
            (COALESCE(is_25, 0) = 1 AND ? > 0) OR 
            (COALESCE(is_SDG, 0) = 1 AND ? > 0) OR 
            (COALESCE(is_international, 0) = 1 AND ? > 0)
        )
        AND CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL) = (
            SELECT MAX(CAST((COALESCE(is_1, 0) * ? + COALESCE(is_10, 0) * ? + COALESCE(is_25, 0) * ? + COALESCE(is_SDG, 0) * ? + COALESCE(is_international, 0) * ?) AS REAL))
            FROM publication 
            WHERE room_id = ? 
            AND (
                (COALESCE(is_1, 0) = 1 AND ? > 0) OR 
                (COALESCE(is_10, 0) = 1 AND ? > 0) OR 
                (COALESCE(is_25, 0) = 1 AND ? > 0) OR 
                (COALESCE(is_SDG, 0) = 1 AND ? > 0) OR 
                (COALESCE(is_international, 0) = 1 AND ? > 0)
            )
        )
        ORDER BY stage1_score DESC
        '''
        
        papers = conn.execute(query, (
            weight_1, weight_10, weight_25, weight_sdg, weight_international, room_id,
            weight_1, weight_10, weight_25, weight_sdg, weight_international,
            weight_1, weight_10, weight_25, weight_sdg, weight_international,
            weight_1, weight_10, weight_25, weight_sdg, weight_international, room_id,
            weight_1, weight_10, weight_25, weight_sdg, weight_international
        )).fetchall()
        
        if not papers:
            conn.close()
            return "2단계 분석 대상 논문이 없습니다.", 404
        
        # Get column names
        column_names = [description[0] for description in conn.execute('SELECT * FROM publication LIMIT 1').description]
        
        # Stage 2 분석 계산 (기존 로직과 동일)
        import math
        import statistics
        
        def safe_float(value):
            try:
                return float(value) if value is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
        
        def safe_log(value):
            try:
                val = float(value) if value is not None else 0.0
                return math.log(val + 1)  # log(0) 방지
            except (ValueError, TypeError, OverflowError):
                return 0.0
        
        def percentile_normalize(values):
            if not values:
                return [0.0] * len(values)
            try:
                sorted_vals = sorted([v for v in values if v is not None])
                if not sorted_vals:
                    return [0.0] * len(values)
                normalized = []
                for val in values:
                    if val is None:
                        normalized.append(0.0)
                    else:
                        rank = sum(1 for v in sorted_vals if v <= val)
                        normalized.append(rank / len(sorted_vals))
                return normalized
            except:
                return [0.0] * len(values)
        
        def winsorize_normalize(values, lower_percentile=5, upper_percentile=95):
            if not values:
                return [0.0] * len(values)
            try:
                clean_values = [v for v in values if v is not None]
                if not clean_values:
                    return [0.0] * len(values)
                
                lower_bound = statistics.quantile(clean_values, lower_percentile / 100)
                upper_bound = statistics.quantile(clean_values, upper_percentile / 100)
                
                winsorized = []
                for val in values:
                    if val is None:
                        winsorized.append(0.0)
                    else:
                        clamped = max(lower_bound, min(upper_bound, val))
                        winsorized.append(clamped)
                
                if max(winsorized) == min(winsorized):
                    return [0.5] * len(winsorized)
                
                min_val, max_val = min(winsorized), max(winsorized)
                return [(v - min_val) / (max_val - min_val) for v in winsorized]
            except:
                return [0.0] * len(values)
        
        # Convert to list of dicts for processing
        paper_data = []
        for paper in papers:
            paper_dict = dict(paper)
            # Type safety for calculations
            for key in paper_dict:
                if key not in ['title', 'record_id', 'eid', 'is_1', 'is_10', 'is_25', 'is_SDG', 'is_international']:
                    try:
                        paper_dict[key] = float(paper_dict[key]) if paper_dict[key] is not None else 0.0
                    except (ValueError, TypeError):
                        paper_dict[key] = 0.0
            paper_data.append(paper_dict)
        
        # Journal impact normalization
        snip_raw = [p['snip_publication_year'] for p in paper_data]
        snip_log = [safe_log(v) for v in snip_raw]
        snip_val_norm = winsorize_normalize(snip_log)
        snip_pct_norm = []
        for p in paper_data:
            try:
                val = float(p['snip_percentile_publication_year']) if p['snip_percentile_publication_year'] is not None else 0.0
                snip_pct_norm.append(val / 100)
            except (ValueError, TypeError):
                snip_pct_norm.append(0.0)
        snip_combined = [0.6 * val + 0.4 * pct for val, pct in zip(snip_val_norm, snip_pct_norm)]
        
        citescore_raw = [p['citescore_publication_year'] for p in paper_data]
        citescore_log = [safe_log(v) for v in citescore_raw]
        citescore_val_norm = winsorize_normalize(citescore_log)
        citescore_pct_norm = []
        for p in paper_data:
            try:
                val = float(p['citescore_percentile_publication_year']) if p['citescore_percentile_publication_year'] is not None else 0.0
                citescore_pct_norm.append(val / 100)
            except (ValueError, TypeError):
                citescore_pct_norm.append(0.0)
        citescore_combined = [0.6 * val + 0.4 * pct for val, pct in zip(citescore_val_norm, citescore_pct_norm)]
        
        sjr_raw = [p['sjr_publication_year'] for p in paper_data]
        sjr_log = [safe_log(v) for v in sjr_raw]
        sjr_val_norm = winsorize_normalize(sjr_log)
        sjr_pct_norm = []
        for p in paper_data:
            try:
                val = float(p['sjr_percentile_publication_year']) if p['sjr_percentile_publication_year'] is not None else 0.0
                sjr_pct_norm.append(val / 100)
            except (ValueError, TypeError):
                sjr_pct_norm.append(0.0)
        sjr_combined = [0.6 * val + 0.4 * pct for val, pct in zip(sjr_val_norm, sjr_pct_norm)]
        
        # Paper performance normalization
        fwci_norm = percentile_normalize([p['field_weighted_citation_impact'] for p in paper_data])
        citations_log = [safe_log(p['citations']) for p in paper_data]
        citations_norm = winsorize_normalize(citations_log)
        views_log = [safe_log(p['views']) for p in paper_data]
        views_norm = winsorize_normalize(views_log)
        fwvi_norm = percentile_normalize([p['field_weighted_view_impact'] for p in paper_data])
        
        # Social impact normalization
        patents_log = [safe_log(p['main_patent_families']) for p in paper_data]
        patents_norm = winsorize_normalize(patents_log)
        policy_log = [safe_log(p['policy_citations']) for p in paper_data]
        policy_norm = winsorize_normalize(policy_log)
        
        # Calculate final scores and add to records
        candidates_with_scores = []
        for i, paper in enumerate(paper_data):
            journal_score = (snip_combined[i] * journal_weights['snip'] + 
                           citescore_combined[i] * journal_weights['citescore'] + 
                           sjr_combined[i] * journal_weights['sjr']) * stage2_weights['journal_indicators']
            
            paper_score = (fwci_norm[i] * paper_weights['fwci'] + 
                          citations_norm[i] * paper_weights['citations'] + 
                          views_norm[i] * paper_weights['views'] + 
                          fwvi_norm[i] * paper_weights['fwvi']) * stage2_weights['paper_performance']
            
            social_score = (patents_norm[i] * social_weights['patents'] + 
                           policy_norm[i] * social_weights['policy']) * stage2_weights['social_impact']
            
            final_score = journal_score + paper_score + social_score
            
            # Add calculated scores to the record
            enhanced_paper = dict(paper)
            enhanced_paper['journal_score_calculated'] = f"{journal_score:.4f}"
            enhanced_paper['paper_score_calculated'] = f"{paper_score:.4f}"
            enhanced_paper['social_score_calculated'] = f"{social_score:.4f}"
            enhanced_paper['final_score_calculated'] = f"{final_score:.4f}"
            
            candidates_with_scores.append(enhanced_paper)
        
        # Sort by final score
        candidates_with_scores.sort(key=lambda x: float(x['final_score_calculated']), reverse=True)
        conn.close()
        
        # Create CSV content
        import io
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Enhanced headers with calculated scores
        enhanced_headers = column_names + ['journal_score_calculated', 'paper_score_calculated', 'social_score_calculated', 'final_score_calculated']
        writer.writerow(enhanced_headers)
        
        # Write data
        for candidate in candidates_with_scores:
            row = []
            for header in enhanced_headers:
                row.append(candidate.get(header, '') or '')
            writer.writerow(row)
        
        # Prepare response
        csv_content = output.getvalue()
        output.close()
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
        response.headers['Content-Disposition'] = f'attachment; filename=stage2_candidates_full_data_{room_id}.csv'
        
        return response
        
    except Exception as e:
        return f"2단계 CSV 다운로드 중 오류가 발생했습니다: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=0)