from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
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
    conn = sqlite3.connect('jbnu.db')
    conn.row_factory = sqlite3.Row
    return conn

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/room_manager')
def room_manager():
    return render_template('room_manager.html')

# 분석방 만들기
@app.route('/create_room')
def create_room():
    return render_template('create_room.html')

@app.route('/save_room', methods=['POST'])
def save_room():
    room_name = request.form.get('room_name')
    year_from = request.form.get('year_from')
    year_to = request.form.get('year_to')
    cutoff_date = request.form.get('cutoff_date')
    
    if not all([room_name, year_from, year_to, cutoff_date]):
        flash('모든 필드를 입력해주세요.')
        return redirect(url_for('create_room'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO room (room_name, year_from, year_to, cutoff_date)
            VALUES (?, ?, ?, ?)
        ''', (room_name, int(year_from), int(year_to), cutoff_date))
        
        room_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        flash(f'분석방 "{room_name}"이 생성되었습니다.')
        return redirect(url_for('unified_upload', room_id=room_id))
        
    except Exception as e:
        flash(f'분석방 생성 중 오류가 발생했습니다: {str(e)}')
        return redirect(url_for('create_room'))

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
        
        # 데이터 소스에 따른 플래그 설정
        if data_source == '전체논문데이터':
            is_paper = 1
        elif data_source == '1%':
            is_1 = 1
        elif data_source == '10%':
            is_10 = 1
        elif data_source == '25%':
            is_25 = 1
        elif data_source == 'SDGs':
            is_SDG = 1
        elif data_source == 'International':
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

def process_file_upload(room_id, data_category, data_source, filepath, filename, task_id):
    """백그라운드에서 파일 업로드를 처리하는 함수"""
    try:
        update_progress(task_id, 0, 100, "파일을 읽고 있습니다...")
        
        # 컬럼 매핑 로드
        column_mapping = load_column_mapping()
        
        # 파일 읽기
        if filename.endswith('.csv'):
            # CSV 파일을 더 유연하게 읽기 (20행이 헤더, 21행부터 데이터)
            try:
                df = pd.read_csv(filepath, encoding='utf-8-sig', header=19, skiprows=None)
            except:
                try:
                    df = pd.read_csv(filepath, encoding='cp949', header=19, skiprows=None)
                except:
                    try:
                        df = pd.read_csv(filepath, encoding='utf-8-sig', header=19, on_bad_lines='skip')
                    except:
                        df = pd.read_csv(filepath, encoding='utf-8-sig', header=19, sep=None, engine='python')
        else:
            df = pd.read_excel(filepath, header=19)
        
        update_progress(task_id, 5, 100, f"총 {len(df)}개 레코드를 처리합니다...")
        
        # DB 연결 및 room 정보 확인
        conn = get_db_connection()
        room = conn.execute('SELECT * FROM room WHERE room_id = ?', (room_id,)).fetchone()
        
        if not room:
            cleanup_progress(task_id)
            return {'success': False, 'error': '존재하지 않는 분석방입니다.'}
        
        cursor = conn.cursor()
        
        # 불리언 플래그 설정 (이전 코드와 동일)
        boolean_flags = {
            'is_paper': 0, 'is_1': 0, 'is_10': 0, 
            'is_25': 0, 'is_SDG': 0, 'is_international': 0
        }
        
        # 데이터 소스에 따른 플래그 설정
        if data_source in ['Scopus', 'Web of Science', 'KCI', '전체논문데이터']:
            boolean_flags['is_paper'] = 1
        elif data_source == '1%':
            boolean_flags['is_1'] = 1
        elif data_source == '10%':
            boolean_flags['is_10'] = 1
        elif data_source == '25%':
            boolean_flags['is_25'] = 1
        elif data_source == 'SDGs':
            boolean_flags['is_SDG'] = 1
        elif data_source == 'International':
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
            INSERT INTO file_uploads (room_id, filename, data_category, data_source, upload_date, record_count)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (room_id, filename, data_category, data_source or '', datetime.now().isoformat(), insert_count + update_count))
        
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
        
        if not data_category:
            return jsonify({'success': False, 'error': '데이터 카테고리를 선택해주세요.'})
        
        if data_category == '학술성과' and not data_source:
            return jsonify({'success': False, 'error': '학술성과의 경우 데이터 소스를 선택해주세요.'})
        
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
                result = process_file_upload(room_id, data_category, data_source, filepath, filename, task_id)
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
        with open(f'result_{task_id}.json', 'r') as f:
            result = json.load(f)
        # 결과 파일 정리
        os.remove(f'result_{task_id}.json')
        return jsonify(result)
    except:
        return jsonify({'success': False, 'error': '결과를 찾을 수 없습니다.'})
                
                # 데이터 소스에 따른 플래그 설정
                if data_source == 'Scopus':
                    boolean_flags['is_paper'] = 1
                elif data_source == 'Web of Science':
                    boolean_flags['is_paper'] = 1
                elif data_source == 'KCI':
                    boolean_flags['is_paper'] = 1
                elif data_source == '전체논문데이터':
                    boolean_flags['is_paper'] = 1
                elif data_source == '1%':
                    boolean_flags['is_1'] = 1
                elif data_source == '10%':
                    boolean_flags['is_10'] = 1
                elif data_source == '25%':
                    boolean_flags['is_25'] = 1
                elif data_source == 'SDGs':
                    boolean_flags['is_SDG'] = 1
                elif data_source == 'International':
                    boolean_flags['is_international'] = 1
                
                total_records = len(df)
                insert_count = 0
                update_count = 0
                error_count = 0
                
                for _, row in df.iterrows():
                    try:
                        # 매핑된 데이터 준비 (인덱스 기반)
                        mapped_data = {}
                        # CSV 파일의 컬럼 순서대로 매핑 (전체 68개 컬럼)
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
                        
                        for i, db_col in enumerate(column_order):
                            if i < len(df.columns):
                                value = row.iloc[i] if i < len(row) else None
                                # NaN 값을 None으로 변환
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
                            update_values = []
                            
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
                        print(f"Row error: {str(e)}")  # 디버그용
                        continue
                
                # 파일 업로드 기록 저장
                print(f"Saving upload record: room_id={room_id}, filename={filename}, data_category='{data_category}', data_source='{data_source}'")
                cursor.execute('''
                    INSERT INTO file_uploads (room_id, filename, data_category, data_source, upload_date, record_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (room_id, filename, data_category, data_source or '', datetime.now().isoformat(), insert_count + update_count))
                
                conn.commit()
                conn.close()
                
                # 업로드된 파일 삭제
                os.remove(filepath)
                
                return jsonify({
                    'success': True,
                    'total_records': total_records,
                    'insert_count': insert_count,
                    'update_count': update_count,
                    'error_count': error_count,
                    'success_count': insert_count + update_count
                })
                
            except Exception as e:
                return jsonify({'success': False, 'error': f'파일 처리 중 오류: {str(e)}'})
        else:
            return jsonify({'success': False, 'error': '허용되지 않는 파일 형식입니다.'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'업로드 중 오류가 발생했습니다: {str(e)}'})

# 분석
@app.route('/analysis')
def analysis():
    conn = get_db_connection()
    rooms = conn.execute('''
        SELECT * FROM room 
        ORDER BY room_id DESC
    ''').fetchall()
    conn.close()
    
    return render_template('analysis.html', rooms=rooms)

# 파일 삭제
@app.route('/delete_upload/<int:upload_id>', methods=['POST'])
def delete_upload(upload_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 업로드 정보 가져오기
        upload = cursor.execute('SELECT * FROM file_uploads WHERE upload_id = ?', (upload_id,)).fetchone()
        if not upload:
            return jsonify({'success': False, 'error': '존재하지 않는 업로드입니다.'})
        
        room_id = upload['room_id']
        data_source = upload['data_source']
        
        # 해당 불리언 플래그를 0으로 설정
        flag_column = None
        if data_source == '전체논문데이터':
            flag_column = 'is_paper'
        elif data_source == '1%':
            flag_column = 'is_1'
        elif data_source == '10%':
            flag_column = 'is_10'
        elif data_source == '25%':
            flag_column = 'is_25'
        elif data_source == 'SDGs':
            flag_column = 'is_SDG'
        elif data_source == 'International':
            flag_column = 'is_international'
        
        if flag_column:
            cursor.execute(f'UPDATE publication SET {flag_column} = 0 WHERE room_id = ?', (room_id,))
        
        # 업로드 기록 삭제
        cursor.execute('DELETE FROM file_uploads WHERE upload_id = ?', (upload_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API
@app.route('/api/rooms')
def api_rooms():
    conn = get_db_connection()
    rooms = conn.execute('SELECT * FROM room ORDER BY room_id DESC').fetchall()
    conn.close()
    
    data = []
    for room in rooms:
        data.append(dict(room))
    
    return jsonify(data)

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
    
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=0)