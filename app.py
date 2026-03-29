from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response, session
from functools import wraps
import sqlite3
import pandas as pd
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import csv
import json
import time
import threading
from deep_translator import GoogleTranslator

app = Flask(__name__)
app.secret_key = 'orap-secret-key-2024-secure'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# 기관별 데이터베이스 매핑
# 기관 정보 (DB에서 로드, 초기값은 하드코딩)
_DEFAULT_INSTITUTIONS = {
    'jbnu': {'name': '전북대학교', 'affiliation': 'Jeonbuk National University', 'db_file': 'jbnu.db'},
    'korea': {'name': '고려대학교', 'affiliation': 'Korea University', 'db_file': 'korea.db'},
}

def _load_institutions():
    """institutions 테이블에서 기관 정보 로드"""
    inst_db, inst_names, inst_affiliations = {}, {}, {}
    try:
        conn = sqlite3.connect(USERS_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='institutions'")
        if cursor.fetchone():
            cursor.execute("SELECT inst_key, inst_name, affiliation, db_file FROM institutions WHERE is_active = 1")
            for row in cursor.fetchall():
                inst_db[row[0]] = row[3]
                inst_names[row[0]] = row[1]
                inst_affiliations[row[0]] = row[2]
        conn.close()
    except Exception:
        pass
    # DB에 없으면 기본값 사용
    if not inst_db:
        for key, info in _DEFAULT_INSTITUTIONS.items():
            inst_db[key] = info['db_file']
            inst_names[key] = info['name']
            inst_affiliations[key] = info['affiliation']
    return inst_db, inst_names, inst_affiliations

INSTITUTION_DB, INSTITUTION_NAMES, INSTITUTION_AFFILIATIONS = _load_institutions()

def reload_institutions():
    """기관 정보 다시 로드 (추가/삭제 후)"""
    global INSTITUTION_DB, INSTITUTION_NAMES, INSTITUTION_AFFILIATIONS
    INSTITUTION_DB, INSTITUTION_NAMES, INSTITUTION_AFFILIATIONS = _load_institutions()

def init_institution_db(db_file):
    """새 기관 DB 파일 생성 및 테이블 초기화"""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(app_dir, db_file)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # publication 테이블
    cursor.execute('''CREATE TABLE IF NOT EXISTS publication (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, authors TEXT, number_of_authors TEXT, scopus_author_ids TEXT,
        year TEXT, full_date TEXT, scopus_source_title TEXT, volume TEXT, issue TEXT, pages TEXT,
        article_number TEXT, issn TEXT, source_id TEXT, source_type TEXT, language TEXT,
        publisher TEXT, institution_ids TEXT, sector TEXT,
        snip_publication_year TEXT, snip_percentile_publication_year TEXT,
        citescore_publication_year TEXT, citescore_percentile_publication_year TEXT,
        sjr_publication_year TEXT, sjr_percentile_publication_year TEXT,
        field_weighted_view_impact TEXT, views TEXT, citations TEXT,
        field_weighted_citation_impact TEXT, field_citation_average TEXT,
        outputs_in_top_citation_percentiles_per_percentile TEXT,
        field_weighted_outputs_in_top_citation_percentiles_per_percentile TEXT,
        main_patent_families TEXT, policy_citations TEXT, reference TEXT, abstract TEXT,
        doi TEXT, publication_type TEXT, open_access TEXT, eid TEXT, pubmed_id TEXT,
        institutions TEXT, number_of_institutions TEXT, scopus_affiliation_ids TEXT,
        scopus_affiliation_names TEXT, scopus_author_id_first_author TEXT,
        scopus_author_id_last_author TEXT, scopus_author_id_corresponding_author TEXT,
        scopus_author_id_single_author TEXT, country_region TEXT,
        number_of_countries_regions TEXT,
        all_science_journal_classification_asjc_code TEXT,
        all_science_journal_classification_asjc_field_name TEXT,
        quacquarelli_symonds_qs_subject_area_code TEXT,
        quacquarelli_symonds_qs_subject_area_field_name TEXT,
        quacquarelli_symonds_qs_subject_code TEXT,
        quacquarelli_symonds_qs_subject_field_name TEXT,
        times_higher_education_the_code TEXT, times_higher_education_the_field_name TEXT,
        anzsrc_for_2020_parent_code TEXT, anzsrc_for_2020_parent_name TEXT,
        anzsrc_for_2020_code TEXT, anzsrc_for_2020_name TEXT,
        sustainable_development_goals_2025 TEXT,
        topic_cluster_name TEXT, topic_cluster_number TEXT, topic_cluster_prominence_percentile TEXT,
        topic_name TEXT, topic_number TEXT, topic_prominence_percentile TEXT,
        publication_link_to_topic_strength TEXT,
        is_paper INTEGER DEFAULT 0, is_1 INTEGER DEFAULT 0, is_10 INTEGER DEFAULT 0,
        is_25 INTEGER DEFAULT 0, is_SDG INTEGER DEFAULT 0, is_international INTEGER DEFAULT 0,
        is_patent_cited INTEGER DEFAULT 0, is_policy_cited INTEGER DEFAULT 0,
        is_coauthored INTEGER DEFAULT 0, is_academic_corporate INTEGER DEFAULT 0,
        j_point REAL DEFAULT 0, a_point REAL DEFAULT 0, s_point REAL DEFAULT 0, t_point REAL DEFAULT 0
    )''')

    # author 테이블
    cursor.execute('''CREATE TABLE IF NOT EXISTS author (
        author_id INTEGER PRIMARY KEY AUTOINCREMENT,
        scopus_author_id TEXT UNIQUE, name TEXT, scholarly_output INTEGER,
        most_recent_publication INTEGER, citations INTEGER, citations_per_publication REAL,
        field_weighted_citation_impact REAL, h_index INTEGER, output_in_top_10_percentile INTEGER,
        oldest_publication INTEGER, scopus_author_profile TEXT, primary_affiliation TEXT,
        orcid TEXT, created_at TEXT, updated_at TEXT
    )''')

    # researcher_score 테이블
    cursor.execute('''CREATE TABLE IF NOT EXISTS researcher_score (
        score_id INTEGER PRIMARY KEY AUTOINCREMENT,
        author_id INTEGER, scopus_author_id TEXT, name TEXT, scholarly_output INTEGER,
        citations INTEGER, h_index INTEGER, profile_url TEXT,
        fwci_mean REAL, fwci_median REAL,
        score_fwci_mean REAL, score_fwci_median REAL,
        score_top_cited REAL, score_top_journal REAL, score_intl_collab REAL,
        score_core_mean REAL, score_core_median REAL,
        score_sdg REAL, score_oa REAL, score_prominence REAL, score_secondary REAL,
        score_total_mean REAL, score_total_median REAL,
        top_10_pct_count INTEGER, intl_collab_count INTEGER, intl_collab_fwci REAL,
        top_journal_pct REAL, has_sdg INTEGER, has_oa INTEGER, avg_topic_prominence REAL
    )''')

    # 기타 필수 테이블
    cursor.execute('''CREATE TABLE IF NOT EXISTS data_snapshot (
        snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_name TEXT NOT NULL, description TEXT,
        collection_date TEXT NOT NULL, year_from INTEGER NOT NULL, year_to INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft', applied_at TEXT, applied_by TEXT,
        total_publications INTEGER DEFAULT 0, total_authors INTEGER DEFAULT 0,
        created_at TEXT, created_by TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS snapshot_files (
        file_id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL, filename TEXT NOT NULL, original_filename TEXT NOT NULL,
        data_type TEXT NOT NULL DEFAULT 'publication', file_size INTEGER DEFAULT 0,
        record_count INTEGER DEFAULT 0, upload_date TEXT,
        FOREIGN KEY (snapshot_id) REFERENCES data_snapshot(snapshot_id))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS institution_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric_year INTEGER NOT NULL, metric_key TEXT NOT NULL,
        metric_value REAL, metric_unit TEXT,
        source TEXT DEFAULT '대학공시',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(metric_year, metric_key))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS scoring_presets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, description TEXT,
        is_system INTEGER DEFAULT 0, is_default INTEGER DEFAULT 0,
        total_core INTEGER DEFAULT 80, total_supplementary INTEGER DEFAULT 10,
        pct_fwci INTEGER DEFAULT 25, pct_top10 INTEGER DEFAULT 25,
        pct_top_journal INTEGER DEFAULT 25, pct_intl_collab INTEGER DEFAULT 25,
        pct_sdg INTEGER DEFAULT 30, pct_oa INTEGER DEFAULT 30, pct_topic INTEGER DEFAULT 40,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # 시스템 프리셋
    cursor.execute('SELECT COUNT(*) FROM scoring_presets WHERE is_system = 1')
    if cursor.fetchone()[0] == 0:
        presets = [
            ('기본 설정', '균형 잡힌 기본 가중치', 1, 1, 80, 10, 25, 25, 25, 25, 30, 30, 40),
            ('인용 중심', 'FWCI와 Top 10% 강조', 1, 0, 80, 10, 35, 35, 15, 15, 30, 30, 40),
            ('국제협력 중심', '국제공동연구 강조', 1, 0, 80, 10, 20, 20, 20, 40, 30, 30, 40),
            ('품질 중심', '상위저널 게재 강조', 1, 0, 80, 10, 30, 20, 35, 15, 30, 30, 40),
        ]
        cursor.executemany('''INSERT INTO scoring_presets
            (name, description, is_system, is_default, total_core, total_supplementary,
             pct_fwci, pct_top10, pct_top_journal, pct_intl_collab, pct_sdg, pct_oa, pct_topic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', presets)

    conn.commit()
    conn.close()
    return db_path

# 사용자 데이터베이스 초기화
USERS_DB = 'users.db'

def init_users_db():
    """사용자 데이터베이스 초기화"""
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()

    # users 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            department TEXT,
            job_description TEXT,
            institution TEXT,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # institutions 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS institutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inst_key TEXT UNIQUE NOT NULL,
            inst_name TEXT NOT NULL,
            affiliation TEXT NOT NULL,
            db_file TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 기본 기관 삽입
    for key, info in _DEFAULT_INSTITUTIONS.items():
        cursor.execute('SELECT id FROM institutions WHERE inst_key = ?', (key,))
        if not cursor.fetchone():
            cursor.execute('INSERT INTO institutions (inst_key, inst_name, affiliation, db_file) VALUES (?, ?, ?, ?)',
                           (key, info['name'], info['affiliation'], info['db_file']))

    # 초기 사용자 추가 (존재하지 않는 경우만)
    initial_users = [
        ('user001', 'user0011234!', 'jbnu', 'user'),
        ('user100', 'user1001234!', 'korea', 'user'),
        ('jbnu_admin', 'jbnuadmin1234!', 'jbnu', 'institution_admin'),
        ('korea_admin', 'koreaadmin1234!', 'korea', 'institution_admin'),
        ('admin', 'admin1234!', None, 'admin')
    ]

    for username, password, institution, role in initial_users:
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if not cursor.fetchone():
            cursor.execute(
                'INSERT INTO users (username, password, institution, role) VALUES (?, ?, ?, ?)',
                (username, password, institution, role)
            )

    conn.commit()
    conn.close()

# 앱 시작 시 users DB 초기화
init_users_db()


# 활동 로그 테이블 초기화
def init_activity_logs_db():
    """활동 로그 테이블 초기화"""
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            user_name TEXT,
            institution TEXT,
            action_type TEXT,
            action_detail TEXT,
            page_url TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_activity_logs_db()


@app.context_processor
def inject_active_snapshot():
    """모든 페이지에 활성 스냅샷 정보 주입"""
    try:
        if not session.get('authenticated'):
            return {'active_snapshot': None}
        conn = get_db_connection()
        # 테이블 존재 여부 먼저 확인
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='data_snapshot'"
        ).fetchone()
        if not table_exists:
            conn.close()
            return {'active_snapshot': None}
        snapshot = conn.execute(
            "SELECT snapshot_name, collection_date, applied_at, year_from, year_to, "
            "total_publications, total_authors FROM data_snapshot WHERE status = 'applied' LIMIT 1"
        ).fetchone()
        conn.close()
        return {'active_snapshot': dict(snapshot) if snapshot else None}
    except Exception:
        return {'active_snapshot': None}


def log_activity(action_type, action_detail='', page_url=None):
    """사용자 활동 로그 기록"""
    try:
        username = session.get('username', '')
        if not username:
            return

        conn = sqlite3.connect(USERS_DB)
        cursor = conn.cursor()

        # 사용자 정보 조회
        cursor.execute('SELECT id, name FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        user_id = user[0] if user else None
        user_name = user[1] if user else ''

        cursor.execute('''
            INSERT INTO activity_logs
            (user_id, username, user_name, institution, action_type, action_detail, page_url, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            username,
            user_name,
            session.get('institution', ''),
            action_type,
            action_detail,
            page_url or request.path,
            request.remote_addr,
            request.user_agent.string[:200] if request.user_agent else ''
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Activity log error: {e}")


def get_institution_affiliation(institution=None):
    """현재 기관의 영문 소속명 반환"""
    if institution is None:
        institution = session.get('institution', 'jbnu')
    return INSTITUTION_AFFILIATIONS.get(institution, 'Jeonbuk National University')


def login_required(f):
    """로그인 필수 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        if not session.get('institution'):
            # 단일 기관 모드가 아닌 경우에만 기관 선택 페이지로
            if not session.get('single_institution'):
                return redirect(url_for('select_institution'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """관리자 권한 필수 데코레이터 (슈퍼관리자 또는 기관관리자)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        user_role = session.get('user_role')
        if user_role not in ('admin', 'institution_admin'):
            flash('관리자 권한이 필요합니다.')
            return redirect(url_for('researcher_ranking'))
        return f(*args, **kwargs)
    return decorated_function


def super_admin_required(f):
    """슈퍼관리자(admin) 전용 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        if session.get('user_role') != 'admin':
            flash('슈퍼관리자 권한이 필요합니다.')
            return redirect(url_for('researcher_ranking'))
        return f(*args, **kwargs)
    return decorated_function


UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

# 컬럼 매핑 (70컬럼/67컬럼 형식)
COLUMN_ORDER_70 = [
    'title', 'authors', 'number_of_authors', 'scopus_author_ids',
    'year', 'full_date', 'scopus_source_title', 'volume', 'issue', 'pages',
    'article_number', 'issn', 'source_id', 'source_type',
    'publisher', 'language',
    'snip_publication_year', 'snip_percentile_publication_year',
    'citescore_publication_year', 'citescore_percentile_publication_year',
    'sjr_publication_year', 'sjr_percentile_publication_year',
    'field_weighted_view_impact', 'views', 'citations',
    'field_weighted_citation_impact', 'field_citation_average',
    'outputs_in_top_citation_percentiles_per_percentile',
    'field_weighted_outputs_in_top_citation_percentiles_per_percentile',
    'main_patent_families', 'policy_citations', 'reference', 'abstract',
    'doi', 'publication_type', 'open_access', 'eid', 'pubmed_id',
    'institutions', 'institution_ids', 'sector',
    'number_of_institutions', 'scopus_affiliation_ids',
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

COLUMN_ORDER_67 = [
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

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 스냅샷 파일 저장 디렉토리
SNAPSHOT_FOLDER = 'snapshots'
if not os.path.exists(SNAPSHOT_FOLDER):
    os.makedirs(SNAPSHOT_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SNAPSHOT_FOLDER'] = SNAPSHOT_FOLDER

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

def get_db_connection(institution=None):
    import os
    import shutil

    # 기관 결정: 파라미터 > 세션 > 기본값(jbnu)
    if institution is None:
        institution = session.get('institution', 'jbnu')

    db_filename = INSTITUTION_DB.get(institution, 'jbnu.db')

    # 앱 디렉토리 기준 경로
    app_dir = os.path.dirname(os.path.abspath(__file__))

    db_path = os.path.join(app_dir, db_filename)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# 데이터베이스 마이그레이션 함수
def migrate_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # publication 테이블에 점수 컬럼들이 있는지 확인
    cursor.execute("PRAGMA table_info(publication)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # 필요한 컬럼들 추가
    score_columns = ['j_point', 'a_point', 's_point', 't_point']
    for column in score_columns:
        if column not in columns:
            try:
                cursor.execute(f"ALTER TABLE publication ADD COLUMN {column} REAL DEFAULT 0.0")
                print(f"Added column: {column}")
            except sqlite3.Error as e:
                print(f"Error adding column {column}: {e}")

    # 새 데이터 컬럼 추가 (70컬럼 CSV 형식 대응)
    new_text_columns = ['publisher', 'institution_ids', 'sector']
    for column in new_text_columns:
        if column not in columns:
            try:
                cursor.execute(f"ALTER TABLE publication ADD COLUMN {column} TEXT")
                print(f"Added column: {column}")
            except sqlite3.Error as e:
                print(f"Error adding column {column}: {e}")

    # 새 불리언 플래그 컬럼 추가
    new_flag_columns = ['is_patent_cited', 'is_policy_cited', 'is_coauthored']
    for column in new_flag_columns:
        if column not in columns:
            try:
                cursor.execute(f"ALTER TABLE publication ADD COLUMN {column} INTEGER DEFAULT 0")
                print(f"Added column: {column}")
            except sqlite3.Error as e:
                print(f"Error adding column {column}: {e}")

    # author 테이블 생성 (기존 스키마와 호환)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS author (
            author_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scopus_author_id TEXT UNIQUE,
            name TEXT,
            scholarly_output INTEGER,
            most_recent_publication INTEGER,
            citations INTEGER,
            citations_per_publication REAL,
            field_weighted_citation_impact REAL,
            h_index INTEGER,
            output_in_top_10_percentile INTEGER,
            oldest_publication INTEGER,
            scopus_author_profile TEXT,
            primary_affiliation TEXT,
            orcid TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # publication 테이블 중복 제거 (EID 기반)
    cursor.execute("""
        SELECT eid, COUNT(*) as cnt FROM publication
        WHERE eid IS NOT NULL AND eid != ''
        GROUP BY eid HAVING cnt > 1
    """)
    dup_eids = cursor.fetchall()

    if dup_eids:
        print(f"Deduplicating {len(dup_eids)} duplicate EID groups...")
        boolean_flags = ['is_paper', 'is_1', 'is_10', 'is_25', 'is_SDG', 'is_international']
        total_deleted = 0

        for row in dup_eids:
            eid = row[0]
            # 해당 EID의 모든 레코드 조회
            cursor.execute("""
                SELECT record_id, {} FROM publication
                WHERE eid = ? ORDER BY record_id DESC
            """.format(', '.join(boolean_flags)), (eid,))
            records = cursor.fetchall()

            # 가장 높은 record_id를 유지할 레코드로 선택
            keep_id = records[0][0]

            # boolean 플래그 OR 병합
            merged_flags = {}
            for flag_idx, flag in enumerate(boolean_flags):
                merged_flags[flag] = max(r[1 + flag_idx] or 0 for r in records)

            # 유지할 레코드 업데이트
            update_parts = []
            for flag, value in merged_flags.items():
                update_parts.append(f"{flag} = {value}")
            cursor.execute(f"""
                UPDATE publication SET {', '.join(update_parts)}
                WHERE record_id = ?
            """, (keep_id,))

            # 나머지 레코드 삭제
            delete_ids = [r[0] for r in records[1:]]
            if delete_ids:
                placeholders = ', '.join(['?' for _ in delete_ids])
                cursor.execute(f"DELETE FROM publication WHERE record_id IN ({placeholders})", delete_ids)
                total_deleted += len(delete_ids)

        print(f"Deleted {total_deleted} duplicate records")

    # DOI 기반 중복 제거 (EID 없는 레코드)
    cursor.execute("""
        SELECT doi, COUNT(*) as cnt FROM publication
        WHERE (eid IS NULL OR eid = '') AND doi IS NOT NULL AND doi != ''
        GROUP BY doi HAVING cnt > 1
    """)
    dup_dois = cursor.fetchall()

    if dup_dois:
        print(f"Deduplicating {len(dup_dois)} duplicate DOI groups (no EID)...")
        total_deleted_doi = 0

        for row in dup_dois:
            doi = row[0]
            cursor.execute("""
                SELECT record_id, {} FROM publication
                WHERE (eid IS NULL OR eid = '') AND doi = ? ORDER BY record_id DESC
            """.format(', '.join(boolean_flags)), (doi,))
            records = cursor.fetchall()

            keep_id = records[0][0]

            merged_flags = {}
            for flag_idx, flag in enumerate(boolean_flags):
                merged_flags[flag] = max(r[1 + flag_idx] or 0 for r in records)

            update_parts = []
            for flag, value in merged_flags.items():
                update_parts.append(f"{flag} = {value}")
            cursor.execute(f"""
                UPDATE publication SET {', '.join(update_parts)}
                WHERE record_id = ?
            """, (keep_id,))

            delete_ids = [r[0] for r in records[1:]]
            if delete_ids:
                placeholders = ', '.join(['?' for _ in delete_ids])
                cursor.execute(f"DELETE FROM publication WHERE record_id IN ({placeholders})", delete_ids)
                total_deleted_doi += len(delete_ids)

        print(f"Deleted {total_deleted_doi} duplicate DOI records")

    # strategic_field_config 테이블 생성 (연구분야분석용)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategic_field_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL,
            keywords TEXT,
            display_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 기본 데이터가 없으면 초기화
    cursor.execute("SELECT COUNT(*) FROM strategic_field_config")
    if cursor.fetchone()[0] == 0:
        default_fields = [
            # 에너지
            ('에너지', '에너지 생산', '["energy production", "power generation", "solar", "wind power", "photovoltaic", "solar cell"]', 1),
            ('에너지', '에너지 변환', '["energy conversion", "power conversion", "inverter", "transformer", "power electronics"]', 2),
            ('에너지', '에너지 저장', '["energy storage", "battery", "ESS", "supercapacitor", "lithium-ion", "secondary battery"]', 3),
            ('에너지', '수소에너지', '["hydrogen", "fuel cell", "electrolysis", "H2", "PEMFC", "SOFC"]', 4),
            # 바이오
            ('바이오', '레드바이오(제약)', '["pharmaceutical", "drug discovery", "therapeutics", "clinical trial", "drug delivery", "biopharmaceutical"]', 1),
            # 농생명
            ('농생명', '스마트팜', '["smart farm", "precision agriculture", "vertical farm", "hydroponics", "greenhouse", "IoT agriculture"]', 1),
            ('농생명', '지능형 농기계', '["agricultural robot", "farm machinery", "tractor", "harvester", "autonomous farming", "agricultural automation"]', 2),
            # 미래 모빌리티
            ('미래모빌리티', '자율주행', '["autonomous driving", "self-driving", "ADAS", "driverless", "autonomous vehicle", "lidar"]', 1),
            ('미래모빌리티', 'UAM', '["urban air mobility", "air taxi", "eVTOL", "flying car", "advanced air mobility", "AAM"]', 2),
            ('미래모빌리티', '드론', '["drone", "UAV", "unmanned aerial", "quadcopter", "multirotor", "UAS"]', 3),
            ('미래모빌리티', '항공', '["aerospace", "aviation", "aircraft", "flight", "aerodynamics", "propulsion"]', 4),
            ('미래모빌리티', '방산(방위산업)', '["defense", "military", "weapon", "missile", "radar", "stealth"]', 5),
            ('미래모빌리티', '로봇', '["robot", "robotics", "manipulator", "humanoid", "cobot", "industrial robot"]', 6),
        ]
        cursor.executemany("""
            INSERT INTO strategic_field_config (category, subcategory, keywords, display_order)
            VALUES (?, ?, ?, ?)
        """, default_fields)
        print("Initialized strategic_field_config with default data")

    # ESG 카테고리 추가 (없으면)
    cursor.execute("SELECT COUNT(*) FROM strategic_field_config WHERE category LIKE 'ESG%'")
    if cursor.fetchone()[0] == 0:
        esg_fields = [
            # ESG-E (환경)
            ('ESG-E(환경)', '기후변화·탄소', '["climate change", "carbon", "CO2", "greenhouse gas", "GHG", "decarbonization", "net zero", "carbon neutral"]', 1),
            ('ESG-E(환경)', '재생에너지', '["renewable energy", "solar energy", "wind energy", "clean energy", "green energy", "sustainable energy"]', 2),
            ('ESG-E(환경)', '환경오염·정화', '["pollution", "water treatment", "air quality", "soil contamination", "waste management", "remediation"]', 3),
            ('ESG-E(환경)', '생태계·생물다양성', '["biodiversity", "ecosystem", "conservation", "endangered species", "habitat", "ecological"]', 4),
            ('ESG-E(환경)', '순환경제·자원', '["circular economy", "recycling", "waste reduction", "resource efficiency", "upcycling", "sustainable materials"]', 5),
            # ESG-S (사회)
            ('ESG-S(사회)', '공중보건·의료', '["public health", "healthcare", "disease prevention", "epidemiology", "global health", "health equity"]', 1),
            ('ESG-S(사회)', '교육·인재양성', '["education", "STEM education", "e-learning", "higher education", "workforce development", "human capital"]', 2),
            ('ESG-S(사회)', '사회적 형평성', '["social equity", "inequality", "diversity", "inclusion", "gender equality", "social justice"]', 3),
            ('ESG-S(사회)', '식품안전·식량', '["food safety", "food security", "nutrition", "agriculture", "crop", "sustainable food"]', 4),
            ('ESG-S(사회)', '지역사회·삶의질', '["community development", "quality of life", "well-being", "urban planning", "rural development", "social welfare"]', 5),
            # ESG-G (지배구조)
            ('ESG-G(지배구조)', '연구윤리·투명성', '["research ethics", "transparency", "open science", "reproducibility", "data sharing", "peer review"]', 1),
            ('ESG-G(지배구조)', '산학협력·기술이전', '["industry-academia", "technology transfer", "patent", "commercialization", "startup", "spin-off"]', 2),
            ('ESG-G(지배구조)', '데이터 거버넌스', '["data governance", "data privacy", "cybersecurity", "information security", "GDPR", "data protection"]', 3),
            ('ESG-G(지배구조)', 'AI 윤리·규제', '["AI ethics", "responsible AI", "algorithmic fairness", "bias", "regulation", "trustworthy AI"]', 4),
        ]
        cursor.executemany("""
            INSERT INTO strategic_field_config (category, subcategory, keywords, display_order)
            VALUES (?, ?, ?, ?)
        """, esg_fields)
        print("Initialized ESG categories in strategic_field_config")

    # data_snapshot 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_snapshot (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_name TEXT NOT NULL,
            description TEXT,
            collection_date TEXT NOT NULL,
            year_from INTEGER NOT NULL,
            year_to INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            applied_at TEXT,
            applied_by TEXT,
            total_publications INTEGER DEFAULT 0,
            total_authors INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            created_by TEXT
        )
    """)

    # snapshot_files 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS snapshot_files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            data_type TEXT NOT NULL DEFAULT 'publication',
            file_size INTEGER DEFAULT 0,
            record_count INTEGER DEFAULT 0,
            upload_date TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (snapshot_id) REFERENCES data_snapshot(snapshot_id)
        )
    """)

    # 기존 데이터가 있고 스냅샷이 없으면 초기 스냅샷 자동 생성
    cursor.execute("SELECT COUNT(*) FROM publication")
    pub_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM data_snapshot")
    snap_count = cursor.fetchone()[0]
    if pub_count > 0 and snap_count == 0:
        cursor.execute("SELECT COUNT(*) FROM author")
        author_count = cursor.fetchone()[0]
        cursor.execute("SELECT MIN(year), MAX(year) FROM publication WHERE year IS NOT NULL")
        year_row = cursor.fetchone()
        min_year = year_row[0] or 2020
        max_year = year_row[1] or 2026
        cursor.execute("""
            INSERT INTO data_snapshot (snapshot_name, description, collection_date, year_from, year_to,
                                       status, applied_at, total_publications, total_authors, created_by)
            VALUES (?, ?, datetime('now'), ?, ?, 'applied', datetime('now'), ?, ?, 'system')
        """, ('초기 데이터', '기존 데이터에서 자동 생성된 스냅샷', min_year, max_year, pub_count, author_count))
        print(f"Created initial snapshot: {pub_count} publications, {author_count} authors")

    conn.commit()
    conn.close()

# 애플리케이션 시작 시 데이터베이스 마이그레이션 실행
try:
    print("Starting database migration...")
    migrate_database()
    print("Database migration completed successfully")
except Exception as e:
    print(f"Database migration failed: {e}")
    print("Continuing with application startup...")

# ============================================
# 인증 및 기관 선택 라우트
# ============================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """로그인 페이지"""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        # 사용자 데이터베이스에서 인증
        conn = sqlite3.connect(USERS_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['authenticated'] = True
            session['username'] = user['username']
            session['user_role'] = user['role']

            # 로그인 활동 기록
            log_activity('로그인', f"사용자: {user['username']}")

            if user['role'] == 'admin':
                # 관리자는 기관 선택 가능
                session['single_institution'] = False
                return redirect(url_for('select_institution'))
            elif user['institution']:
                # 기관 사용자는 해당 기관으로 바로 접속
                session['institution'] = user['institution']
                session['institution_name'] = INSTITUTION_NAMES.get(user['institution'], user['institution'])
                session['single_institution'] = True
                return redirect(url_for('researcher_ranking'))
            else:
                # 기관 정보 없으면 선택 화면으로
                session['single_institution'] = False
                return redirect(url_for('select_institution'))
        else:
            return render_template('login.html', error='아이디 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html')


@app.route('/logout')
def logout():
    """로그아웃"""
    log_activity('로그아웃', '')
    session.clear()
    return redirect(url_for('login'))


@app.route('/select_institution')
def select_institution():
    """기관 선택 페이지"""
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template('select_institution.html', institutions=INSTITUTION_NAMES)


@app.route('/select_institution/<institution>')
def select_institution_action(institution):
    """기관 선택 처리"""
    if not session.get('authenticated'):
        return redirect(url_for('login'))

    if institution in INSTITUTION_DB:
        session['institution'] = institution
        session['institution_name'] = INSTITUTION_NAMES.get(institution, institution)
        return redirect(url_for('researcher_ranking'))
    else:
        flash('잘못된 기관 선택입니다.')
        return redirect(url_for('select_institution'))


@app.route('/switch_institution')
def switch_institution():
    """기관 전환 (기관 선택 화면으로)"""
    if 'institution' in session:
        del session['institution']
    return redirect(url_for('select_institution'))


# 메인 페이지 - 연구자 랭킹으로 리다이렉트
@app.route('/')
def index():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    if not session.get('institution'):
        return redirect(url_for('select_institution'))
    return redirect(url_for('researcher_ranking'))


# ============================================================
# 우수 연구자 점수 산출 시스템 (Excellent Researcher Scoring)
# ============================================================
# 우수 연구자 점수 산출 시스템 (Excellent Researcher Scoring)
# ============================================================

def calculate_researcher_score(author_data, pub_stats):
    """
    연구자 점수 계산 함수

    핵심지표 (80점 만점):
    - FWCI: 35점
    - Top 10% 피인용 논문: 20점
    - 상위저널 비율: 15점
    - 국제협력 FWCI: 10점

    보조지표 (10점 만점):
    - SDG 관련: 3점
    - Open Access: 2점
    - Topic Prominence: 5점

    총점: 90점 만점
    """
    scores = {}

    # 1. FWCI 점수 (35점 만점)
    fwci = author_data.get('field_weighted_citation_impact', 0) or 0
    if fwci >= 10:
        scores['fwci'] = 35
    elif fwci >= 8:
        scores['fwci'] = 30
    elif fwci >= 6:
        scores['fwci'] = 25
    elif fwci >= 4:
        scores['fwci'] = 20
    elif fwci >= 2:
        scores['fwci'] = 15
    else:
        scores['fwci'] = 10

    # 2. Top 10% 피인용 논문 점수 (20점 만점)
    top_10_count = author_data.get('output_in_top_10_percentile', 0) or 0
    if top_10_count >= 3:
        scores['top_cited'] = 20
    elif top_10_count >= 1:
        scores['top_cited'] = 15
    else:
        scores['top_cited'] = 10

    # 3. 상위 저널 비율 점수 (15점 만점)
    # SNIP, CiteScore, SJR 중 하나라도 상위 10% (percentile <= 10) 인 논문 비율
    top_journal_pct = pub_stats.get('top_journal_percentage', 0)
    if top_journal_pct >= 10:  # 상위저널 비율 10% 이상이면 상위 10%로 판정
        scores['top_journal'] = 15
    else:
        scores['top_journal'] = 5

    # 4. 국제협력 FWCI 점수 (10점 만점)
    intl_fwci = pub_stats.get('international_collab_fwci', None)
    if intl_fwci is None or intl_fwci == 0:
        scores['intl_collab'] = 0
    elif intl_fwci >= 2.0:
        scores['intl_collab'] = 10
    elif intl_fwci >= 1.5:
        scores['intl_collab'] = 7
    elif intl_fwci >= 1.0:
        scores['intl_collab'] = 4
    else:
        scores['intl_collab'] = 1

    # 핵심지표 소계
    scores['core_total'] = scores['fwci'] + scores['top_cited'] + scores['top_journal'] + scores['intl_collab']

    # 5. SDG 관련 점수 (3점 만점)
    has_sdg = pub_stats.get('has_sdg_publications', False)
    scores['sdg'] = 3 if has_sdg else 0

    # 6. Open Access 점수 (2점 만점)
    has_oa = pub_stats.get('has_open_access', False)
    scores['open_access'] = 2 if has_oa else 0

    # 7. Topic Prominence 점수 (5점 만점)
    avg_prominence = pub_stats.get('avg_topic_prominence', 0)
    scores['topic_prominence'] = 5 if avg_prominence >= 90 else 0

    # 보조지표 소계
    scores['secondary_total'] = scores['sdg'] + scores['open_access'] + scores['topic_prominence']

    # 총점
    scores['total'] = scores['core_total'] + scores['secondary_total']

    return scores


def get_author_publication_stats(conn, scopus_author_id):
    """
    저자의 논문 통계 조회 (저자 ID 기반)
    """
    cursor = conn.cursor()

    # 해당 저자가 참여한 논문들 조회
    # scopus_author_ids 컬럼에서 저자 ID가 포함된 논문들 검색
    cursor.execute("""
        SELECT
            field_weighted_citation_impact,
            is_international,
            snip_percentile_publication_year,
            citescore_percentile_publication_year,
            sjr_percentile_publication_year,
            sustainable_development_goals_2025,
            open_access,
            topic_prominence_percentile
        FROM publication
        WHERE scopus_author_ids LIKE ?
    """, (f'%{scopus_author_id}%',))

    publications = cursor.fetchall()

    stats = {
        'total_publications': len(publications),
        'international_collab_count': 0,
        'international_collab_fwci_sum': 0,
        'international_collab_fwci': None,
        'top_journal_count': 0,
        'top_journal_percentage': 0,
        'has_sdg_publications': False,
        'has_open_access': False,
        'topic_prominence_sum': 0,
        'topic_prominence_count': 0,
        'avg_topic_prominence': 0
    }

    for pub in publications:
        fwci = pub['field_weighted_citation_impact']
        is_intl = pub['is_international']
        snip_pct = pub['snip_percentile_publication_year']
        citescore_pct = pub['citescore_percentile_publication_year']
        sjr_pct = pub['sjr_percentile_publication_year']
        sdg = pub['sustainable_development_goals_2025']
        oa = pub['open_access']
        topic_prom = pub['topic_prominence_percentile']

        # 국제협력 논문 통계
        if is_intl == 1 and fwci:
            try:
                fwci_val = float(fwci)
                stats['international_collab_count'] += 1
                stats['international_collab_fwci_sum'] += fwci_val
            except (ValueError, TypeError):
                pass

        # 상위 저널 판단 (SNIP, CiteScore, SJR 중 하나라도 percentile <= 10)
        is_top_journal = False
        for pct in [snip_pct, citescore_pct, sjr_pct]:
            if pct:
                try:
                    if int(pct) <= 10:
                        is_top_journal = True
                        break
                except (ValueError, TypeError):
                    pass
        if is_top_journal:
            stats['top_journal_count'] += 1

        # SDG 관련 여부
        if sdg and str(sdg).strip():
            stats['has_sdg_publications'] = True

        # Open Access 여부
        if oa and str(oa).strip():
            stats['has_open_access'] = True

        # Topic Prominence
        if topic_prom:
            try:
                prom_val = float(topic_prom)
                stats['topic_prominence_sum'] += prom_val
                stats['topic_prominence_count'] += 1
            except (ValueError, TypeError):
                pass

    # 평균 계산
    if stats['international_collab_count'] > 0:
        stats['international_collab_fwci'] = stats['international_collab_fwci_sum'] / stats['international_collab_count']

    if stats['total_publications'] > 0:
        stats['top_journal_percentage'] = (stats['top_journal_count'] / stats['total_publications']) * 100

    if stats['topic_prominence_count'] > 0:
        stats['avg_topic_prominence'] = stats['topic_prominence_sum'] / stats['topic_prominence_count']

    return stats


def get_author_paper_drilldown(conn, scopus_author_id):
    """
    저자의 논문별 점수 기여도 드릴다운 데이터 조회
    각 지표별로 기여한 논문 목록 반환
    """
    cursor = conn.cursor()

    # 해당 저자가 참여한 논문들 조회 (상세 정보 포함)
    cursor.execute("""
        SELECT
            title,
            year,
            field_weighted_citation_impact,
            is_international,
            is_top_cited,
            snip_percentile_publication_year,
            citescore_percentile_publication_year,
            sjr_percentile_publication_year,
            sustainable_development_goals_2025,
            open_access,
            topic_prominence_percentile,
            topic_name,
            doi,
            eid,
            scopus_source_title,
            citations
        FROM publication
        WHERE scopus_author_ids LIKE ?
        ORDER BY year DESC, citations DESC
    """, (f'%{scopus_author_id}%',))

    publications = cursor.fetchall()

    # 각 지표별 논문 목록 분류
    drilldown = {
        'fwci': [],           # 모든 논문 (FWCI 점수 기여)
        'top_cited': [],      # is_top_cited=1 논문
        'top_journal': [],    # 상위 저널 논문
        'intl_collab': [],    # is_international=1 논문
        'sdg': [],            # SDG 관련 논문
        'open_access': [],    # OA 논문
        'prominence': []      # Prominence >= 90% 논문
    }

    # FWCI 점수 계산 함수 (inline)
    def calc_fwci_score(fwci):
        if fwci is None:
            return 0
        try:
            fwci = float(fwci)
        except:
            return 0
        if fwci >= 4.0:
            return 35
        elif fwci >= 3.0:
            return 30
        elif fwci >= 2.0:
            return 25
        elif fwci >= 1.5:
            return 20
        elif fwci >= 1.0:
            return 15
        elif fwci >= 0.5:
            return 10
        else:
            return 5

    for pub in publications:
        title = pub['title'] or 'Untitled'
        year = pub['year'] or ''
        fwci = pub['field_weighted_citation_impact']
        is_intl = pub['is_international']
        is_top_cited = pub['is_top_cited']
        snip_pct = pub['snip_percentile_publication_year']
        citescore_pct = pub['citescore_percentile_publication_year']
        sjr_pct = pub['sjr_percentile_publication_year']
        sdg = pub['sustainable_development_goals_2025']
        oa = pub['open_access']
        topic_prom = pub['topic_prominence_percentile']
        topic_name = pub['topic_name']
        doi = pub['doi']
        eid = pub['eid']
        journal = pub['scopus_source_title'] or ''
        citations = pub['citations'] or 0

        # Scopus 링크 생성
        scopus_link = None
        if eid:
            scopus_link = f"https://www.scopus.com/record/display.uri?eid={eid}&origin=resultslist"
        elif doi:
            scopus_link = f"https://doi.org/{doi}"

        # 기본 논문 정보
        paper_info = {
            'title': title[:80] + '...' if len(title) > 80 else title,
            'year': year,
            'journal': journal[:40] + '...' if len(journal) > 40 else journal,
            'citations': citations,
            'scopus_link': scopus_link
        }

        # 1. FWCI (모든 논문)
        try:
            fwci_val = float(fwci) if fwci else 0
            fwci_score = calc_fwci_score(fwci_val)
            drilldown['fwci'].append({
                **paper_info,
                'value': round(fwci_val, 2),
                'score': fwci_score,
                'max': 35
            })
        except:
            pass

        # 2. Top 10% 피인용
        if is_top_cited == 1:
            drilldown['top_cited'].append({
                **paper_info,
                'value': 'Top 10%',
                'score': 20,
                'max': 20
            })

        # 3. 상위 저널
        is_top_journal = False
        best_percentile = None
        for pct in [snip_pct, citescore_pct, sjr_pct]:
            if pct:
                try:
                    pct_val = int(pct)
                    if pct_val <= 10:
                        is_top_journal = True
                        if best_percentile is None or pct_val < best_percentile:
                            best_percentile = pct_val
                except:
                    pass
        if is_top_journal:
            drilldown['top_journal'].append({
                **paper_info,
                'value': f'Top {best_percentile}%',
                'score': 15,
                'max': 15
            })

        # 4. 국제협력
        if is_intl == 1:
            try:
                fwci_val = float(fwci) if fwci else 0
                drilldown['intl_collab'].append({
                    **paper_info,
                    'value': round(fwci_val, 2),
                    'score': 10 if fwci_val >= 1.5 else (5 if fwci_val >= 1.0 else 0),
                    'max': 10
                })
            except:
                pass

        # 5. SDG
        if sdg and str(sdg).strip():
            drilldown['sdg'].append({
                **paper_info,
                'value': str(sdg)[:30],
                'score': 3,
                'max': 3
            })

        # 6. Open Access
        if oa and str(oa).strip():
            drilldown['open_access'].append({
                **paper_info,
                'value': str(oa),
                'score': 2,
                'max': 2
            })

        # 7. Prominence
        if topic_prom:
            try:
                prom_val = float(topic_prom)
                if prom_val >= 90:
                    drilldown['prominence'].append({
                        **paper_info,
                        'value': f'{prom_val:.1f}%',
                        'topic': topic_name[:30] if topic_name else '',
                        'score': 5,
                        'max': 5
                    })
            except:
                pass

    # 각 지표별 요약 정보 추가
    summary = {
        'fwci': {
            'count': len(drilldown['fwci']),
            'avg_score': round(sum(p['score'] for p in drilldown['fwci']) / max(1, len(drilldown['fwci'])), 1)
        },
        'top_cited': {'count': len(drilldown['top_cited'])},
        'top_journal': {'count': len(drilldown['top_journal'])},
        'intl_collab': {'count': len(drilldown['intl_collab'])},
        'sdg': {'count': len(drilldown['sdg'])},
        'open_access': {'count': len(drilldown['open_access'])},
        'prominence': {'count': len(drilldown['prominence'])}
    }

    return {
        'papers': drilldown,
        'summary': summary
    }


def batch_calculate_researcher_scores():
    """
    모든 전북대 연구자의 점수를 일괄 계산하여 researcher_score 테이블에 저장
    개별 논문별 점수를 계산한 후 평균/중위값으로 집계
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 개별 논문 점수 계산 함수들
    def calc_fwci_score(fwci):
        """FWCI → 점수 변환 (35점 만점)"""
        if fwci is None:
            return 10  # 기본값
        if fwci >= 10:
            return 35
        elif fwci >= 8:
            return 30
        elif fwci >= 6:
            return 25
        elif fwci >= 4:
            return 20
        elif fwci >= 2:
            return 15
        else:
            return 10

    def calc_top_cited_score(is_top_10):
        """Top 10% 피인용 여부 → 점수 (20점 만점)"""
        return 20 if is_top_10 else 10

    def calc_top_journal_score(snip_pct, citescore_pct, sjr_pct):
        """상위 저널 여부 → 점수 (15점 만점)"""
        for pct in [snip_pct, citescore_pct, sjr_pct]:
            if pct:
                try:
                    if int(pct) <= 10:
                        return 15  # 상위 10% 저널
                except:
                    pass
        return 5  # 기타 저널

    def calc_intl_fwci_score(fwci):
        """국제협력 논문 FWCI → 점수 (10점 만점)"""
        if fwci is None:
            return 0
        if fwci >= 2.0:
            return 10
        elif fwci >= 1.5:
            return 7
        elif fwci >= 1.0:
            return 4
        else:
            return 1

    def calc_sdg_score(has_sdg):
        """SDG 관련 여부 → 점수 (3점 만점)"""
        return 3 if has_sdg else 0

    def calc_oa_score(has_oa):
        """Open Access 여부 → 점수 (2점 만점)"""
        return 2 if has_oa else 0

    def calc_prominence_score(prominence):
        """Topic Prominence → 점수 (5점 만점)"""
        if prominence is None:
            return 0
        return 5 if prominence >= 90 else 0

    # 1. 해당 기관 저자 목록 가져오기
    affiliation = get_institution_affiliation()
    cursor.execute("""
        SELECT author_id, scopus_author_id, name, scholarly_output, citations,
               field_weighted_citation_impact, h_index, output_in_top_10_percentile,
               primary_affiliation, scopus_author_profile
        FROM author
        WHERE primary_affiliation = ?
    """, (affiliation,))
    authors = cursor.fetchall()

    # 2. 논문 데이터를 한 번에 가져와서 메모리에 캐싱
    cursor.execute("""
        SELECT scopus_author_ids, field_weighted_citation_impact, is_international, is_10,
               snip_percentile_publication_year, citescore_percentile_publication_year,
               sjr_percentile_publication_year, sustainable_development_goals_2025,
               open_access, topic_prominence_percentile
        FROM publication
    """)
    all_publications = cursor.fetchall()

    # 저자별 개별 논문 점수 수집
    author_pub_scores = {}

    for pub in all_publications:
        scopus_ids_str = pub['scopus_author_ids'] or ''
        scopus_ids = [sid.strip() for sid in scopus_ids_str.replace('|', ' ').split() if sid.strip()]

        # 논문별 점수 계산
        fwci_val = None
        if pub['field_weighted_citation_impact']:
            try:
                fwci_val = float(pub['field_weighted_citation_impact'])
            except:
                pass

        prominence_val = None
        if pub['topic_prominence_percentile']:
            try:
                prominence_val = float(pub['topic_prominence_percentile'])
            except:
                pass

        pub_scores = {
            'fwci_val': fwci_val,
            'fwci_score': calc_fwci_score(fwci_val),
            'top_cited_score': calc_top_cited_score(pub['is_10'] == 1),
            'top_journal_score': calc_top_journal_score(
                pub['snip_percentile_publication_year'],
                pub['citescore_percentile_publication_year'],
                pub['sjr_percentile_publication_year']
            ),
            'is_international': pub['is_international'] == 1,
            'intl_fwci_score': calc_intl_fwci_score(fwci_val) if pub['is_international'] == 1 else None,
            'sdg_score': calc_sdg_score(bool(pub['sustainable_development_goals_2025'])),
            'oa_score': calc_oa_score(bool(pub['open_access'])),
            'prominence_score': calc_prominence_score(prominence_val)
        }

        for scopus_id in scopus_ids:
            if scopus_id not in author_pub_scores:
                author_pub_scores[scopus_id] = []
            author_pub_scores[scopus_id].append(pub_scores)

    # 3. 기존 데이터 삭제
    cursor.execute("DELETE FROM researcher_score")

    # 통계 계산 함수들
    def calc_median(values):
        if not values:
            return 0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
        return sorted_vals[mid]

    def calc_mean(values):
        if not values:
            return 0
        return sum(values) / len(values)

    # 4. 각 저자별 점수 계산 및 저장
    inserted = 0
    for author in authors:
        author_dict = dict(author)
        scopus_id = author_dict['scopus_author_id']

        # 저자의 논문별 점수 가져오기
        pub_scores_list = author_pub_scores.get(scopus_id, [])

        if not pub_scores_list:
            continue  # 논문이 없으면 건너뜀

        # 각 지표별 점수 리스트 추출
        fwci_values = [p['fwci_val'] for p in pub_scores_list if p['fwci_val'] is not None]
        fwci_scores = [p['fwci_score'] for p in pub_scores_list]
        top_cited_scores = [p['top_cited_score'] for p in pub_scores_list]
        top_journal_scores = [p['top_journal_score'] for p in pub_scores_list]
        intl_fwci_scores = [p['intl_fwci_score'] for p in pub_scores_list if p['intl_fwci_score'] is not None]
        sdg_scores = [p['sdg_score'] for p in pub_scores_list]
        oa_scores = [p['oa_score'] for p in pub_scores_list]
        prominence_scores = [p['prominence_score'] for p in pub_scores_list]

        # FWCI 값 (중위값/평균)
        fwci_mean_val = calc_mean(fwci_values) if fwci_values else 0
        fwci_median_val = calc_median(fwci_values) if fwci_values else 0

        # 각 지표별 평균 점수 계산 (개별 논문 점수의 평균)
        score_fwci_mean = calc_mean(fwci_scores)
        score_fwci_median = calc_median(fwci_scores)
        score_top_cited = calc_mean(top_cited_scores)
        score_top_journal = calc_mean(top_journal_scores)
        score_intl_collab = calc_mean(intl_fwci_scores) if intl_fwci_scores else 0
        score_sdg = calc_mean(sdg_scores)
        score_oa = calc_mean(oa_scores)
        score_prominence = calc_mean(prominence_scores)

        # 핵심지표 소계 (mean/median)
        score_core_mean = score_fwci_mean + score_top_cited + score_top_journal + score_intl_collab
        score_core_median = score_fwci_median + score_top_cited + score_top_journal + score_intl_collab

        # 보조지표 소계
        score_secondary = score_sdg + score_oa + score_prominence

        # 총점
        score_total_mean = score_core_mean + score_secondary
        score_total_median = score_core_median + score_secondary

        # 통계 정보
        intl_count = sum(1 for p in pub_scores_list if p['is_international'])
        intl_fwci_vals = [p['fwci_val'] for p in pub_scores_list if p['is_international'] and p['fwci_val'] is not None]
        intl_fwci_avg = calc_mean(intl_fwci_vals) if intl_fwci_vals else None

        top_journal_count = sum(1 for p in pub_scores_list if p['top_journal_score'] == 15)
        top_journal_pct = (top_journal_count / len(pub_scores_list)) * 100 if pub_scores_list else 0

        has_sdg = any(p['sdg_score'] > 0 for p in pub_scores_list)
        has_oa = any(p['oa_score'] > 0 for p in pub_scores_list)

        prom_values = [p['prominence_score'] for p in pub_scores_list if p['prominence_score'] is not None]
        avg_prominence = calc_mean(prom_values) if prom_values else 0

        # DB 저장 (개별 논문 점수 평균 기반)
        cursor.execute("""
            INSERT INTO researcher_score (
                author_id, scopus_author_id, name, scholarly_output, citations,
                fwci, fwci_mean, fwci_median,
                h_index, top_10_pct_count, intl_collab_count, intl_collab_fwci,
                top_journal_pct, has_sdg, has_oa, avg_topic_prominence,
                score_fwci, score_fwci_mean, score_fwci_median,
                score_top_cited, score_top_journal, score_intl_collab,
                score_core, score_core_mean, score_core_median,
                score_sdg, score_oa, score_prominence, score_secondary,
                score_total, score_total_mean, score_total_median,
                profile_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            author_dict['author_id'], scopus_id, author_dict['name'],
            author_dict['scholarly_output'], author_dict['citations'],
            fwci_median_val,  # 기본 fwci는 중위값
            fwci_mean_val,
            fwci_median_val,
            author_dict['h_index'],
            author_dict['output_in_top_10_percentile'],
            intl_count,
            intl_fwci_avg,
            top_journal_pct,
            1 if has_sdg else 0,
            1 if has_oa else 0,
            avg_prominence,
            score_fwci_median,  # 기본 score_fwci는 중위값 기준
            score_fwci_mean,
            score_fwci_median,
            score_top_cited,
            score_top_journal,
            score_intl_collab,
            score_core_median,  # 기본 score_core는 중위값 기준
            score_core_mean,
            score_core_median,
            score_sdg,
            score_oa,
            score_prominence,
            score_secondary,
            score_total_median,  # 기본 score_total은 중위값 기준
            score_total_mean,
            score_total_median,
            author_dict['scopus_author_profile']
        ))
        inserted += 1

    conn.commit()
    conn.close()

    return inserted


def calculate_researcher_scores_by_year(year_from, year_to):
    """
    특정 연도 범위의 논문만으로 연구자 점수를 실시간 계산 (DB 저장 안 함)
    batch_calculate_researcher_scores()와 동일한 점수 계산 로직 사용
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 점수 계산 함수들 (batch 함수와 동일)
    def calc_fwci_score(fwci):
        if fwci is None: return 10
        if fwci >= 10: return 35
        elif fwci >= 8: return 30
        elif fwci >= 6: return 25
        elif fwci >= 4: return 20
        elif fwci >= 2: return 15
        else: return 10

    def calc_top_cited_score(is_top_10):
        return 20 if is_top_10 else 10

    def calc_top_journal_score(snip_pct, citescore_pct, sjr_pct):
        for pct in [snip_pct, citescore_pct, sjr_pct]:
            if pct:
                try:
                    if int(pct) <= 10:
                        return 15
                except:
                    pass
        return 5

    def calc_intl_fwci_score(fwci):
        if fwci is None: return 0
        if fwci >= 2.0: return 10
        elif fwci >= 1.5: return 7
        elif fwci >= 1.0: return 4
        else: return 1

    def calc_sdg_score(has_sdg):
        return 3 if has_sdg else 0

    def calc_oa_score(has_oa):
        return 2 if has_oa else 0

    def calc_prominence_score(prominence):
        if prominence is None: return 0
        return 5 if prominence >= 90 else 0

    def calc_median(values):
        if not values: return 0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
        return sorted_vals[mid]

    def calc_mean(values):
        if not values: return 0
        return sum(values) / len(values)

    # 1. 해당 기관 저자 목록
    affiliation = get_institution_affiliation()
    cursor.execute("""
        SELECT author_id, scopus_author_id, name, scholarly_output, citations,
               field_weighted_citation_impact, h_index, output_in_top_10_percentile,
               scopus_author_profile
        FROM author
        WHERE primary_affiliation = ?
    """, (affiliation,))
    authors = cursor.fetchall()

    # 2. 연도 범위 필터된 논문 데이터 가져오기
    cursor.execute("""
        SELECT scopus_author_ids, field_weighted_citation_impact, is_international, is_10,
               snip_percentile_publication_year, citescore_percentile_publication_year,
               sjr_percentile_publication_year, sustainable_development_goals_2025,
               open_access, topic_prominence_percentile, year,
               field_citation_average, citations
        FROM publication
        WHERE CAST(year AS INTEGER) BETWEEN ? AND ?
    """, (year_from, year_to))
    filtered_pubs = cursor.fetchall()

    # 3. 저자별 논문 점수 집계
    author_pub_scores = {}
    for pub in filtered_pubs:
        scopus_ids_str = pub['scopus_author_ids'] or ''
        scopus_ids = [sid.strip() for sid in scopus_ids_str.replace('|', ' ').split() if sid.strip()]

        fwci_val = None
        if pub['field_weighted_citation_impact']:
            try: fwci_val = float(pub['field_weighted_citation_impact'])
            except: pass

        prominence_val = None
        if pub['topic_prominence_percentile']:
            try: prominence_val = float(pub['topic_prominence_percentile'])
            except: pass

        fca_val = None
        if pub['field_citation_average']:
            try: fca_val = float(pub['field_citation_average'])
            except: pass

        pub_citations = 0
        if pub['citations']:
            try: pub_citations = int(float(str(pub['citations'])))
            except: pass

        pub_scores = {
            'fwci_val': fwci_val,
            'fwci_score': calc_fwci_score(fwci_val),
            'top_cited_score': calc_top_cited_score(pub['is_10'] == 1),
            'top_journal_score': calc_top_journal_score(
                pub['snip_percentile_publication_year'],
                pub['citescore_percentile_publication_year'],
                pub['sjr_percentile_publication_year']
            ),
            'is_international': pub['is_international'] == 1,
            'intl_fwci_score': calc_intl_fwci_score(fwci_val) if pub['is_international'] == 1 else None,
            'sdg_score': calc_sdg_score(bool(pub['sustainable_development_goals_2025'])),
            'oa_score': calc_oa_score(bool(pub['open_access'])),
            'prominence_score': calc_prominence_score(prominence_val),
            'field_citation_average': fca_val,
            'pub_citations': pub_citations
        }

        for scopus_id in scopus_ids:
            if scopus_id not in author_pub_scores:
                author_pub_scores[scopus_id] = []
            author_pub_scores[scopus_id].append(pub_scores)

    conn.close()

    # 4. 각 저자별 점수 계산
    results = []
    for author in authors:
        author_dict = dict(author)
        scopus_id = author_dict['scopus_author_id']
        pub_scores_list = author_pub_scores.get(scopus_id, [])

        if not pub_scores_list:
            continue

        fwci_values = [p['fwci_val'] for p in pub_scores_list if p['fwci_val'] is not None]
        fwci_scores = [p['fwci_score'] for p in pub_scores_list]
        top_cited_scores = [p['top_cited_score'] for p in pub_scores_list]
        top_journal_scores = [p['top_journal_score'] for p in pub_scores_list]
        intl_fwci_scores = [p['intl_fwci_score'] for p in pub_scores_list if p['intl_fwci_score'] is not None]
        sdg_scores = [p['sdg_score'] for p in pub_scores_list]
        oa_scores = [p['oa_score'] for p in pub_scores_list]
        prominence_scores = [p['prominence_score'] for p in pub_scores_list]

        fwci_mean_val = calc_mean(fwci_values) if fwci_values else 0
        fwci_median_val = calc_median(fwci_values) if fwci_values else 0

        score_fwci_mean = calc_mean(fwci_scores)
        score_fwci_median = calc_median(fwci_scores)
        score_top_cited = calc_mean(top_cited_scores)
        score_top_journal = calc_mean(top_journal_scores)
        score_intl_collab = calc_mean(intl_fwci_scores) if intl_fwci_scores else 0
        score_sdg = calc_mean(sdg_scores)
        score_oa = calc_mean(oa_scores)
        score_prominence = calc_mean(prominence_scores)

        score_core_mean = score_fwci_mean + score_top_cited + score_top_journal + score_intl_collab
        score_core_median = score_fwci_median + score_top_cited + score_top_journal + score_intl_collab
        score_secondary = score_sdg + score_oa + score_prominence
        score_total_mean = score_core_mean + score_secondary
        score_total_median = score_core_median + score_secondary

        intl_count = sum(1 for p in pub_scores_list if p['is_international'])
        intl_fwci_vals = [p['fwci_val'] for p in pub_scores_list if p['is_international'] and p['fwci_val'] is not None]
        intl_fwci_avg = calc_mean(intl_fwci_vals) if intl_fwci_vals else None
        top_journal_count = sum(1 for p in pub_scores_list if p['top_journal_score'] == 15)
        top_journal_pct = (top_journal_count / len(pub_scores_list)) * 100 if pub_scores_list else 0

        # field_citation_average 기반 기대인용수 및 실제인용수
        expected_citations = sum(p['field_citation_average'] for p in pub_scores_list if p['field_citation_average'] is not None)
        actual_citations_in_period = sum(p['pub_citations'] for p in pub_scores_list)

        results.append({
            'author_id': author_dict['author_id'],
            'scopus_author_id': scopus_id,
            'name': author_dict['name'],
            'scholarly_output': len(pub_scores_list),  # 해당 기간 논문 수
            'scholarly_output_total': author_dict['scholarly_output'],  # 전체 논문 수
            'citations': author_dict['citations'],
            'expected_citations': round(expected_citations, 1),
            'actual_citations_in_period': actual_citations_in_period,
            'fwci': round(fwci_median_val, 2),
            'fwci_mean': round(fwci_mean_val, 2),
            'fwci_median': round(fwci_median_val, 2),
            'h_index': author_dict['h_index'],
            'top_10_pct_count': author_dict['output_in_top_10_percentile'],
            'primary_affiliation': affiliation,
            'profile_url': author_dict['scopus_author_profile'],
            'intl_collab_count': intl_count,
            'intl_collab_fwci': round(intl_fwci_avg, 2) if intl_fwci_avg else None,
            'top_journal_pct': round(top_journal_pct, 1),
            'has_sdg': any(p['sdg_score'] > 0 for p in pub_scores_list),
            'has_oa': any(p['oa_score'] > 0 for p in pub_scores_list),
            'avg_topic_prominence': 0,
            'score_fwci': score_fwci_median,
            'score_fwci_mean': score_fwci_mean,
            'score_fwci_median': score_fwci_median,
            'score_top_cited': score_top_cited,
            'score_top_journal': score_top_journal,
            'score_intl_collab': score_intl_collab,
            'score_core': score_core_median,
            'score_core_mean': score_core_mean,
            'score_core_median': score_core_median,
            'score_sdg': score_sdg,
            'score_oa': score_oa,
            'score_prominence': score_prominence,
            'score_secondary': score_secondary,
            'score_total': score_total_median,
            'score_total_mean': score_total_mean,
            'score_total_median': score_total_median
        })

    return results


@app.route('/api/recalculate_scores')
def api_recalculate_scores():
    """점수 재계산 API"""
    try:
        count = batch_calculate_researcher_scores()
        return jsonify({'success': True, 'message': f'{count}명의 연구자 점수가 계산되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/researcher_ranking')
@login_required
def researcher_ranking():
    """우수 연구자 랭킹 페이지"""
    log_activity('페이지 조회', '연구자 랭킹')
    return render_template('researcher_ranking.html')


@app.route('/api/researcher_scores')
def api_researcher_scores():
    """연구자 점수 API (사전 계산 테이블 또는 연도 범위 실시간 계산)"""
    try:
        # 검색 조건
        min_output = request.args.get('min_output', 10, type=int)
        limit = request.args.get('limit', 100, type=int)
        fwci_method = request.args.get('fwci_method', 'median')
        year_from = request.args.get('year_from', type=int)
        year_to = request.args.get('year_to', type=int)

        # 연도 범위 지정 시: 실시간 계산
        if year_from and year_to:
            all_results = calculate_researcher_scores_by_year(year_from, year_to)

            # FWCI 방식에 따라 정렬
            if fwci_method == 'mean':
                sort_key = 'score_total_mean'
            else:
                sort_key = 'score_total_median'

            # 최소 논문 수 필터 및 정렬
            filtered = [r for r in all_results if r['scholarly_output'] >= min_output]
            filtered.sort(key=lambda x: x[sort_key], reverse=True)

            total_count = len(filtered)
            if limit > 0:
                filtered = filtered[:limit]

            # FWCI 방식에 따라 표시값 선택
            results = []
            for r in filtered:
                if fwci_method == 'mean':
                    r['fwci'] = r['fwci_mean']
                    r['score_fwci'] = r['score_fwci_mean']
                    r['score_core'] = r['score_core_mean']
                    r['score_total'] = r['score_total_mean']
                else:
                    r['fwci'] = r['fwci_median']
                    r['score_fwci'] = r['score_fwci_median']
                    r['score_core'] = r['score_core_median']
                    r['score_total'] = r['score_total_median']
                results.append(r)

            return jsonify({
                'total_count': total_count,
                'returned_count': len(results),
                'fwci_method': fwci_method,
                'year_from': year_from,
                'year_to': year_to,
                'researchers': results
            })

        # 연도 미지정: 기존 사전 계산 테이블 조회 (빠름)
        conn = get_db_connection()
        cursor = conn.cursor()
        affiliation = get_institution_affiliation()

        if fwci_method == 'mean':
            order_col = 'score_total_mean'
            fwci_col = 'fwci_mean'
        else:
            order_col = 'score_total_median'
            fwci_col = 'fwci_median'

        cursor.execute(f"""
            SELECT * FROM researcher_score
            WHERE scholarly_output >= ?
            ORDER BY {order_col} DESC, {fwci_col} DESC
            LIMIT ?
        """, (min_output, limit))

        rows = cursor.fetchall()

        if not rows:
            conn.close()
            batch_calculate_researcher_scores()
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT * FROM researcher_score
                WHERE scholarly_output >= ?
                ORDER BY {order_col} DESC, {fwci_col} DESC
                LIMIT ?
            """, (min_output, limit))
            rows = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM researcher_score WHERE scholarly_output >= ?", (min_output,))
        total_count = cursor.fetchone()[0]

        results = []
        for row in rows:
            if fwci_method == 'mean':
                fwci_val = row['fwci_mean']
                score_fwci = row['score_fwci_mean']
                score_core = row['score_core_mean']
                score_total = row['score_total_mean']
            else:
                fwci_val = row['fwci_median']
                score_fwci = row['score_fwci_median']
                score_core = row['score_core_median']
                score_total = row['score_total_median']

            results.append({
                'author_id': row['author_id'],
                'scopus_author_id': row['scopus_author_id'],
                'name': row['name'],
                'scholarly_output': row['scholarly_output'],
                'citations': row['citations'],
                'fwci': round(fwci_val, 2) if fwci_val else 0,
                'fwci_mean': round(row['fwci_mean'], 2) if row['fwci_mean'] else 0,
                'fwci_median': round(row['fwci_median'], 2) if row['fwci_median'] else 0,
                'h_index': row['h_index'],
                'top_10_pct_count': row['top_10_pct_count'],
                'primary_affiliation': affiliation,
                'profile_url': row['profile_url'],
                'intl_collab_count': row['intl_collab_count'],
                'intl_collab_fwci': round(row['intl_collab_fwci'], 2) if row['intl_collab_fwci'] else None,
                'top_journal_pct': round(row['top_journal_pct'], 1) if row['top_journal_pct'] else 0,
                'has_sdg': row['has_sdg'] == 1,
                'has_oa': row['has_oa'] == 1,
                'avg_topic_prominence': round(row['avg_topic_prominence'], 1) if row['avg_topic_prominence'] else 0,
                'score_fwci': score_fwci,
                'score_top_cited': row['score_top_cited'],
                'score_top_journal': row['score_top_journal'],
                'score_intl_collab': row['score_intl_collab'],
                'score_core': score_core,
                'score_sdg': row['score_sdg'],
                'score_oa': row['score_oa'],
                'score_prominence': row['score_prominence'],
                'score_secondary': row['score_secondary'],
                'score_total': score_total
            })

        conn.close()

        return jsonify({
            'total_count': total_count,
            'returned_count': len(results),
            'fwci_method': fwci_method,
            'researchers': results
        })
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/bibliometric_ranking')
def api_bibliometric_ranking():
    """계량서지학 지표 기반 연구자 랭킹 API (인용수, FWCI, h-index, g-index, i10-index)"""
    try:
        min_output = request.args.get('min_output', 10, type=int)
        limit = request.args.get('limit', 100, type=int)
        sort_by = request.args.get('sort_by', 'h_index')
        year_from = request.args.get('year_from', type=int)
        year_to = request.args.get('year_to', type=int)

        conn = get_db_connection()
        cursor = conn.cursor()
        affiliation = get_institution_affiliation()

        # 저자 목록 조회
        cursor.execute("""
            SELECT author_id, scopus_author_id, name, scholarly_output,
                   citations, field_weighted_citation_impact, h_index,
                   scopus_author_profile, primary_affiliation,
                   oldest_publication, most_recent_publication
            FROM author
            WHERE primary_affiliation LIKE ?
        """, (f'%{affiliation}%',))
        authors = [dict(row) for row in cursor.fetchall()]

        # 논문 데이터 조회 (인용수 필요)
        year_filter = ""
        params = []
        if year_from and year_to:
            year_filter = "WHERE year >= ? AND year <= ?"
            params = [year_from, year_to]

        cursor.execute(f"""
            SELECT scopus_author_ids, citations
            FROM publication
            {year_filter}
        """, params)
        publications = cursor.fetchall()

        # 저자별 논문 인용수 리스트 구축
        author_citations = {}  # scopus_author_id -> [citation_count, ...]
        for pub in publications:
            author_ids_str = pub['scopus_author_ids'] or ''
            try:
                    cite_count = int(float(pub['citations'] or 0))
            except (ValueError, TypeError):
                    cite_count = 0
            for aid in author_ids_str.replace(';', '|').split('|'):
                aid = aid.strip()
                if aid:
                    if aid not in author_citations:
                        author_citations[aid] = []
                    author_citations[aid].append(cite_count)

        conn.close()

        results = []
        for author in authors:
            sid = author['scopus_author_id']
            cites_list = author_citations.get(sid, [])
            paper_count = len(cites_list) if (year_from and year_to) else (author['scholarly_output'] or 0)

            if paper_count < min_output:
                continue

            # 인용수 내림차순 정렬
            cites_list.sort(reverse=True)

            # g-index 계산: 상위 g편의 인용 합계 >= g^2
            g_index = 0
            cumulative = 0
            for i, c in enumerate(cites_list):
                cumulative += c
                if cumulative >= (i + 1) ** 2:
                    g_index = i + 1

            # i10-index 계산: 인용 10회 이상 논문 수
            i10_index = sum(1 for c in cites_list if c >= 10)

            # h-index: 논문 데이터에서 항상 재계산 (상세와 일치)
            h_index = 0
            for i, c in enumerate(cites_list):
                if c >= (i + 1):
                    h_index = i + 1
                else:
                    break

            if year_from and year_to:
                total_citations = sum(cites_list)
                fwci = None  # 기간 필터 시 개별 FWCI 재계산 불가
            else:
                total_citations = author['citations'] or 0
                fwci = author['field_weighted_citation_impact']

            # m-index 계산: h-index / 학술 활동 연수
            oldest = author.get('oldest_publication')
            most_recent = author.get('most_recent_publication')
            if oldest and most_recent and most_recent >= oldest:
                career_years = most_recent - oldest + 1
                m_index = round(h_index / career_years, 2) if career_years > 0 else None
            else:
                career_years = None
                m_index = None

            # hg-index 계산: √(h × g)
            import math
            hg_index = round(math.sqrt(h_index * g_index), 2) if h_index > 0 and g_index > 0 else 0

            results.append({
                'scopus_author_id': sid,
                'name': author['name'],
                'scholarly_output': paper_count,
                'citations': total_citations,
                'fwci': round(fwci, 2) if fwci else None,
                'h_index': h_index,
                'g_index': g_index,
                'hg_index': hg_index,
                'i10_index': i10_index,
                'm_index': m_index,
                'career_years': career_years,
                'primary_affiliation': affiliation,
                'profile_url': author['scopus_author_profile']
            })

        # 정렬
        valid_sort_keys = ['citations', 'fwci', 'h_index', 'g_index', 'hg_index', 'i10_index', 'm_index', 'scholarly_output', 'name']
        if sort_by not in valid_sort_keys:
            sort_by = 'h_index'
        results.sort(key=lambda x: (x[sort_by] if x[sort_by] is not None else -1), reverse=(sort_by != 'name'))

        total_count = len(results)
        if limit > 0:
            results = results[:limit]

        return jsonify({
            'total_count': total_count,
            'returned_count': len(results),
            'sort_by': sort_by,
            'year_from': year_from,
            'year_to': year_to,
            'researchers': results
        })
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/bibliometric_detail/<scopus_id>')
def api_bibliometric_detail(scopus_id):
    """계량서지학 지표 상세 API - h/g/i10-index 산출 근거 제공"""
    try:
        year_from = request.args.get('year_from', type=int)
        year_to = request.args.get('year_to', type=int)

        conn = get_db_connection()
        cursor = conn.cursor()

        # 저자 기본 정보
        cursor.execute("""
            SELECT author_id, scopus_author_id, name, scholarly_output,
                   citations, field_weighted_citation_impact, h_index,
                   scopus_author_profile, primary_affiliation, orcid,
                   oldest_publication, most_recent_publication
            FROM author WHERE scopus_author_id = ?
        """, (scopus_id,))
        author = cursor.fetchone()
        if not author:
            conn.close()
            return jsonify({'error': 'Author not found'}), 404
        author_dict = dict(author)

        # 해당 저자의 논문 목록 (인용수 포함)
        year_filter = ""
        params = []
        if year_from and year_to:
            year_filter = "AND year >= ? AND year <= ?"
            params = [year_from, year_to]

        cursor.execute(f"""
            SELECT title, year, citations, field_weighted_citation_impact,
                   scopus_source_title, eid
            FROM publication
            WHERE scopus_author_ids LIKE ?
            {year_filter}
            ORDER BY CAST(citations AS INTEGER) DESC
        """, (f'%{scopus_id}%', *params))
        papers_raw = cursor.fetchall()
        conn.close()

        # 논문 데이터 정리
        papers = []
        for p in papers_raw:
            try:
                cites = int(float(p['citations'] or 0))
            except (ValueError, TypeError):
                cites = 0
            eid = p['eid'] or ''
            scopus_link = f"https://www.scopus.com/record/display.uri?eid={eid}" if eid else None
            papers.append({
                'title': p['title'] or '',
                'year': p['year'],
                'citations': cites,
                'fwci': round(float(p['field_weighted_citation_impact'] or 0), 2),
                'source': p['scopus_source_title'] or '',
                'scopus_link': scopus_link
            })

        # 인용수 내림차순 정렬 (이미 SQL에서 정렬했지만 확실히)
        papers.sort(key=lambda x: x['citations'], reverse=True)

        total_papers = len(papers)
        total_citations = sum(p['citations'] for p in papers)

        # h-index 계산 및 경계 표시
        h_index = 0
        for i, p in enumerate(papers):
            if p['citations'] >= (i + 1):
                h_index = i + 1
            else:
                break

        # g-index 계산 및 경계 표시
        g_index = 0
        cumulative = 0
        g_cumulative_list = []
        for i, p in enumerate(papers):
            cumulative += p['citations']
            g_squared = (i + 1) ** 2
            g_cumulative_list.append({
                'rank': i + 1,
                'citations': p['citations'],
                'cumulative': cumulative,
                'g_squared': g_squared,
                'satisfies': cumulative >= g_squared
            })
            if cumulative >= g_squared:
                g_index = i + 1

        # i10-index 계산
        i10_index = sum(1 for p in papers if p['citations'] >= 10)

        # 상세 논문 리스트 (상위 제한)
        h_papers = papers[:max(h_index + 3, 10)]  # h-index 경계 전후
        for i, p in enumerate(h_papers):
            p['rank'] = i + 1
            p['is_h_core'] = (i < h_index)

        g_detail = g_cumulative_list[:max(g_index + 3, 10)]

        i10_papers = [p for p in papers if p['citations'] >= 10][:20]

        # m-index 계산: h-index / 학술 활동 연수
        oldest_pub = author_dict.get('oldest_publication')
        most_recent_pub = author_dict.get('most_recent_publication')
        if oldest_pub and most_recent_pub and most_recent_pub >= oldest_pub:
            career_years = most_recent_pub - oldest_pub + 1
            m_index = round(h_index / career_years, 2) if career_years > 0 else None
        else:
            career_years = None
            m_index = None

        # hg-index 계산: √(h × g)
        import math
        hg_index = round(math.sqrt(h_index * g_index), 2) if h_index > 0 and g_index > 0 else 0

        return jsonify({
            'author': {
                'scopus_author_id': author_dict['scopus_author_id'],
                'name': author_dict['name'],
                'scholarly_output': total_papers if (year_from and year_to) else (author_dict['scholarly_output'] or 0),
                'citations': total_citations if (year_from and year_to) else (author_dict['citations'] or 0),
                'fwci': round(author_dict['field_weighted_citation_impact'] or 0, 2),
                'h_index_original': author_dict['h_index'] or 0,
                'primary_affiliation': author_dict['primary_affiliation'] or '',
                'scopus_author_profile': author_dict['scopus_author_profile'] or '',
                'orcid': author_dict['orcid'] or ''
            },
            'indices': {
                'h_index': h_index,
                'g_index': g_index,
                'hg_index': hg_index,
                'i10_index': i10_index,
                'm_index': m_index,
                'career_years': career_years,
                'oldest_publication': oldest_pub,
                'most_recent_publication': most_recent_pub,
                'total_papers': total_papers,
                'total_citations': total_citations
            },
            'h_detail': {
                'description': f'상위 {h_index}편의 논문이 각각 {h_index}회 이상 인용됨',
                'papers': h_papers
            },
            'g_detail': {
                'description': f'상위 {g_index}편 논문의 인용 합계({g_cumulative_list[g_index-1]["cumulative"] if g_index > 0 else 0})가 {g_index}² = {g_index**2} 이상',
                'papers': g_detail
            },
            'i10_detail': {
                'description': f'10회 이상 인용된 논문 {i10_index}편',
                'papers': i10_papers
            },
            'm_detail': {
                'description': f'h-index({h_index}) ÷ 학술활동 연수({career_years}년, {oldest_pub}~{most_recent_pub}) = {m_index}' if m_index else '학술활동 기간 정보 없음'
            },
            'hg_detail': {
                'description': f'√(h-index({h_index}) × g-index({g_index})) = √{h_index * g_index} = {hg_index}'
            },
            'year_from': year_from,
            'year_to': year_to
        })
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/researcher_score/<scopus_id>')
def api_researcher_score_detail(scopus_id):
    """개별 연구자 점수 상세 API - researcher_score 테이블 사용"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # FWCI 방식 파라미터 (기본: median)
    fwci_method = request.args.get('fwci_method', 'median')

    # 연도 범위 파라미터 (리스트 필터와 일치)
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)

    # author 테이블에서 기본 정보 조회
    cursor.execute("""
        SELECT
            author_id,
            scopus_author_id,
            name,
            scholarly_output,
            citations,
            citations_per_publication,
            field_weighted_citation_impact,
            h_index,
            output_in_top_10_percentile,
            most_recent_publication,
            oldest_publication,
            primary_affiliation,
            scopus_author_profile,
            orcid
        FROM author
        WHERE scopus_author_id = ?
    """, (scopus_id,))

    author = cursor.fetchone()

    if not author:
        conn.close()
        return jsonify({'error': 'Author not found'}), 404

    author_dict = dict(author)

    # 연도 필터가 있으면 해당 기간의 논문 수 계산
    period_scholarly_output = None
    if year_from and year_to:
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM publication
            WHERE scopus_author_ids LIKE '%' || ? || '%'
            AND CAST(year AS INTEGER) BETWEEN ? AND ?
        """, (scopus_id, year_from, year_to))
        period_result = cursor.fetchone()
        period_scholarly_output = period_result['count'] if period_result else 0
    else:
        # 연도 필터 없이도 publication 테이블 기반 논문수 계산 (리스트와 일관성 유지)
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM publication
            WHERE scopus_author_ids LIKE '%' || ? || '%'
        """, (scopus_id,))
        period_result = cursor.fetchone()
        period_scholarly_output = period_result['count'] if period_result else 0

    # researcher_score 테이블에서 사전 계산된 점수 조회
    cursor.execute("""
        SELECT * FROM researcher_score
        WHERE scopus_author_id = ?
    """, (scopus_id,))

    score_row = cursor.fetchone()

    # 논문별 드릴다운 데이터 조회
    paper_drilldown = get_author_paper_drilldown(conn, scopus_id)

    if score_row:
        # researcher_score 테이블에서 점수 사용
        row = dict(score_row)
        conn.close()

        # FWCI 방식에 따른 값 선택
        if fwci_method == 'mean':
            fwci_val = row.get('fwci_mean', 0) or 0
            score_fwci = row.get('score_fwci_mean', 0) or 0
            score_core = row.get('score_core_mean', 0) or 0
            score_total = row.get('score_total_mean', 0) or 0
        else:
            fwci_val = row.get('fwci_median', 0) or 0
            score_fwci = row.get('score_fwci_median', 0) or 0
            score_core = row.get('score_core_median', 0) or 0
            score_total = row.get('score_total_median', 0) or 0

        # 드릴다운에서 센 개수를 사용 (표시값과 논문 목록 일치)
        drilldown_summary = paper_drilldown.get('summary', {})

        # 기간 논문수: 연도 필터가 있으면 해당 기간, 아니면 전체
        display_scholarly_output = period_scholarly_output if period_scholarly_output is not None else row.get('scholarly_output', 0)

        return jsonify({
            'author': author_dict,
            'year_from': year_from,
            'year_to': year_to,
            'publication_stats': {
                'total_publications': display_scholarly_output,
                'total_publications_all': author_dict['scholarly_output'],  # 전체 기간 논문수 (참고용)
                'international_collab_count': drilldown_summary.get('intl_collab', {}).get('count', 0),
                'international_collab_fwci': row.get('intl_collab_fwci'),
                'top_journal_count': drilldown_summary.get('top_journal', {}).get('count', 0),
                'top_journal_percentage': row.get('top_journal_pct', 0),
                'has_sdg_publications': row.get('has_sdg', 0) == 1,
                'has_open_access': row.get('has_oa', 0) == 1,
                'avg_topic_prominence': row.get('avg_topic_prominence', 0)
            },
            'scores': {
                'fwci': score_fwci,
                'top_cited': row.get('score_top_cited', 0),
                'top_journal': row.get('score_top_journal', 0),
                'intl_collab': row.get('score_intl_collab', 0),
                'core_total': score_core,
                'sdg': row.get('score_sdg', 0),
                'open_access': row.get('score_oa', 0),
                'topic_prominence': row.get('score_prominence', 0),
                'secondary_total': row.get('score_secondary', 0),
                'total': score_total
            },
            'score_breakdown': {
                'core_indicators': {
                    'fwci': {'score': score_fwci, 'max': 35, 'value': round(fwci_val, 2)},
                    'top_cited': {'score': row.get('score_top_cited', 0), 'max': 20, 'value': drilldown_summary.get('top_cited', {}).get('count', 0)},
                    'top_journal': {'score': row.get('score_top_journal', 0), 'max': 15, 'value': f"{row.get('top_journal_pct', 0):.1f}%"},
                    'intl_collab': {'score': row.get('score_intl_collab', 0), 'max': 10, 'value': row.get('intl_collab_fwci')}
                },
                'secondary_indicators': {
                    'sdg': {'score': row.get('score_sdg', 0), 'max': 3, 'value': row.get('has_sdg', 0) == 1},
                    'open_access': {'score': row.get('score_oa', 0), 'max': 2, 'value': row.get('has_oa', 0) == 1},
                    'topic_prominence': {'score': row.get('score_prominence', 0), 'max': 5, 'value': row.get('avg_topic_prominence', 0)}
                },
                'totals': {
                    'core': {'score': score_core, 'max': 80},
                    'secondary': {'score': row.get('score_secondary', 0), 'max': 10},
                    'total': {'score': score_total, 'max': 90}
                }
            },
            'paper_drilldown': paper_drilldown
        })
    else:
        # researcher_score 테이블에 없는 경우 기존 방식으로 계산 (fallback)
        pub_stats = get_author_publication_stats(conn, scopus_id)
        scores = calculate_researcher_score(author_dict, pub_stats)
        conn.close()

        # 기간 논문수: 연도 필터가 있으면 해당 기간, 아니면 전체
        if period_scholarly_output is not None:
            pub_stats['total_publications'] = period_scholarly_output
            pub_stats['total_publications_all'] = author_dict['scholarly_output']

        return jsonify({
            'author': author_dict,
            'year_from': year_from,
            'year_to': year_to,
            'publication_stats': pub_stats,
            'scores': scores,
            'score_breakdown': {
                'core_indicators': {
                    'fwci': {'score': scores['fwci'], 'max': 35, 'value': author_dict['field_weighted_citation_impact']},
                    'top_cited': {'score': scores['top_cited'], 'max': 20, 'value': author_dict['output_in_top_10_percentile']},
                    'top_journal': {'score': scores['top_journal'], 'max': 15, 'value': f"{pub_stats['top_journal_percentage']:.1f}%"},
                    'intl_collab': {'score': scores['intl_collab'], 'max': 10, 'value': pub_stats['international_collab_fwci']}
                },
                'secondary_indicators': {
                    'sdg': {'score': scores['sdg'], 'max': 3, 'value': pub_stats['has_sdg_publications']},
                    'open_access': {'score': scores['open_access'], 'max': 2, 'value': pub_stats['has_open_access']},
                    'topic_prominence': {'score': scores['topic_prominence'], 'max': 5, 'value': pub_stats['avg_topic_prominence']}
                },
                'totals': {
                    'core': {'score': scores['core_total'], 'max': 80},
                    'secondary': {'score': scores['secondary_total'], 'max': 10},
                    'total': {'score': scores['total'], 'max': 90}
                }
            },
            'paper_drilldown': paper_drilldown
        })


@app.route('/api/download_researcher_ranking')
@login_required
def download_researcher_ranking():
    """연구자 랭킹 CSV 다운로드 (사전 계산 테이블 사용)"""
    log_activity('다운로드', '연구자 랭킹 CSV')
    import io

    conn = get_db_connection()
    cursor = conn.cursor()

    min_output = request.args.get('min_output', 10, type=int)
    fwci_method = request.args.get('fwci_method', 'median')

    # FWCI 방식에 따른 정렬 및 컬럼 선택
    if fwci_method == 'mean':
        order_col = 'score_total_mean'
        fwci_col = 'fwci_mean'
        score_fwci_col = 'score_fwci_mean'
        score_core_col = 'score_core_mean'
        score_total_col = 'score_total_mean'
        method_label = '산술평균'
    else:
        order_col = 'score_total_median'
        fwci_col = 'fwci_median'
        score_fwci_col = 'score_fwci_median'
        score_core_col = 'score_core_median'
        score_total_col = 'score_total_median'
        method_label = '중위값'

    # 사전 계산된 테이블에서 조회
    cursor.execute(f"""
        SELECT * FROM researcher_score
        WHERE scholarly_output >= ?
        ORDER BY {order_col} DESC, {fwci_col} DESC
    """, (min_output,))

    rows = cursor.fetchall()
    conn.close()

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    headers = ['순위', '연구자명', 'Scopus ID', '총논문수', '총인용수', f'FWCI({method_label})', 'h-index',
               'Top10%논문수', '국제협력FWCI', '상위저널비율(%)', 'SDG해당', 'OA해당',
               '평균Topic Prominence', 'FWCI점수', 'Top10%점수', '상위저널점수',
               '국제협력점수', '핵심지표소계', 'SDG점수', 'OA점수', 'Prominence점수',
               '보조지표소계', '총점', 'Scopus Profile']
    writer.writerow(headers)

    for i, r in enumerate(rows):
        writer.writerow([
            i + 1,
            r['name'],
            r['scopus_author_id'],
            r['scholarly_output'],
            r['citations'],
            round(r[fwci_col], 2) if r[fwci_col] else 0,
            r['h_index'],
            r['top_10_pct_count'],
            round(r['intl_collab_fwci'], 2) if r['intl_collab_fwci'] else '',
            round(r['top_journal_pct'], 1) if r['top_journal_pct'] else 0,
            'Y' if r['has_sdg'] else 'N',
            'Y' if r['has_oa'] else 'N',
            round(r['avg_topic_prominence'], 1) if r['avg_topic_prominence'] else 0,
            r[score_fwci_col],
            r['score_top_cited'],
            r['score_top_journal'],
            r['score_intl_collab'],
            r[score_core_col],
            r['score_sdg'],
            r['score_oa'],
            r['score_prominence'],
            r['score_secondary'],
            r[score_total_col],
            r['profile_url']
        ])

    csv_content = output.getvalue()
    output.close()

    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = f'attachment; filename=researcher_ranking_{datetime.now().strftime("%Y%m%d")}.csv'

    return response


# ========================================
# 잠재 연구자 발굴 모듈 API
# ========================================

@app.route('/analysis_modules')
@login_required
def analysis_modules():
    """연구자 분석 모듈 메인 페이지"""
    log_activity('페이지 조회', '분석 모듈')
    return render_template('analysis_modules.html')


@app.route('/api/potential_researchers')
def api_potential_researchers():
    """
    잠재 연구자 발굴 API
    1. 최근 3년 성장률 높은 연구자
    2. FWCI 높지만 논문 수 적은 연구자
    3. Topic Prominence 90+ 분야 연구자
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    affiliation = get_institution_affiliation()

    analysis_type = request.args.get('type', 'growth')  # growth, high_fwci_low_output, high_prominence
    limit = request.args.get('limit', 50, type=int)
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)

    # 연도 필터 SQL 조건
    year_condition = ""
    year_params = []
    if year_from and year_to:
        year_condition = " AND CAST(year AS INTEGER) BETWEEN ? AND ?"
        year_params = [year_from, year_to]

    results = []

    if analysis_type == 'growth':
        # 1. 최근 성장률 높은 연구자
        # 성장률 = 경력 대비 최근 논문 비율. 항상 전체 논문 이력 기반으로 계산.
        # 연도 필터는 "최근" 기간만 조정하고, 과거 이력은 항상 포함.
        from datetime import datetime
        current_year = datetime.now().year

        # 항상 전체 논문을 가져옴 (성장률은 전체 경력 대비 지표)
        cursor.execute("""
            SELECT scopus_author_ids, year
            FROM publication
            WHERE scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
        """)
        all_pubs = cursor.fetchall()

        # 최근 기준 연도: 연도 필터 지정 시 year_from, 아니면 현재연도 - 2
        recent_cutoff = year_from if (year_from and year_to) else (current_year - 2)
        recent_end = year_to if (year_from and year_to) else current_year
        recent_span = recent_end - recent_cutoff + 1

        # 저자별 최근/이전 논문 수 집계
        author_pub_counts = {}
        for pub in all_pubs:
            scopus_ids_str = pub['scopus_author_ids'] or ''
            scopus_ids = [sid.strip() for sid in scopus_ids_str.replace('|', ' ').split() if sid.strip()]
            try:
                year = int(float(pub['year'])) if pub['year'] else 0
            except:
                year = 0

            for sid in scopus_ids:
                if sid not in author_pub_counts:
                    author_pub_counts[sid] = {'recent': 0, 'old': 0, 'total': 0}
                if recent_cutoff <= year <= recent_end:
                    author_pub_counts[sid]['recent'] += 1
                elif year > 0:
                    author_pub_counts[sid]['old'] += 1
                if year > 0:
                    author_pub_counts[sid]['total'] += 1

        # 해당 기관 저자 정보 조회
        cursor.execute(f"""
            SELECT a.scopus_author_id, a.name, a.scholarly_output, a.citations,
                   a.field_weighted_citation_impact as fwci, a.h_index,
                   a.most_recent_publication, a.oldest_publication,
                   a.scopus_author_profile as profile_url,
                   rs.score_total_median as score_total
            FROM author a
            LEFT JOIN researcher_score rs ON a.scopus_author_id = rs.scopus_author_id
            WHERE a.primary_affiliation = ?
            AND a.scholarly_output >= 5
            AND a.most_recent_publication >= {recent_cutoff}
        """, (affiliation,))
        authors = cursor.fetchall()

        for author in authors:
            author_dict = dict(author)
            scopus_id = author_dict['scopus_author_id']

            counts = author_pub_counts.get(scopus_id, {'recent': 0, 'old': 0, 'total': 0})
            recent_count = counts['recent']
            old_count = counts['old']
            total_count = counts['total']

            # 성장률 계산: 전체 경력 대비 최근 논문 비율
            career_years = (author_dict['most_recent_publication'] or current_year) - (author_dict['oldest_publication'] or current_year - 4) + 1

            if total_count > 0 and old_count > 0 and career_years > recent_span:
                expected_ratio = recent_span / career_years
                actual_ratio = recent_count / total_count
                growth_rate = (actual_ratio / expected_ratio - 1) * 100 if expected_ratio > 0 else 0
            else:
                growth_rate = 0

            if recent_count >= 3:  # 최근 기간 논문이 3편 이상인 경우만
                period_output = total_count if (year_from and year_to) else author_dict['scholarly_output']
                results.append({
                    'scopus_author_id': scopus_id,
                    'name': author_dict['name'],
                    'scholarly_output': period_output,
                    'citations': author_dict['citations'],
                    'fwci': round(author_dict['fwci'], 2) if author_dict['fwci'] else 0,
                    'h_index': author_dict['h_index'],
                    'recent_3yr_count': recent_count,
                    'growth_rate': round(growth_rate, 1),
                    'career_years': career_years,
                    'profile_url': author_dict['profile_url'],
                    'score_total': author_dict['score_total'] or 0
                })

        results.sort(key=lambda x: x['growth_rate'], reverse=True)
        results = results[:limit]

    elif analysis_type == 'high_fwci_low_output':
        # 2. FWCI 높지만 논문 수 적은 연구자 (잠재력 높음)
        import math

        if year_from and year_to:
            # 연도 필터: 해당 기간 논문에서 직접 집계
            cursor.execute("""
                SELECT scopus_author_ids, field_weighted_citation_impact
                FROM publication
                WHERE CAST(year AS INTEGER) BETWEEN ? AND ?
                AND scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
            """, (year_from, year_to))
            period_pubs = cursor.fetchall()

            # 저자별 논문수, FWCI 집계
            author_stats = {}
            for pub in period_pubs:
                scopus_ids_str = pub['scopus_author_ids'] or ''
                scopus_ids = [sid.strip() for sid in scopus_ids_str.replace('|', ' ').split() if sid.strip()]
                fwci_val = None
                try:
                    fwci_val = float(pub['field_weighted_citation_impact']) if pub['field_weighted_citation_impact'] else None
                except:
                    pass
                for sid in scopus_ids:
                    if sid not in author_stats:
                        author_stats[sid] = {'count': 0, 'fwci_values': []}
                    author_stats[sid]['count'] += 1
                    if fwci_val is not None:
                        author_stats[sid]['fwci_values'].append(fwci_val)

            # 해당 기관 저자 정보
            cursor.execute("""
                SELECT a.scopus_author_id, a.name, a.citations, a.h_index,
                       a.scopus_author_profile as profile_url,
                       rs.score_total_median as score_total
                FROM author a
                LEFT JOIN researcher_score rs ON a.scopus_author_id = rs.scopus_author_id
                WHERE a.primary_affiliation = ?
            """, (affiliation,))
            for author in cursor.fetchall():
                ad = dict(author)
                sid = ad['scopus_author_id']
                stats = author_stats.get(sid)
                if not stats or stats['count'] < 5 or stats['count'] > 30:
                    continue
                fwci_vals = stats['fwci_values']
                if not fwci_vals:
                    continue
                avg_fwci = sum(fwci_vals) / len(fwci_vals)
                if avg_fwci < 1.5:
                    continue
                # Median FWCI
                sorted_fwci = sorted(fwci_vals)
                n = len(sorted_fwci)
                mid = n // 2
                median_fwci = (sorted_fwci[mid - 1] + sorted_fwci[mid]) / 2 if n % 2 == 0 else sorted_fwci[mid]
                efficiency = avg_fwci / max(1, math.log(stats['count'] + 1))
                results.append({
                    'scopus_author_id': sid,
                    'name': ad['name'],
                    'scholarly_output': stats['count'],
                    'citations': ad['citations'],
                    'fwci': round(avg_fwci, 2),
                    'fwci_median': round(median_fwci, 2),
                    'h_index': ad['h_index'],
                    'efficiency_score': round(efficiency, 2),
                    'profile_url': ad['profile_url'],
                    'score_total': ad['score_total'] or 0,
                    'potential_note': '논문 수 대비 높은 FWCI - 연구 지원 시 높은 성장 잠재력'
                })
        else:
            cursor.execute("""
                SELECT a.scopus_author_id, a.name, a.scholarly_output, a.citations,
                       a.field_weighted_citation_impact as fwci, a.h_index,
                       a.scopus_author_profile as profile_url,
                       rs.fwci_median, rs.score_total_median as score_total
                FROM author a
                LEFT JOIN researcher_score rs ON a.scopus_author_id = rs.scopus_author_id
                WHERE a.primary_affiliation = ?
                AND a.scholarly_output BETWEEN 5 AND 30
                AND a.field_weighted_citation_impact >= 1.5
                ORDER BY a.field_weighted_citation_impact DESC
                LIMIT ?
            """, (affiliation, limit))
            rows = cursor.fetchall()

            for row in rows:
                row_dict = dict(row)
                efficiency = row_dict['fwci'] / max(1, math.log(row_dict['scholarly_output'] + 1))
                results.append({
                    'scopus_author_id': row_dict['scopus_author_id'],
                    'name': row_dict['name'],
                    'scholarly_output': row_dict['scholarly_output'],
                    'citations': row_dict['citations'],
                    'fwci': round(row_dict['fwci'], 2) if row_dict['fwci'] else 0,
                    'fwci_median': round(row_dict['fwci_median'], 2) if row_dict['fwci_median'] else 0,
                    'h_index': row_dict['h_index'],
                    'efficiency_score': round(efficiency, 2),
                    'profile_url': row_dict['profile_url'],
                    'score_total': row_dict['score_total'] or 0,
                    'potential_note': '논문 수 대비 높은 FWCI - 연구 지원 시 높은 성장 잠재력'
                })

        results.sort(key=lambda x: x['efficiency_score'], reverse=True)

    elif analysis_type == 'high_prominence':
        # 3. Topic Prominence 90+ 분야 연구자
        # 먼저 prominence 90+ 논문을 가진 저자들 찾기
        prom_query = """
            SELECT DISTINCT p.scopus_author_ids,
                   p.topic_name, p.topic_prominence_percentile
            FROM publication p
            WHERE CAST(p.topic_prominence_percentile AS REAL) >= 90
        """
        if year_from and year_to:
            prom_query += " AND CAST(p.year AS INTEGER) BETWEEN ? AND ?"
            cursor.execute(prom_query, (year_from, year_to))
        else:
            cursor.execute(prom_query)
        prominence_pubs = cursor.fetchall()

        # 저자별 고prominence 논문 수 집계
        author_prominence = {}
        for pub in prominence_pubs:
            scopus_ids_str = pub['scopus_author_ids'] or ''
            scopus_ids = [sid.strip() for sid in scopus_ids_str.replace('|', ' ').split() if sid.strip()]
            for sid in scopus_ids:
                if sid not in author_prominence:
                    author_prominence[sid] = {
                        'count': 0,
                        'topics': set(),
                        'max_prominence': 0
                    }
                author_prominence[sid]['count'] += 1
                if pub['topic_name']:
                    author_prominence[sid]['topics'].add(pub['topic_name'])
                try:
                    prom = float(pub['topic_prominence_percentile'])
                    if prom > author_prominence[sid]['max_prominence']:
                        author_prominence[sid]['max_prominence'] = prom
                except:
                    pass

        # 연도 필터 시: 해당 기간의 저자별 논문수를 별도 집계
        prom_period_counts = {}
        if year_from and year_to:
            cursor.execute("""
                SELECT scopus_author_ids
                FROM publication
                WHERE CAST(year AS INTEGER) BETWEEN ? AND ?
                AND scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
            """, (year_from, year_to))
            for pub in cursor.fetchall():
                scopus_ids_str = pub['scopus_author_ids'] or ''
                for sid in [s.strip() for s in scopus_ids_str.replace('|', ' ').split() if s.strip()]:
                    prom_period_counts[sid] = prom_period_counts.get(sid, 0) + 1

        # 해당 기관 연구자 정보와 결합
        for scopus_id, prom_data in author_prominence.items():
            if prom_data['count'] < 2:  # 최소 2편 이상
                continue

            cursor.execute("""
                SELECT a.scopus_author_id, a.name, a.scholarly_output, a.citations,
                       a.field_weighted_citation_impact as fwci, a.h_index,
                       a.scopus_author_profile as profile_url,
                       rs.score_total_median as score_total
                FROM author a
                LEFT JOIN researcher_score rs ON a.scopus_author_id = rs.scopus_author_id
                WHERE a.scopus_author_id = ?
                AND a.primary_affiliation = ?
            """, (scopus_id, affiliation))
            author = cursor.fetchone()

            if author:
                author_dict = dict(author)
                # 연도 필터 시 해당 기간 논문수, 아니면 전체 논문수
                period_output = prom_period_counts.get(scopus_id, 0) if (year_from and year_to) else author_dict['scholarly_output']
                results.append({
                    'scopus_author_id': scopus_id,
                    'name': author_dict['name'],
                    'scholarly_output': period_output,
                    'citations': author_dict['citations'],
                    'fwci': round(author_dict['fwci'], 2) if author_dict['fwci'] else 0,
                    'h_index': author_dict['h_index'],
                    'high_prominence_count': prom_data['count'],
                    'max_prominence': round(prom_data['max_prominence'], 1),
                    'topics': list(prom_data['topics'])[:3],  # 상위 3개 토픽만
                    'profile_url': author_dict['profile_url'],
                    'score_total': author_dict['score_total'] or 0
                })

        results.sort(key=lambda x: (x['high_prominence_count'], x['max_prominence']), reverse=True)
        results = results[:limit]

    # DB 내 최신 데이터 연도
    cursor.execute("SELECT MAX(CAST(year AS INTEGER)) FROM publication WHERE year IS NOT NULL")
    max_data_year = cursor.fetchone()[0] or (datetime.now().year - 1)

    conn.close()

    return jsonify({
        'analysis_type': analysis_type,
        'count': len(results),
        'researchers': results,
        'max_data_year': max_data_year
    })


# ========================================
# 고인용 논문 유도 대상 모듈 API
# ========================================

@app.route('/api/high_citation_potential')
def api_high_citation_potential():
    """
    고인용 논문 유도 대상 API
    1. 상위 저널 게재율 높지만 인용수 낮은 연구자
    2. 국제협력 확대 시 인용 향상 가능한 연구자
    3. Top 10% 저널 게재 경험 있지만 Top 10% 피인용 없는 연구자
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    analysis_type = request.args.get('type', 'top_journal_low_citation')
    limit = request.args.get('limit', 50, type=int)
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)

    results = []

    # 연도 필터 시 실시간 계산된 점수 사용
    year_scores = None
    if year_from and year_to:
        year_scores = calculate_researcher_scores_by_year(year_from, year_to)
        year_scores_map = {r['scopus_author_id']: r for r in year_scores}

    if analysis_type == 'top_journal_low_citation':
        # 1. 상위 저널 게재율 높지만 인용수 낮은 연구자
        # 기대인용수 = SUM(field_citation_average) — 각 논문의 분야별 평균 인용수 합계
        if year_from and year_to:
            for sid, rs in year_scores_map.items():
                if rs['top_journal_pct'] < 30 or rs['scholarly_output'] < 10:
                    continue
                expected_citations = rs.get('expected_citations', 0) or 0
                actual_citations = rs.get('actual_citations_in_period', 0) or 0
                if expected_citations <= 0:
                    continue
                citation_gap = actual_citations - expected_citations
                if citation_gap < 0:
                    cpp = actual_citations / max(1, rs['scholarly_output'])
                    results.append({
                        'scopus_author_id': sid,
                        'name': rs['name'],
                        'scholarly_output': rs['scholarly_output'],
                        'expected_citations': round(expected_citations, 1),
                        'citations': actual_citations,
                        'fwci': round(rs['fwci'], 2) if rs['fwci'] else 0,
                        'h_index': rs['h_index'],
                        'top_journal_pct': round(rs['top_journal_pct'], 1),
                        'citation_gap': round(citation_gap, 1),
                        'citations_per_pub': round(cpp, 1),
                        'profile_url': rs['profile_url'],
                        'recommendation': '상위 저널 게재율 대비 인용 부족 - 홍보/네트워킹 지원 필요'
                    })
        else:
            # 비필터 모드: 전체 publication 1회 스캔으로 저자별 기대인용수/실제인용수 집계
            cursor.execute("""
                SELECT scopus_author_ids, field_citation_average, citations
                FROM publication
                WHERE scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
            """)
            author_citation_agg = {}  # {scopus_id: {expected, actual}}
            for pub in cursor.fetchall():
                fca = 0
                if pub['field_citation_average']:
                    try: fca = float(pub['field_citation_average'])
                    except: pass
                cit = 0
                if pub['citations']:
                    try: cit = int(float(str(pub['citations'])))
                    except: pass
                for sid in (s.strip() for s in (pub['scopus_author_ids'] or '').replace('|', ' ').split() if s.strip()):
                    if sid not in author_citation_agg:
                        author_citation_agg[sid] = {'expected': 0.0, 'actual': 0}
                    author_citation_agg[sid]['expected'] += fca
                    author_citation_agg[sid]['actual'] += cit

            cursor.execute("""
                SELECT rs.scopus_author_id, rs.name, rs.scholarly_output, rs.citations,
                       rs.fwci, rs.h_index, rs.top_journal_pct, rs.profile_url,
                       a.citations_per_publication
                FROM researcher_score rs
                JOIN author a ON rs.scopus_author_id = a.scopus_author_id
                WHERE rs.top_journal_pct >= 30
                AND rs.scholarly_output >= 10
                ORDER BY rs.top_journal_pct DESC
            """)
            for row in cursor.fetchall():
                row_dict = dict(row)
                sid = row_dict['scopus_author_id']
                agg = author_citation_agg.get(sid)
                if not agg:
                    continue

                expected_citations = agg['expected']
                actual_citations = agg['actual']

                if expected_citations <= 0:
                    continue
                citation_gap = actual_citations - expected_citations
                if citation_gap < 0:
                    results.append({
                        'scopus_author_id': sid,
                        'name': row_dict['name'],
                        'scholarly_output': row_dict['scholarly_output'],
                        'expected_citations': round(expected_citations, 1),
                        'citations': actual_citations,
                        'fwci': round(row_dict['fwci'], 2) if row_dict['fwci'] else 0,
                        'h_index': row_dict['h_index'],
                        'top_journal_pct': round(row_dict['top_journal_pct'], 1),
                        'citation_gap': round(citation_gap, 1),
                        'citations_per_pub': round(row_dict['citations_per_publication'], 1) if row_dict['citations_per_publication'] else 0,
                        'profile_url': row_dict['profile_url'],
                        'recommendation': '상위 저널 게재율 대비 인용 부족 - 홍보/네트워킹 지원 필요'
                    })

        results.sort(key=lambda x: x['citation_gap'], reverse=False)
        results = results[:limit]

    elif analysis_type == 'intl_collab_potential':
        # 2. 국제협력 확대 시 인용 향상 가능한 연구자
        if year_from and year_to:
            for sid, rs in year_scores_map.items():
                if rs['scholarly_output'] < 10 or (rs['fwci_median'] or 0) < 1.0:
                    continue
                intl_ratio = (rs['intl_collab_count'] or 0) / max(1, rs['scholarly_output'])
                if intl_ratio >= 0.3:
                    continue
                results.append({
                    'scopus_author_id': sid,
                    'name': rs['name'],
                    'scholarly_output': rs['scholarly_output'],
                    'citations': rs['citations'],
                    'fwci': round(rs['fwci_median'], 2) if rs['fwci_median'] else 0,
                    'h_index': rs['h_index'],
                    'intl_collab_count': rs['intl_collab_count'] or 0,
                    'intl_collab_ratio': round(intl_ratio * 100, 1),
                    'intl_collab_fwci': round(rs['intl_collab_fwci'], 2) if rs['intl_collab_fwci'] else None,
                    'profile_url': rs['profile_url'],
                    'recommendation': '국제협력 확대 시 인용 향상 가능성 높음'
                })
            results.sort(key=lambda x: x['fwci'], reverse=True)
        else:
            cursor.execute("""
                SELECT rs.*, a.most_recent_publication
                FROM researcher_score rs
                JOIN author a ON rs.scopus_author_id = a.scopus_author_id
                WHERE rs.scholarly_output >= 10
                AND rs.fwci_median >= 1.0
                AND (rs.intl_collab_count * 1.0 / rs.scholarly_output) < 0.3
                ORDER BY rs.fwci_median DESC
            """)
            rows = cursor.fetchall()
            for row in rows:
                row_dict = dict(row)
                intl_ratio = (row_dict['intl_collab_count'] or 0) / max(1, row_dict['scholarly_output'])
                results.append({
                    'scopus_author_id': row_dict['scopus_author_id'],
                    'name': row_dict['name'],
                    'scholarly_output': row_dict['scholarly_output'],
                    'citations': row_dict['citations'],
                    'fwci': round(row_dict['fwci_median'], 2) if row_dict['fwci_median'] else 0,
                    'h_index': row_dict['h_index'],
                    'intl_collab_count': row_dict['intl_collab_count'] or 0,
                    'intl_collab_ratio': round(intl_ratio * 100, 1),
                    'intl_collab_fwci': round(row_dict['intl_collab_fwci'], 2) if row_dict['intl_collab_fwci'] else None,
                    'profile_url': row_dict['profile_url'],
                    'recommendation': '국제협력 확대 시 인용 향상 가능성 높음'
                })

        results = results[:limit]

    elif analysis_type == 'top_journal_no_top_cited':
        # 3. Top 10% 저널 게재 경험 있지만 Top 10% 피인용 없는 연구자
        if year_from and year_to:
            # 연도 필터 시: 해당 기간 top journal 보유 + top 10% 피인용 없는 저자
            cursor.execute("""
                SELECT a.output_in_top_10_percentile
                FROM author a
                WHERE a.primary_affiliation = ?
                AND (a.output_in_top_10_percentile IS NULL OR a.output_in_top_10_percentile = 0)
            """, (affiliation,))
            no_top_cited_set = set()
            # 먼저 해당 기관 저자 중 top 10% 피인용 없는 저자 조회
            cursor.execute("""
                SELECT a.scopus_author_id
                FROM author a
                WHERE a.primary_affiliation = ?
                AND (a.output_in_top_10_percentile IS NULL OR a.output_in_top_10_percentile = 0)
            """, (affiliation,))
            no_top_cited_set = {row['scopus_author_id'] for row in cursor.fetchall()}

            for sid, rs in year_scores_map.items():
                if sid not in no_top_cited_set:
                    continue
                if rs['top_journal_pct'] <= 0 or rs['scholarly_output'] < 10:
                    continue
                results.append({
                    'scopus_author_id': sid,
                    'name': rs['name'],
                    'scholarly_output': rs['scholarly_output'],
                    'citations': rs['citations'],
                    'fwci': round(rs['fwci'], 2) if rs['fwci'] else 0,
                    'h_index': rs['h_index'],
                    'top_journal_pct': round(rs['top_journal_pct'], 1),
                    'top_10_cited_count': 0,
                    'profile_url': rs['profile_url'],
                    'recommendation': '상위 저널 게재 경험 있음 - 인용 극대화 전략 필요'
                })
        else:
            cursor.execute("""
                SELECT rs.*, a.output_in_top_10_percentile as top_cited_from_author
                FROM researcher_score rs
                JOIN author a ON rs.scopus_author_id = a.scopus_author_id
                WHERE rs.top_journal_pct > 0
                AND rs.scholarly_output >= 10
                AND (a.output_in_top_10_percentile IS NULL OR a.output_in_top_10_percentile = 0)
            """)
            rows = cursor.fetchall()
            for row in rows:
                row_dict = dict(row)
                results.append({
                    'scopus_author_id': row_dict['scopus_author_id'],
                    'name': row_dict['name'],
                    'scholarly_output': row_dict['scholarly_output'],
                    'citations': row_dict['citations'],
                    'fwci': round(row_dict['fwci'], 2) if row_dict['fwci'] else 0,
                    'h_index': row_dict['h_index'],
                    'top_journal_pct': round(row_dict['top_journal_pct'], 1),
                    'top_10_cited_count': 0,
                    'profile_url': row_dict['profile_url'],
                    'recommendation': '상위 저널 게재 경험 있음 - 인용 극대화 전략 필요'
                })

        results.sort(key=lambda x: x['top_journal_pct'], reverse=True)
        results = results[:limit]

    # DB 내 최신 데이터 연도
    cursor.execute("SELECT MAX(CAST(year AS INTEGER)) FROM publication WHERE year IS NOT NULL")
    max_data_year = cursor.fetchone()[0] or (datetime.now().year - 1)

    conn.close()

    return jsonify({
        'analysis_type': analysis_type,
        'count': len(results),
        'researchers': results,
        'max_data_year': max_data_year
    })


# ========================================
# 공동연구 분석 모듈 API
# ========================================

@app.route('/api/collaboration_analysis')
def api_collaboration_analysis():
    """
    공동연구 분석 API
    1. 국제협력 없는 고성과 연구자 (지원 대상)
    2. 공동연구 활발 + 고인용 연구자 (롤모델/멘토)
    3. 분야별 협력 허브 연구자
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    affiliation = get_institution_affiliation()

    analysis_type = request.args.get('type', 'no_intl_high_performer')
    limit = request.args.get('limit', 50, type=int)
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)

    results = []

    # 연도 필터 시 실시간 계산된 점수 사용
    year_scores_map = None
    if year_from and year_to and analysis_type in ('no_intl_high_performer', 'collab_high_citation'):
        year_scores = calculate_researcher_scores_by_year(year_from, year_to)
        year_scores_map = {r['scopus_author_id']: r for r in year_scores}

    if analysis_type == 'no_intl_high_performer':
        # 1. 국제협력 없는 고성과 연구자 (지원 대상)
        if year_scores_map:
            for sid, rs in year_scores_map.items():
                if rs['scholarly_output'] < 15 or (rs['fwci_median'] or 0) < 1.0:
                    continue
                if (rs['intl_collab_count'] or 0) > 2:
                    continue
                results.append({
                    'scopus_author_id': sid,
                    'name': rs['name'],
                    'scholarly_output': rs['scholarly_output'],
                    'citations': rs['citations'],
                    'fwci': round(rs['fwci_median'], 2) if rs['fwci_median'] else 0,
                    'h_index': rs['h_index'],
                    'intl_collab_count': rs['intl_collab_count'] or 0,
                    'top_journal_pct': round(rs['top_journal_pct'], 1) if rs['top_journal_pct'] else 0,
                    'profile_url': rs['profile_url'],
                    'score_total': rs['score_total_median'] or 0,
                    'support_type': '국제협력 지원 대상',
                    'recommendation': '높은 연구 성과 보유 - 국제협력 지원 시 성장 잠재력 큼'
                })
            results.sort(key=lambda x: x['fwci'], reverse=True)
        else:
            cursor.execute("""
                SELECT rs.*
                FROM researcher_score rs
                WHERE rs.scholarly_output >= 15
                AND rs.fwci_median >= 1.0
                AND (rs.intl_collab_count IS NULL OR rs.intl_collab_count <= 2)
                ORDER BY rs.fwci_median DESC
            """)
            rows = cursor.fetchall()
            for row in rows:
                row_dict = dict(row)
                results.append({
                    'scopus_author_id': row_dict['scopus_author_id'],
                    'name': row_dict['name'],
                    'scholarly_output': row_dict['scholarly_output'],
                    'citations': row_dict['citations'],
                    'fwci': round(row_dict['fwci_median'], 2) if row_dict['fwci_median'] else 0,
                    'h_index': row_dict['h_index'],
                    'intl_collab_count': row_dict['intl_collab_count'] or 0,
                    'top_journal_pct': round(row_dict['top_journal_pct'], 1) if row_dict['top_journal_pct'] else 0,
                    'profile_url': row_dict['profile_url'],
                    'score_total': row_dict['score_total_median'] or 0,
                    'support_type': '국제협력 지원 대상',
                    'recommendation': '높은 연구 성과 보유 - 국제협력 지원 시 성장 잠재력 큼'
                })

        results = results[:limit]

    elif analysis_type == 'collab_high_citation':
        # 2. 공동연구 활발 + 고인용 연구자 (롤모델/멘토)
        if year_scores_map:
            for sid, rs in year_scores_map.items():
                if rs['scholarly_output'] < 20 or (rs['intl_collab_count'] or 0) < 5:
                    continue
                if (rs['fwci_median'] or 0) < 1.5:
                    continue
                intl_ratio = (rs['intl_collab_count'] or 0) / max(1, rs['scholarly_output'])
                intl_collab_fwci = rs['intl_collab_fwci'] or 0
                results.append({
                    'scopus_author_id': sid,
                    'name': rs['name'],
                    'scholarly_output': rs['scholarly_output'],
                    'citations': rs['citations'],
                    'fwci': round(rs['fwci_median'], 2) if rs['fwci_median'] else 0,
                    'h_index': rs['h_index'],
                    'intl_collab_count': rs['intl_collab_count'] or 0,
                    'intl_collab_ratio': round(intl_ratio * 100, 1),
                    'intl_collab_fwci': round(intl_collab_fwci, 2) if intl_collab_fwci else None,
                    'profile_url': rs['profile_url'],
                    'score_total': rs['score_total_median'] or 0,
                    'role': '롤모델/멘토',
                    'recommendation': '국제협력 + 고인용 성과 - 신진 연구자 멘토링 적합'
                })
            results.sort(key=lambda x: ((x['intl_collab_fwci'] or 0) * x['intl_collab_count']), reverse=True)
        else:
            cursor.execute("""
                SELECT rs.*
                FROM researcher_score rs
                WHERE rs.scholarly_output >= 20
                AND rs.intl_collab_count >= 5
                AND rs.fwci_median >= 1.5
                ORDER BY (rs.intl_collab_fwci * rs.intl_collab_count) DESC
            """)
            rows = cursor.fetchall()
            for row in rows:
                row_dict = dict(row)
                intl_ratio = (row_dict['intl_collab_count'] or 0) / max(1, row_dict['scholarly_output'])
                results.append({
                    'scopus_author_id': row_dict['scopus_author_id'],
                    'name': row_dict['name'],
                    'scholarly_output': row_dict['scholarly_output'],
                    'citations': row_dict['citations'],
                    'fwci': round(row_dict['fwci_median'], 2) if row_dict['fwci_median'] else 0,
                    'h_index': row_dict['h_index'],
                    'intl_collab_count': row_dict['intl_collab_count'] or 0,
                    'intl_collab_ratio': round(intl_ratio * 100, 1),
                    'intl_collab_fwci': round(row_dict['intl_collab_fwci'], 2) if row_dict['intl_collab_fwci'] else None,
                    'profile_url': row_dict['profile_url'],
                    'score_total': row_dict['score_total_median'] or 0,
                    'role': '롤모델/멘토',
                    'recommendation': '국제협력 + 고인용 성과 - 신진 연구자 멘토링 적합'
                })

        results = results[:limit]

    elif analysis_type == 'field_hub':
        # 3. 분야별 협력 허브 연구자
        # 먼저 해당 기관 연구자 정보를 한 번에 캐싱
        cursor.execute("""
            SELECT a.scopus_author_id, a.name, a.scholarly_output, a.citations,
                   a.field_weighted_citation_impact as fwci, a.h_index,
                   a.scopus_author_profile as profile_url,
                   rs.score_total_median as score_total, rs.intl_collab_count
            FROM author a
            LEFT JOIN researcher_score rs ON a.scopus_author_id = rs.scopus_author_id
            WHERE a.primary_affiliation = ?
        """, (affiliation,))
        jbnu_authors = {row['scopus_author_id']: dict(row) for row in cursor.fetchall()}

        # 연도 필터 시: 해당 기간의 저자별 논문수를 별도 집계
        author_period_counts = {}
        if year_from and year_to:
            cursor.execute("""
                SELECT scopus_author_ids
                FROM publication
                WHERE CAST(year AS INTEGER) BETWEEN ? AND ?
                AND scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
            """, (year_from, year_to))
            for pub in cursor.fetchall():
                scopus_ids_str = pub['scopus_author_ids'] or ''
                for sid in [s.strip() for s in scopus_ids_str.replace('|', ' ').split() if s.strip()]:
                    if sid in jbnu_authors:
                        author_period_counts[sid] = author_period_counts.get(sid, 0) + 1

        # 각 분야에서 공저자 수가 많은 연구자 찾기
        hub_query = """
            SELECT p.all_science_journal_classification_asjc_field_name as field,
                   p.scopus_author_ids, p.number_of_authors
            FROM publication p
            WHERE p.all_science_journal_classification_asjc_field_name IS NOT NULL
            AND p.all_science_journal_classification_asjc_field_name != ''
        """
        if year_from and year_to:
            hub_query += " AND CAST(p.year AS INTEGER) BETWEEN ? AND ?"
            cursor.execute(hub_query, (year_from, year_to))
        else:
            cursor.execute(hub_query)
        pubs = cursor.fetchall()

        # 분야별 저자 협력 네트워크 분석
        field_author_network = {}
        for pub in pubs:
            field = pub['field']
            if not field:
                continue

            scopus_ids_str = pub['scopus_author_ids'] or ''
            scopus_ids = [sid.strip() for sid in scopus_ids_str.replace('|', ' ').split() if sid.strip()]

            try:
                num_authors = int(pub['number_of_authors']) if pub['number_of_authors'] else len(scopus_ids)
            except:
                num_authors = len(scopus_ids)

            for sid in scopus_ids:
                # 전북대 연구자만 처리 (미리 필터링)
                if sid not in jbnu_authors:
                    continue

                key = (field, sid)
                if key not in field_author_network:
                    field_author_network[key] = {
                        'pub_count': 0,
                        'total_coauthors': 0,
                        'unique_coauthors': set()
                    }
                field_author_network[key]['pub_count'] += 1
                field_author_network[key]['total_coauthors'] += num_authors - 1
                for other_sid in scopus_ids:
                    if other_sid != sid:
                        field_author_network[key]['unique_coauthors'].add(other_sid)

        # 전북대 연구자와 결합 (캐시에서 조회)
        field_hubs = {}
        for (field, scopus_id), data in field_author_network.items():
            if data['pub_count'] < 5:  # 최소 5편 이상
                continue

            author_dict = jbnu_authors.get(scopus_id)
            if author_dict:
                hub_score = data['pub_count'] * len(data['unique_coauthors'])

                if field not in field_hubs:
                    field_hubs[field] = []

                # 연도 필터 시 해당 기간 논문수, 아니면 전체 논문수
                period_output = author_period_counts.get(scopus_id, 0) if (year_from and year_to) else author_dict['scholarly_output']

                field_hubs[field].append({
                    'scopus_author_id': scopus_id,
                    'name': author_dict['name'],
                    'scholarly_output': period_output,
                    'citations': author_dict['citations'],
                    'fwci': round(author_dict['fwci'], 2) if author_dict['fwci'] else 0,
                    'h_index': author_dict['h_index'],
                    'field': field,
                    'field_pub_count': data['pub_count'],
                    'unique_coauthors': len(data['unique_coauthors']),
                    'hub_score': hub_score,
                    'intl_collab_count': author_dict['intl_collab_count'] or 0,
                    'profile_url': author_dict['profile_url'],
                    'score_total': author_dict['score_total'] or 0,
                    'role': '분야 허브 연구자'
                })

        # 각 분야별 상위 허브 연구자 추출
        for field in field_hubs:
            field_hubs[field].sort(key=lambda x: x['hub_score'], reverse=True)
            field_hubs[field] = field_hubs[field][:3]  # 분야별 상위 3명

        # 결과 평탄화
        for field, researchers in field_hubs.items():
            results.extend(researchers)

        results.sort(key=lambda x: x['hub_score'], reverse=True)
        results = results[:limit]

    # DB 내 최신 데이터 연도
    cursor.execute("SELECT MAX(CAST(year AS INTEGER)) FROM publication WHERE year IS NOT NULL")
    max_data_year = cursor.fetchone()[0] or (datetime.now().year - 1)

    conn.close()

    return jsonify({
        'analysis_type': analysis_type,
        'count': len(results),
        'researchers': results,
        'max_data_year': max_data_year
    })


@app.route('/research_strategy')
@login_required
def research_strategy():
    """연구 전략 메인 페이지"""
    log_activity('페이지 조회', '연구 전략')
    return render_template('research_strategy.html')


@app.route('/api/research_trajectory')
def api_research_trajectory():
    """
    연구 궤적 분석 API
    1. growth_trajectory — 3년 연속 성장 연구자
    2. early_warning — 연구 활동 감소 조기 경보
    3. rising_star — 신진 라이징 스타
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    affiliation = get_institution_affiliation()

    analysis_type = request.args.get('type', 'growth_trajectory')
    limit = request.args.get('limit', 50, type=int)
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)

    from datetime import datetime
    current_year = datetime.now().year

    # author 테이블 dict 구축 (해당 기관 소속만)
    cursor.execute("""
        SELECT scopus_author_id, name, scholarly_output, citations,
               field_weighted_citation_impact, h_index,
               oldest_publication, most_recent_publication, scopus_author_profile
        FROM author
        WHERE primary_affiliation = ?
    """, (affiliation,))
    jbnu_authors = {}
    for row in cursor.fetchall():
        jbnu_authors[row['scopus_author_id']] = {
            'name': row['name'],
            'scholarly_output': row['scholarly_output'] or 0,
            'citations': row['citations'] or 0,
            'fwci': row['field_weighted_citation_impact'] or 0,
            'h_index': row['h_index'] or 0,
            'oldest_pub': row['oldest_publication'],
            'most_recent_pub': row['most_recent_publication'],
            'profile_url': row['scopus_author_profile'] or ''
        }

    # publication 1회 스캔 → 연구자별 연도별 논문수 dict
    # 궤적 분석은 연속 연도 비교가 필요하므로 항상 전체 데이터 로드
    cursor.execute("""
        SELECT scopus_author_ids, year, field_weighted_citation_impact
        FROM publication
        WHERE scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
    """)

    author_year_counts = {}  # {scopus_id: {year: count}}
    author_year_fwci = {}    # {scopus_id: {year: [fwci_vals]}}
    for pub in cursor.fetchall():
        try:
            yr = int(float(pub['year'])) if pub['year'] else None
        except (ValueError, TypeError):
            yr = None
        if yr is None:
            continue

        fwci_val = 0
        if pub['field_weighted_citation_impact']:
            try:
                fwci_val = float(pub['field_weighted_citation_impact'])
            except (ValueError, TypeError):
                pass

        for sid in (s.strip() for s in (pub['scopus_author_ids'] or '').replace('|', ' ').split() if s.strip()):
            if sid not in author_year_counts:
                author_year_counts[sid] = {}
                author_year_fwci[sid] = {}
            author_year_counts[sid][yr] = author_year_counts[sid].get(yr, 0) + 1
            if yr not in author_year_fwci[sid]:
                author_year_fwci[sid][yr] = []
            author_year_fwci[sid][yr].append(fwci_val)

    results = []

    # DB에서 가장 최근 연도 조회 (현재 연도에 데이터가 없을 수 있음)
    cursor.execute("SELECT MAX(CAST(year AS INTEGER)) FROM publication WHERE year IS NOT NULL")
    max_data_year = cursor.fetchone()[0] or (current_year - 1)

    if analysis_type == 'growth_trajectory':
        # 3년 연속 논문수 증가 연구자
        check_end = min(year_to, max_data_year) if (year_from and year_to) else max_data_year
        check_start = check_end - 2  # 최근 3년

        for sid, year_dict in author_year_counts.items():
            if sid not in jbnu_authors:
                continue
            author = jbnu_authors[sid]

            counts = []
            for y in range(check_start, check_end + 1):
                counts.append(year_dict.get(y, 0))

            # 3년 연속 증가 확인 (각 연도 >= 1편이면서 순차적 증가)
            if len(counts) >= 3 and counts[0] >= 1:
                is_growing = all(counts[i] > counts[i-1] for i in range(1, len(counts)))
                if not is_growing:
                    continue

                total_period = sum(year_dict.get(y, 0) for y in range(check_start, check_end + 1))
                growth_pct = round((counts[-1] - counts[0]) / counts[0] * 100) if counts[0] > 0 else 0

                results.append({
                    'scopus_author_id': sid,
                    'name': author['name'],
                    'scholarly_output': author['scholarly_output'],
                    'citations': author['citations'],
                    'fwci': round(author['fwci'], 2),
                    'h_index': author['h_index'],
                    'year_counts': {str(y): year_dict.get(y, 0) for y in range(check_start, check_end + 1)},
                    'y1': counts[0],
                    'y2': counts[1],
                    'y3': counts[2],
                    'growth_pct': growth_pct,
                    'total_period': total_period,
                    'profile_url': author['profile_url']
                })

        results.sort(key=lambda x: x['growth_pct'], reverse=True)
        results = results[:limit]

    elif analysis_type == 'early_warning':
        # 연구 활동 감소 조기 경보: 과거 활발 + 최근 2년 급감
        check_end = min(year_to, max_data_year) if (year_from and year_to) else max_data_year
        recent_start = check_end - 1
        past_start = check_end - 4
        past_end = check_end - 2

        for sid, year_dict in author_year_counts.items():
            if sid not in jbnu_authors:
                continue
            author = jbnu_authors[sid]

            past_count = sum(year_dict.get(y, 0) for y in range(past_start, past_end + 1))
            recent_count = sum(year_dict.get(y, 0) for y in range(recent_start, check_end + 1))

            if past_count < 5:  # 과거 최소 5편 이상이어야
                continue

            past_avg = past_count / 3.0
            recent_avg = recent_count / 2.0

            if past_avg > 0 and recent_avg < past_avg * 0.5:
                decline_pct = round((1 - recent_avg / past_avg) * 100)
                results.append({
                    'scopus_author_id': sid,
                    'name': author['name'],
                    'scholarly_output': author['scholarly_output'],
                    'citations': author['citations'],
                    'fwci': round(author['fwci'], 2),
                    'h_index': author['h_index'],
                    'past_avg': round(past_avg, 1),
                    'recent_avg': round(recent_avg, 1),
                    'decline_pct': decline_pct,
                    'past_period': f"{past_start}-{past_end}",
                    'recent_period': f"{recent_start}-{check_end}",
                    'profile_url': author['profile_url']
                })

        results.sort(key=lambda x: x['decline_pct'], reverse=True)
        results = results[:limit]

    elif analysis_type == 'rising_star':
        # 신진 라이징 스타: 최초발표 5년 이내 + 높은 FWCI 또는 h-index
        for sid, author in jbnu_authors.items():
            oldest = author['oldest_pub']
            if not oldest:
                continue
            try:
                oldest_yr = int(oldest)
            except (ValueError, TypeError):
                continue

            career_years = current_year - oldest_yr + 1
            if career_years > 5 or career_years < 1:
                continue

            if sid not in author_year_counts:
                continue

            total_pubs = sum(author_year_counts[sid].values())
            if total_pubs < 3:  # 최소 3편
                continue

            fwci = author['fwci']
            h_index = author['h_index'] or 0

            # FWCI > 1.5 또는 h_index >= 5 (신진 기준)
            if fwci < 1.5 and h_index < 5:
                continue

            star_score = round(fwci * 40 + h_index * 3 + total_pubs * 2, 1)

            results.append({
                'scopus_author_id': sid,
                'name': author['name'],
                'scholarly_output': total_pubs,
                'citations': author['citations'],
                'fwci': round(fwci, 2),
                'h_index': h_index,
                'career_years': career_years,
                'first_pub_year': oldest_yr,
                'star_score': star_score,
                'profile_url': author['profile_url']
            })

        results.sort(key=lambda x: x['star_score'], reverse=True)
        results = results[:limit]

    conn.close()

    return jsonify({
        'analysis_type': analysis_type,
        'count': len(results),
        'researchers': results,
        'max_data_year': max_data_year
    })


@app.route('/api/societal_impact')
def api_societal_impact():
    """
    사회적 영향력 분석 API
    1. patent_cited — 특허 인용 연구자
    2. policy_cited — 정책 인용 연구자
    3. sdg_contribution — SDG 기여 연구자
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    affiliation = get_institution_affiliation()

    analysis_type = request.args.get('type', 'patent_cited')
    limit = request.args.get('limit', 50, type=int)
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)

    year_condition = ""
    year_params = []
    if year_from and year_to:
        year_condition = " AND CAST(year AS INTEGER) BETWEEN ? AND ?"
        year_params = [year_from, year_to]

    # author 테이블 dict (해당 기관 소속만)
    cursor.execute("""
        SELECT scopus_author_id, name, scholarly_output, citations,
               field_weighted_citation_impact, h_index, scopus_author_profile
        FROM author
        WHERE primary_affiliation = ?
    """, (affiliation,))
    jbnu_authors = {}
    for row in cursor.fetchall():
        jbnu_authors[row['scopus_author_id']] = {
            'name': row['name'],
            'scholarly_output': row['scholarly_output'] or 0,
            'citations': row['citations'] or 0,
            'fwci': row['field_weighted_citation_impact'] or 0,
            'h_index': row['h_index'] or 0,
            'profile_url': row['scopus_author_profile'] or ''
        }

    results = []

    if analysis_type == 'patent_cited':
        # 특허 인용 연구자
        cursor.execute(f"""
            SELECT scopus_author_ids, main_patent_families
            FROM publication
            WHERE is_patent_cited = 1
                  AND scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
                  {year_condition}
        """, year_params)

        author_patent = {}  # {sid: {'patent_pubs': count, 'total_patents': sum}}
        for pub in cursor.fetchall():
            patent_count = 0
            if pub['main_patent_families']:
                try:
                    patent_count = int(float(str(pub['main_patent_families'])))
                except (ValueError, TypeError):
                    pass

            for sid in (s.strip() for s in (pub['scopus_author_ids'] or '').replace('|', ' ').split() if s.strip()):
                if sid not in author_patent:
                    author_patent[sid] = {'patent_pubs': 0, 'total_patents': 0}
                author_patent[sid]['patent_pubs'] += 1
                author_patent[sid]['total_patents'] += patent_count

        for sid, data in author_patent.items():
            if sid not in jbnu_authors:
                continue
            author = jbnu_authors[sid]
            results.append({
                'scopus_author_id': sid,
                'name': author['name'],
                'scholarly_output': author['scholarly_output'],
                'citations': author['citations'],
                'fwci': round(author['fwci'], 2),
                'h_index': author['h_index'],
                'patent_pubs': data['patent_pubs'],
                'total_patents': data['total_patents'],
                'profile_url': author['profile_url']
            })

        results.sort(key=lambda x: x['total_patents'], reverse=True)
        results = results[:limit]

    elif analysis_type == 'policy_cited':
        # 정책 인용 연구자
        cursor.execute(f"""
            SELECT scopus_author_ids, policy_citations
            FROM publication
            WHERE is_policy_cited = 1
                  AND scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
                  {year_condition}
        """, year_params)

        author_policy = {}
        for pub in cursor.fetchall():
            policy_count = 0
            if pub['policy_citations']:
                try:
                    policy_count = int(float(str(pub['policy_citations'])))
                except (ValueError, TypeError):
                    pass

            for sid in (s.strip() for s in (pub['scopus_author_ids'] or '').replace('|', ' ').split() if s.strip()):
                if sid not in author_policy:
                    author_policy[sid] = {'policy_pubs': 0, 'total_policies': 0}
                author_policy[sid]['policy_pubs'] += 1
                author_policy[sid]['total_policies'] += policy_count

        for sid, data in author_policy.items():
            if sid not in jbnu_authors:
                continue
            author = jbnu_authors[sid]
            results.append({
                'scopus_author_id': sid,
                'name': author['name'],
                'scholarly_output': author['scholarly_output'],
                'citations': author['citations'],
                'fwci': round(author['fwci'], 2),
                'h_index': author['h_index'],
                'policy_pubs': data['policy_pubs'],
                'total_policies': data['total_policies'],
                'profile_url': author['profile_url']
            })

        results.sort(key=lambda x: x['total_policies'], reverse=True)
        results = results[:limit]

    elif analysis_type == 'sdg_contribution':
        # SDG 기여 연구자
        cursor.execute(f"""
            SELECT scopus_author_ids, sustainable_development_goals_2025
            FROM publication
            WHERE is_SDG = 1
                  AND scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
                  {year_condition}
        """, year_params)

        author_sdg = {}  # {sid: {'sdg_pubs': count, 'sdg_categories': set}}
        for pub in cursor.fetchall():
            sdg_text = pub['sustainable_development_goals_2025'] or ''
            sdg_list = [s.strip() for s in sdg_text.replace('|', ',').split(',') if s.strip()]

            for sid in (s.strip() for s in (pub['scopus_author_ids'] or '').replace('|', ' ').split() if s.strip()):
                if sid not in author_sdg:
                    author_sdg[sid] = {'sdg_pubs': 0, 'sdg_categories': set()}
                author_sdg[sid]['sdg_pubs'] += 1
                for sdg in sdg_list:
                    author_sdg[sid]['sdg_categories'].add(sdg)

        for sid, data in author_sdg.items():
            if sid not in jbnu_authors:
                continue
            author = jbnu_authors[sid]
            categories = sorted(data['sdg_categories'])
            results.append({
                'scopus_author_id': sid,
                'name': author['name'],
                'scholarly_output': author['scholarly_output'],
                'citations': author['citations'],
                'fwci': round(author['fwci'], 2),
                'h_index': author['h_index'],
                'sdg_pubs': data['sdg_pubs'],
                'sdg_count': len(categories),
                'sdg_categories': ', '.join(categories[:5]),
                'profile_url': author['profile_url']
            })

        results.sort(key=lambda x: x['sdg_pubs'], reverse=True)
        results = results[:limit]

    conn.close()

    return jsonify({
        'analysis_type': analysis_type,
        'count': len(results),
        'researchers': results
    })


@app.route('/api/strategic_portfolio')
def api_strategic_portfolio():
    """
    전략 포트폴리오 분석 API
    1. field_strategy_map — 분야별 전략 맵
    2. collab_effect — 협력 효과 분석
    3. academic_corporate — 산학협력 분석
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    affiliation = get_institution_affiliation()

    analysis_type = request.args.get('type', 'field_strategy_map')
    limit = request.args.get('limit', 50, type=int)
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)

    year_condition = ""
    year_params = []
    if year_from and year_to:
        year_condition = " AND CAST(year AS INTEGER) BETWEEN ? AND ?"
        year_params = [year_from, year_to]

    results = []

    if analysis_type == 'field_strategy_map':
        # 분야별 전략 맵: ASJC 분야별 논문수/평균FWCI/국제비율 집계
        cursor.execute(f"""
            SELECT all_science_journal_classification_asjc_field_name,
                   field_weighted_citation_impact, is_international, is_top_cited,
                   is_1, citations
            FROM publication
            WHERE all_science_journal_classification_asjc_field_name IS NOT NULL
                  AND all_science_journal_classification_asjc_field_name != ''
                  {year_condition}
        """, year_params)

        field_stats = {}  # {field: {count, fwci_sum, intl, top_cited, is_1, citations_sum}}
        for pub in cursor.fetchall():
            fields = [f.strip() for f in (pub['all_science_journal_classification_asjc_field_name'] or '').replace('|', ',').split(',') if f.strip()]

            fwci_val = 0
            if pub['field_weighted_citation_impact']:
                try:
                    fwci_val = float(pub['field_weighted_citation_impact'])
                except (ValueError, TypeError):
                    pass

            cit_val = 0
            if pub['citations']:
                try:
                    cit_val = int(float(str(pub['citations'])))
                except (ValueError, TypeError):
                    pass

            is_intl = 1 if pub['is_international'] else 0
            is_tc = 1 if pub['is_top_cited'] else 0
            is_1_val = 1 if pub['is_1'] else 0

            for field in fields:
                if field not in field_stats:
                    field_stats[field] = {'count': 0, 'fwci_sum': 0, 'intl': 0, 'top_cited': 0, 'is_1': 0, 'citations_sum': 0}
                fs = field_stats[field]
                fs['count'] += 1
                fs['fwci_sum'] += fwci_val
                fs['intl'] += is_intl
                fs['top_cited'] += is_tc
                fs['is_1'] += is_1_val
                fs['citations_sum'] += cit_val

        for field, fs in field_stats.items():
            if fs['count'] < 10:  # 최소 10편
                continue
            avg_fwci = round(fs['fwci_sum'] / fs['count'], 2)
            intl_ratio = round(fs['intl'] / fs['count'] * 100, 1)
            top_cited_ratio = round(fs['top_cited'] / fs['count'] * 100, 1)
            top_journal_ratio = round(fs['is_1'] / fs['count'] * 100, 1)

            # 전략 등급: FWCI >= 1.5 + 국제비율 >= 40% = "핵심 강점"
            if avg_fwci >= 1.5 and intl_ratio >= 40:
                strategy = '핵심 강점'
                strategy_class = 'success'
            elif avg_fwci >= 1.0:
                strategy = '성장 분야'
                strategy_class = 'primary'
            elif fs['count'] >= 50:
                strategy = '규모 우위'
                strategy_class = 'info'
            else:
                strategy = '육성 필요'
                strategy_class = 'warning'

            results.append({
                'field': field,
                'pub_count': fs['count'],
                'avg_fwci': avg_fwci,
                'intl_ratio': intl_ratio,
                'top_cited_ratio': top_cited_ratio,
                'top_journal_ratio': top_journal_ratio,
                'total_citations': fs['citations_sum'],
                'strategy': strategy,
                'strategy_class': strategy_class
            })

        results.sort(key=lambda x: x['pub_count'], reverse=True)
        results = results[:limit]

    elif analysis_type == 'collab_effect':
        # 협력 효과 분석: 연구자별 협력 유형별 FWCI 비교
        cursor.execute(f"""
            SELECT scopus_author_ids, field_weighted_citation_impact,
                   is_single_author, is_institutional_collab, is_national_collab, is_international
            FROM publication
            WHERE scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
                  {year_condition}
        """, year_params)

        # author dict (해당 기관 소속만)
        cursor2 = conn.cursor()
        cursor2.execute("""
            SELECT scopus_author_id, name, scholarly_output, citations,
                   field_weighted_citation_impact, h_index, scopus_author_profile
            FROM author
            WHERE primary_affiliation = ?
        """, (affiliation,))
        jbnu_authors = {}
        for row in cursor2.fetchall():
            jbnu_authors[row['scopus_author_id']] = {
                'name': row['name'],
                'scholarly_output': row['scholarly_output'] or 0,
                'citations': row['citations'] or 0,
                'fwci': row['field_weighted_citation_impact'] or 0,
                'h_index': row['h_index'] or 0,
                'profile_url': row['scopus_author_profile'] or ''
            }

        author_collab = {}  # {sid: {single: [fwci], institutional: [fwci], national: [fwci], international: [fwci]}}
        for pub in cursor.fetchall():
            fwci_val = 0
            if pub['field_weighted_citation_impact']:
                try:
                    fwci_val = float(pub['field_weighted_citation_impact'])
                except (ValueError, TypeError):
                    pass

            collab_type = 'other'
            if pub['is_international']:
                collab_type = 'international'
            elif pub['is_national_collab']:
                collab_type = 'national'
            elif pub['is_institutional_collab']:
                collab_type = 'institutional'
            elif pub['is_single_author']:
                collab_type = 'single'

            for sid in (s.strip() for s in (pub['scopus_author_ids'] or '').replace('|', ' ').split() if s.strip()):
                if sid not in author_collab:
                    author_collab[sid] = {'single': [], 'institutional': [], 'national': [], 'international': [], 'other': []}
                author_collab[sid][collab_type].append(fwci_val)

        for sid, data in author_collab.items():
            if sid not in jbnu_authors:
                continue
            author = jbnu_authors[sid]

            total_pubs = sum(len(v) for v in data.values())
            if total_pubs < 5:
                continue

            def avg_fwci(lst):
                return round(sum(lst) / len(lst), 2) if lst else None

            intl_fwci = avg_fwci(data['international'])
            natl_fwci = avg_fwci(data['national'])
            inst_fwci = avg_fwci(data['institutional'])
            single_fwci = avg_fwci(data['single'])

            # 국제 > 국내 효과 비교
            best_fwci = max(filter(None, [intl_fwci, natl_fwci, inst_fwci, single_fwci]), default=0)
            if intl_fwci and single_fwci and single_fwci > 0:
                collab_boost = round((intl_fwci - single_fwci) / single_fwci * 100)
            elif intl_fwci and natl_fwci and natl_fwci > 0:
                collab_boost = round((intl_fwci - natl_fwci) / natl_fwci * 100)
            else:
                collab_boost = 0

            results.append({
                'scopus_author_id': sid,
                'name': author['name'],
                'scholarly_output': author['scholarly_output'],
                'citations': author['citations'],
                'fwci': round(author['fwci'], 2),
                'h_index': author['h_index'],
                'single_fwci': single_fwci,
                'inst_fwci': inst_fwci,
                'natl_fwci': natl_fwci,
                'intl_fwci': intl_fwci,
                'intl_count': len(data['international']),
                'collab_boost': collab_boost,
                'profile_url': author['profile_url']
            })

        results.sort(key=lambda x: x['collab_boost'], reverse=True)
        results = results[:limit]

    elif analysis_type == 'academic_corporate':
        # 산학협력 분석
        cursor.execute(f"""
            SELECT scopus_author_ids, field_weighted_citation_impact, citations
            FROM publication
            WHERE is_academic_corporate = 1
                  AND scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
                  {year_condition}
        """, year_params)

        # author dict (해당 기관 소속만)
        cursor2 = conn.cursor()
        cursor2.execute("""
            SELECT scopus_author_id, name, scholarly_output, citations,
                   field_weighted_citation_impact, h_index, scopus_author_profile
            FROM author
            WHERE primary_affiliation = ?
        """, (affiliation,))
        jbnu_authors = {}
        for row in cursor2.fetchall():
            jbnu_authors[row['scopus_author_id']] = {
                'name': row['name'],
                'scholarly_output': row['scholarly_output'] or 0,
                'citations': row['citations'] or 0,
                'fwci': row['field_weighted_citation_impact'] or 0,
                'h_index': row['h_index'] or 0,
                'profile_url': row['scopus_author_profile'] or ''
            }

        # 전체 논문수도 필요 (산학 비율 계산용)
        cursor.execute(f"""
            SELECT scopus_author_ids
            FROM publication
            WHERE scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
                  {year_condition}
        """, year_params)
        author_total = {}
        for pub in cursor.fetchall():
            for sid in (s.strip() for s in (pub['scopus_author_ids'] or '').replace('|', ' ').split() if s.strip()):
                author_total[sid] = author_total.get(sid, 0) + 1

        # 산학협력 논문 집계 재수행
        cursor.execute(f"""
            SELECT scopus_author_ids, field_weighted_citation_impact, citations
            FROM publication
            WHERE is_academic_corporate = 1
                  AND scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
                  {year_condition}
        """, year_params)

        author_corp = {}
        for pub in cursor.fetchall():
            fwci_val = 0
            if pub['field_weighted_citation_impact']:
                try:
                    fwci_val = float(pub['field_weighted_citation_impact'])
                except (ValueError, TypeError):
                    pass
            cit_val = 0
            if pub['citations']:
                try:
                    cit_val = int(float(str(pub['citations'])))
                except (ValueError, TypeError):
                    pass

            for sid in (s.strip() for s in (pub['scopus_author_ids'] or '').replace('|', ' ').split() if s.strip()):
                if sid not in author_corp:
                    author_corp[sid] = {'corp_pubs': 0, 'fwci_list': [], 'cit_sum': 0}
                author_corp[sid]['corp_pubs'] += 1
                author_corp[sid]['fwci_list'].append(fwci_val)
                author_corp[sid]['cit_sum'] += cit_val

        for sid, data in author_corp.items():
            if sid not in jbnu_authors:
                continue
            if data['corp_pubs'] < 2:
                continue
            author = jbnu_authors[sid]
            total = author_total.get(sid, 1)
            corp_ratio = round(data['corp_pubs'] / total * 100, 1) if total > 0 else 0
            avg_fwci = round(sum(data['fwci_list']) / len(data['fwci_list']), 2) if data['fwci_list'] else 0

            results.append({
                'scopus_author_id': sid,
                'name': author['name'],
                'scholarly_output': author['scholarly_output'],
                'citations': author['citations'],
                'fwci': round(author['fwci'], 2),
                'h_index': author['h_index'],
                'corp_pubs': data['corp_pubs'],
                'corp_ratio': corp_ratio,
                'corp_avg_fwci': avg_fwci,
                'corp_citations': data['cit_sum'],
                'profile_url': author['profile_url']
            })

        results.sort(key=lambda x: x['corp_pubs'], reverse=True)
        results = results[:limit]

    conn.close()

    return jsonify({
        'analysis_type': analysis_type,
        'count': len(results),
        'researchers': results
    })


###############################################################################
# 학문분야분석 (Field Analysis)
###############################################################################

@app.route('/field_analysis')
@login_required
def field_analysis():
    log_activity('페이지 조회', '학문분야분석')
    return render_template('field_analysis.html')


@app.route('/api/field_list')
def api_field_list():
    """학문분야 목록 조회 — ASJC 분야명별 논문 수 (5편 이상)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT all_science_journal_classification_asjc_field_name
        FROM publication
        WHERE all_science_journal_classification_asjc_field_name IS NOT NULL
              AND all_science_journal_classification_asjc_field_name != ''
    """)

    field_counts = {}
    for pub in cursor.fetchall():
        fields = [f.strip() for f in (pub['all_science_journal_classification_asjc_field_name'] or '').replace('|', ',').split(',') if f.strip()]
        for field in fields:
            field_counts[field] = field_counts.get(field, 0) + 1

    conn.close()

    result = [{'name': name, 'pub_count': cnt}
              for name, cnt in field_counts.items() if cnt >= 5]
    result.sort(key=lambda x: x['pub_count'], reverse=True)

    return jsonify({'fields': result})


@app.route('/api/field_analysis/overview')
def api_field_analysis_overview():
    """
    분야별 종합 현황 API
    - fields: ||| 구분 분야명
    - year_from / year_to: 기간 필터
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    fields_param = request.args.get('fields', '')
    selected_fields = [f.strip() for f in fields_param.split('|||') if f.strip()]
    if not selected_fields:
        conn.close()
        return jsonify({'count': 0, 'fields': []})

    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)

    year_condition = ""
    year_params = []
    if year_from and year_to:
        year_condition = " AND CAST(year AS INTEGER) BETWEEN ? AND ?"
        year_params = [year_from, year_to]

    cursor.execute(f"""
        SELECT all_science_journal_classification_asjc_field_name,
               field_weighted_citation_impact, is_international, is_top_cited,
               is_1, citations, is_SDG, is_patent_cited, is_academic_corporate
        FROM publication
        WHERE all_science_journal_classification_asjc_field_name IS NOT NULL
              AND all_science_journal_classification_asjc_field_name != ''
              {year_condition}
    """, year_params)

    selected_set = set(selected_fields)
    field_stats = {}
    for pub in cursor.fetchall():
        fields = [f.strip() for f in (pub['all_science_journal_classification_asjc_field_name'] or '').replace('|', ',').split(',') if f.strip()]
        matched = [f for f in fields if f in selected_set]
        if not matched:
            continue

        fwci_val = 0
        try:
            fwci_val = float(pub['field_weighted_citation_impact']) if pub['field_weighted_citation_impact'] else 0
        except (ValueError, TypeError):
            pass

        cit_val = 0
        try:
            cit_val = int(float(str(pub['citations']))) if pub['citations'] else 0
        except (ValueError, TypeError):
            pass

        is_intl = 1 if pub['is_international'] else 0
        is_tc = 1 if pub['is_top_cited'] else 0
        is_1_val = 1 if pub['is_1'] else 0
        is_sdg = 1 if pub['is_SDG'] else 0
        is_patent = 1 if pub['is_patent_cited'] else 0
        is_corp = 1 if pub['is_academic_corporate'] else 0

        for field in matched:
            if field not in field_stats:
                field_stats[field] = {
                    'count': 0, 'fwci_sum': 0, 'intl': 0, 'top_cited': 0,
                    'is_1': 0, 'citations_sum': 0, 'sdg': 0, 'patent': 0, 'corp': 0
                }
            fs = field_stats[field]
            fs['count'] += 1
            fs['fwci_sum'] += fwci_val
            fs['intl'] += is_intl
            fs['top_cited'] += is_tc
            fs['is_1'] += is_1_val
            fs['citations_sum'] += cit_val
            fs['sdg'] += is_sdg
            fs['patent'] += is_patent
            fs['corp'] += is_corp

    conn.close()

    results = []
    for field in selected_fields:
        fs = field_stats.get(field)
        if not fs:
            results.append({
                'field': field, 'pub_count': 0, 'total_citations': 0,
                'avg_fwci': 0, 'intl_ratio': 0, 'top_journal_ratio': 0,
                'top_cited_ratio': 0, 'strategy': '데이터 없음', 'strategy_class': 'secondary',
                'sdg_ratio': 0, 'corp_ratio': 0, 'patent_ratio': 0
            })
            continue

        cnt = fs['count']
        avg_fwci = round(fs['fwci_sum'] / cnt, 2)
        intl_ratio = round(fs['intl'] / cnt * 100, 1)
        top_cited_ratio = round(fs['top_cited'] / cnt * 100, 1)
        top_journal_ratio = round(fs['is_1'] / cnt * 100, 1)
        sdg_ratio = round(fs['sdg'] / cnt * 100, 1)
        corp_ratio = round(fs['corp'] / cnt * 100, 1)
        patent_ratio = round(fs['patent'] / cnt * 100, 1)

        if avg_fwci >= 1.5 and intl_ratio >= 40:
            strategy = '핵심 강점'
            strategy_class = 'success'
        elif avg_fwci >= 1.0:
            strategy = '성장 분야'
            strategy_class = 'primary'
        elif cnt >= 50:
            strategy = '규모 우위'
            strategy_class = 'info'
        else:
            strategy = '육성 필요'
            strategy_class = 'warning'

        results.append({
            'field': field,
            'pub_count': cnt,
            'total_citations': fs['citations_sum'],
            'avg_fwci': avg_fwci,
            'intl_ratio': intl_ratio,
            'top_journal_ratio': top_journal_ratio,
            'top_cited_ratio': top_cited_ratio,
            'strategy': strategy,
            'strategy_class': strategy_class,
            'sdg_ratio': sdg_ratio,
            'corp_ratio': corp_ratio,
            'patent_ratio': patent_ratio
        })

    return jsonify({'count': len(results), 'fields': results})


@app.route('/api/field_analysis/researchers')
def api_field_analysis_researchers():
    """
    분야별 주요 연구자 API
    - fields: ||| 구분 분야명
    - year_from / year_to: 기간 필터
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    affiliation = get_institution_affiliation()

    fields_param = request.args.get('fields', '')
    selected_fields = [f.strip() for f in fields_param.split('|||') if f.strip()]
    if not selected_fields:
        conn.close()
        return jsonify({'count': 0, 'researchers': []})

    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)

    year_condition = ""
    year_params = []
    if year_from and year_to:
        year_condition = " AND CAST(year AS INTEGER) BETWEEN ? AND ?"
        year_params = [year_from, year_to]

    # 해당 기관 저자 정보
    cursor.execute("""
        SELECT scopus_author_id, name, scholarly_output, citations,
               field_weighted_citation_impact, h_index, scopus_author_profile
        FROM author
        WHERE primary_affiliation = ?
    """, (affiliation,))
    jbnu_authors = {}
    for row in cursor.fetchall():
        jbnu_authors[row['scopus_author_id']] = {
            'name': row['name'],
            'scholarly_output': row['scholarly_output'] or 0,
            'citations': row['citations'] or 0,
            'fwci': row['field_weighted_citation_impact'] or 0,
            'h_index': row['h_index'] or 0,
            'profile_url': row['scopus_author_profile'] or ''
        }

    # 분야별 논문에서 저자 추출
    cursor.execute(f"""
        SELECT all_science_journal_classification_asjc_field_name,
               scopus_author_ids, field_weighted_citation_impact, is_international
        FROM publication
        WHERE all_science_journal_classification_asjc_field_name IS NOT NULL
              AND all_science_journal_classification_asjc_field_name != ''
              AND scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
              {year_condition}
    """, year_params)

    selected_set = set(selected_fields)
    # {(sid, field): {pubs, fwci_list, intl}}
    author_field = {}
    for pub in cursor.fetchall():
        fields = [f.strip() for f in (pub['all_science_journal_classification_asjc_field_name'] or '').replace('|', ',').split(',') if f.strip()]
        matched = [f for f in fields if f in selected_set]
        if not matched:
            continue

        fwci_val = 0
        try:
            fwci_val = float(pub['field_weighted_citation_impact']) if pub['field_weighted_citation_impact'] else 0
        except (ValueError, TypeError):
            pass

        is_intl = 1 if pub['is_international'] else 0

        sids = [s.strip() for s in (pub['scopus_author_ids'] or '').replace('|', ' ').split() if s.strip()]
        for sid in sids:
            if sid not in jbnu_authors:
                continue
            for field in matched:
                key = (sid, field)
                if key not in author_field:
                    author_field[key] = {'pubs': 0, 'fwci_list': [], 'intl': 0}
                af = author_field[key]
                af['pubs'] += 1
                af['fwci_list'].append(fwci_val)
                af['intl'] += is_intl

    conn.close()

    results = []
    for (sid, field), data in author_field.items():
        if data['pubs'] < 2:
            continue
        author = jbnu_authors[sid]
        avg_fwci = round(sum(data['fwci_list']) / len(data['fwci_list']), 2) if data['fwci_list'] else 0
        results.append({
            'scopus_author_id': sid,
            'name': author['name'],
            'field': field,
            'field_pubs': data['pubs'],
            'field_fwci': avg_fwci,
            'h_index': author['h_index'],
            'scholarly_output': author['scholarly_output'],
            'citations': author['citations'],
            'intl_collabs': data['intl'],
            'profile_url': author['profile_url']
        })

    results.sort(key=lambda x: x['field_pubs'], reverse=True)
    results = results[:200]

    return jsonify({'count': len(results), 'researchers': results})


@app.route('/api/field_analysis/trend')
def api_field_analysis_trend():
    """
    분야별 연도 추이 API
    - fields: ||| 구분 분야명
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    fields_param = request.args.get('fields', '')
    selected_fields = [f.strip() for f in fields_param.split('|||') if f.strip()]
    if not selected_fields:
        conn.close()
        return jsonify({'count': 0, 'trends': []})

    cursor.execute("""
        SELECT all_science_journal_classification_asjc_field_name,
               year, field_weighted_citation_impact
        FROM publication
        WHERE all_science_journal_classification_asjc_field_name IS NOT NULL
              AND all_science_journal_classification_asjc_field_name != ''
              AND year IS NOT NULL AND year != ''
    """)

    selected_set = set(selected_fields)
    # {field: {year: {count, fwci_sum}}}
    field_year = {}
    for pub in cursor.fetchall():
        fields = [f.strip() for f in (pub['all_science_journal_classification_asjc_field_name'] or '').replace('|', ',').split(',') if f.strip()]
        matched = [f for f in fields if f in selected_set]
        if not matched:
            continue

        try:
            year = int(float(pub['year']))
        except (ValueError, TypeError):
            continue

        fwci_val = 0
        try:
            fwci_val = float(pub['field_weighted_citation_impact']) if pub['field_weighted_citation_impact'] else 0
        except (ValueError, TypeError):
            pass

        for field in matched:
            if field not in field_year:
                field_year[field] = {}
            if year not in field_year[field]:
                field_year[field][year] = {'count': 0, 'fwci_sum': 0}
            field_year[field][year]['count'] += 1
            field_year[field][year]['fwci_sum'] += fwci_val

    conn.close()

    # 연도 범위 결정
    all_years = set()
    for fy in field_year.values():
        all_years.update(fy.keys())
    if not all_years:
        return jsonify({'count': 0, 'trends': [], 'years': []})

    years_sorted = sorted(all_years)

    trends = []
    for field in selected_fields:
        fy = field_year.get(field, {})
        yearly = []
        for y in years_sorted:
            d = fy.get(y, {'count': 0, 'fwci_sum': 0})
            avg_fwci = round(d['fwci_sum'] / d['count'], 2) if d['count'] > 0 else 0
            yearly.append({'year': y, 'pub_count': d['count'], 'avg_fwci': avg_fwci})
        trends.append({'field': field, 'yearly': yearly})

    return jsonify({
        'count': len(trends),
        'years': years_sorted,
        'trends': trends
    })


@app.route('/api/field_analysis/collaborators')
def api_field_analysis_collaborators():
    """
    분야별 기관 간 공동연구자 API
    - 전북대와 고려대 연구자 간의 공동 저자 관계를 분석
    """
    import sqlite3

    fields_param = request.args.get('fields', '')
    selected_fields = [f.strip() for f in fields_param.split('|||') if f.strip()]
    year_from = request.args.get('year_from')
    year_to = request.args.get('year_to')

    if not selected_fields:
        return jsonify({'count': 0, 'collaborators': []})

    # 두 DB 모두 열기 (원본 파일 사용)
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    jbnu_db_path = os.path.join(base_dir, 'jbnu.db')
    korea_db_path = os.path.join(base_dir, 'korea.db')

    try:
        jbnu_conn = sqlite3.connect(jbnu_db_path)
        jbnu_conn.row_factory = sqlite3.Row
        jbnu_cursor = jbnu_conn.cursor()

        korea_conn = sqlite3.connect(korea_db_path)
        korea_conn.row_factory = sqlite3.Row
        korea_cursor = korea_conn.cursor()
    except Exception as e:
        return jsonify({'count': 0, 'collaborators': [], 'error': f'DB 연결 실패: {str(e)}'})

    # 전북대 연구자 목록 (scopus_author_id -> name)
    jbnu_cursor.execute("SELECT scopus_author_id, name FROM author WHERE scopus_author_id IS NOT NULL")
    jbnu_authors = {row['scopus_author_id']: row['name'] for row in jbnu_cursor.fetchall()}

    # 고려대 연구자 목록 (scopus_author_id -> name)
    korea_cursor.execute("SELECT scopus_author_id, name FROM author WHERE scopus_author_id IS NOT NULL AND primary_affiliation = 'Korea University'")
    korea_authors = {row['scopus_author_id']: row['name'] for row in korea_cursor.fetchall()}

    # 연도 조건
    year_condition = ""
    if year_from and year_to:
        year_condition = f"AND CAST(year AS INTEGER) >= {int(year_from)} AND CAST(year AS INTEGER) <= {int(year_to)}"

    # 전북대 논문에서 공동저자 찾기
    selected_set = set(selected_fields)
    collaborations = {}  # (jbnu_id, korea_id, field) -> {pub_count, pubs}

    # 전북대 논문의 저자 정보 조회
    jbnu_cursor.execute(f"""
        SELECT eid, all_science_journal_classification_asjc_field_name,
               scopus_author_ids, title, year
        FROM publication
        WHERE all_science_journal_classification_asjc_field_name IS NOT NULL
              AND scopus_author_ids IS NOT NULL
              {year_condition}
    """)

    for pub in jbnu_cursor.fetchall():
        fields = [f.strip() for f in (pub['all_science_journal_classification_asjc_field_name'] or '').replace('|', ',').split(',') if f.strip()]
        matched_fields = [f for f in fields if f in selected_set]
        if not matched_fields:
            continue

        # 저자 ID 파싱 (파이프 또는 세미콜론으로 구분)
        raw_ids = (pub['scopus_author_ids'] or '').replace(';', '|')
        author_ids = [a.strip() for a in raw_ids.split('|') if a.strip()]

        # 전북대 저자와 고려대 저자 식별
        jbnu_in_pub = [aid for aid in author_ids if aid in jbnu_authors]
        korea_in_pub = [aid for aid in author_ids if aid in korea_authors]

        # 공동 저자 쌍 기록
        for jbnu_id in jbnu_in_pub:
            for korea_id in korea_in_pub:
                for field in matched_fields:
                    key = (jbnu_id, korea_id, field)
                    if key not in collaborations:
                        collaborations[key] = {
                            'jbnu_id': jbnu_id,
                            'jbnu_name': jbnu_authors.get(jbnu_id, 'Unknown'),
                            'korea_id': korea_id,
                            'korea_name': korea_authors.get(korea_id, 'Unknown'),
                            'field': field,
                            'pub_count': 0,
                            'eids': set()
                        }
                    collaborations[key]['pub_count'] += 1
                    collaborations[key]['eids'].add(pub['eid'])

    jbnu_conn.close()
    korea_conn.close()

    # 결과 정리
    result = []
    for key, collab in collaborations.items():
        result.append({
            'jbnu_id': collab['jbnu_id'],
            'jbnu_name': collab['jbnu_name'],
            'korea_id': collab['korea_id'],
            'korea_name': collab['korea_name'],
            'field': collab['field'],
            'pub_count': len(collab['eids']),  # 고유 논문 수
            'jbnu_profile': f"https://www.scopus.com/authid/detail.uri?authorId={collab['jbnu_id']}",
            'korea_profile': f"https://www.scopus.com/authid/detail.uri?authorId={collab['korea_id']}"
        })

    # 논문 수 기준 내림차순 정렬
    result.sort(key=lambda x: (-x['pub_count'], x['field'], x['jbnu_name']))

    return jsonify({
        'count': len(result),
        'collaborators': result
    })


# ==================== 설문 관련 ====================

@app.route('/survey')
@login_required
def survey():
    """설문 페이지"""
    log_activity('페이지 조회', '설문참여')
    return render_template('survey.html')


@app.route('/api/survey/check_email', methods=['POST'])
def check_survey_email():
    """이메일 중복 체크"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()

        if not email:
            return jsonify({'exists': False})

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM survey_response WHERE LOWER(email) = ?", (email,))
        count = cursor.fetchone()[0]
        conn.close()

        return jsonify({'exists': count > 0})
    except Exception as e:
        return jsonify({'exists': False, 'error': str(e)}), 500


@app.route('/api/survey/submit', methods=['POST'])
def submit_survey():
    """설문 응답 저장"""
    try:
        data = request.get_json()

        email = data.get('email', '').strip().lower()

        if not email:
            return jsonify({'success': False, 'error': '이메일을 입력해 주세요.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # 이메일 중복 체크
        cursor.execute("SELECT COUNT(*) FROM survey_response WHERE LOWER(email) = ?", (email,))
        if cursor.fetchone()[0] > 0:
            conn.close()
            return jsonify({'success': False, 'error': '이미 설문에 참여하셨습니다.'}), 400

        # 클라이언트 IP (프록시 고려)
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address:
            ip_address = ip_address.split(',')[0].strip()

        cursor.execute("""
            INSERT INTO survey_response (
                email, role, role_other, experience, purpose, purpose_other,
                a1_efficiency, a2_decision, a3_strategy, a4_context,
                b1_easy_understand, b2_intuitive, b3_find_info, b4_flow, b5_help,
                c1_trust, c2_relevance, c3_comprehension, c4_evidence, c5_timeliness,
                d1_actual_use, d2_changed_decision,
                e1_continue, e2_recommend,
                f1_strengths, f2_difficulties, f3_trust_improve, f4_feature_request, f5_other,
                ip_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            email,
            data.get('role'), data.get('role_other'), data.get('experience'),
            ','.join(data.get('purpose', [])), data.get('purpose_other'),
            data.get('a1'), data.get('a2'), data.get('a3'), data.get('a4'),
            data.get('b1'), data.get('b2'), data.get('b3'), data.get('b4'), data.get('b5'),
            data.get('c1'), data.get('c2'), data.get('c3'), data.get('c4'), data.get('c5'),
            data.get('d1'), data.get('d2'),
            data.get('e1'), data.get('e2'),
            data.get('f1'), data.get('f2'), data.get('f3'), data.get('f4'), data.get('f5'),
            ip_address
        ))

        conn.commit()
        response_id = cursor.lastrowid
        conn.close()

        return jsonify({'success': True, 'response_id': response_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/survey/analysis')
@login_required
def survey_analysis():
    """설문 결과 분석 페이지"""
    log_activity('페이지 조회', '설문분석')
    return render_template('survey_analysis.html')


@app.route('/api/survey/results')
def survey_results():
    """설문 결과 조회 (관리자용)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 전체 응답 수
    cursor.execute("SELECT COUNT(*) FROM survey_response")
    total_count = cursor.fetchone()[0]

    # 역할별 분포
    cursor.execute("""
        SELECT role, COUNT(*) as cnt
        FROM survey_response
        GROUP BY role
    """)
    role_dist = [{'role': r['role'], 'count': r['cnt']} for r in cursor.fetchall()]

    # 리커트 문항 평균
    cursor.execute("""
        SELECT
            AVG(a1_efficiency) as a1, AVG(a2_decision) as a2, AVG(a3_strategy) as a3, AVG(a4_context) as a4,
            AVG(b1_easy_understand) as b1, AVG(b2_intuitive) as b2, AVG(b3_find_info) as b3, AVG(b4_flow) as b4, AVG(b5_help) as b5,
            AVG(c1_trust) as c1, AVG(c2_relevance) as c2, AVG(c3_comprehension) as c3, AVG(c4_evidence) as c4, AVG(c5_timeliness) as c5,
            AVG(d1_actual_use) as d1, AVG(d2_changed_decision) as d2,
            AVG(e1_continue) as e1, AVG(e2_recommend) as e2
        FROM survey_response
    """)
    avg_row = cursor.fetchone()
    likert_avg = {
        'A_유용성': {
            'a1_업무효율': round(avg_row['a1'] or 0, 2),
            'a2_의사결정': round(avg_row['a2'] or 0, 2),
            'a3_전략수립': round(avg_row['a3'] or 0, 2),
            'a4_맥락적합': round(avg_row['a4'] or 0, 2)
        },
        'B_사용성': {
            'b1_이해용이': round(avg_row['b1'] or 0, 2),
            'b2_직관성': round(avg_row['b2'] or 0, 2),
            'b3_정보탐색': round(avg_row['b3'] or 0, 2),
            'b4_흐름': round(avg_row['b4'] or 0, 2),
            'b5_도움말': round(avg_row['b5'] or 0, 2)
        },
        'C_정보품질': {
            'c1_신뢰성': round(avg_row['c1'] or 0, 2),
            'c2_관련성': round(avg_row['c2'] or 0, 2),
            'c3_이해도': round(avg_row['c3'] or 0, 2),
            'c4_근거제시': round(avg_row['c4'] or 0, 2),
            'c5_최신성': round(avg_row['c5'] or 0, 2)
        },
        'D_활용경험': {
            'd1_실제활용': round(avg_row['d1'] or 0, 2),
            'd2_판단변화': round(avg_row['d2'] or 0, 2)
        },
        'E_활용의향': {
            'e1_지속사용': round(avg_row['e1'] or 0, 2),
            'e2_추천의향': round(avg_row['e2'] or 0, 2)
        }
    }

    # 서술형 응답
    cursor.execute("""
        SELECT f1_strengths, f2_difficulties, f3_trust_improve, f4_feature_request, f5_other, submitted_at
        FROM survey_response
        ORDER BY submitted_at DESC
    """)
    qualitative = []
    for row in cursor.fetchall():
        qualitative.append({
            'strengths': row['f1_strengths'],
            'difficulties': row['f2_difficulties'],
            'trust_improve': row['f3_trust_improve'],
            'feature_request': row['f4_feature_request'],
            'other': row['f5_other'],
            'submitted_at': row['submitted_at']
        })

    conn.close()

    return jsonify({
        'total_count': total_count,
        'role_distribution': role_dist,
        'likert_averages': likert_avg,
        'qualitative_responses': qualitative
    })


@app.route('/api/translate', methods=['POST'])
def translate_text():
    """텍스트 번역 API (Google Translate 사용)"""
    data = request.get_json()
    texts = data.get('texts', [])
    source_lang = data.get('source', 'ko')
    target_lang = data.get('target', 'en')

    if not texts:
        return jsonify({'translations': []})

    try:
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        translations = []
        for text in texts:
            if text and text.strip():
                translated = translator.translate(text)
                translations.append(translated)
            else:
                translations.append(text)
        return jsonify({'translations': translations})
    except Exception as e:
        # 번역 실패 시 원본 텍스트 반환
        return jsonify({'translations': texts, 'error': str(e)})


# ============================================
# 점수 산출 기준 동적 설정 (Scoring Presets)
# ============================================

def init_scoring_presets_table():
    """scoring_presets 테이블 초기화 및 시스템 프리셋 삽입"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scoring_presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            is_system INTEGER DEFAULT 0,
            is_default INTEGER DEFAULT 0,

            -- 총점 배분
            total_core INTEGER DEFAULT 80,
            total_supplementary INTEGER DEFAULT 10,

            -- 핵심지표 비율 (%)
            pct_fwci INTEGER DEFAULT 25,
            pct_top10 INTEGER DEFAULT 25,
            pct_top_journal INTEGER DEFAULT 25,
            pct_intl_collab INTEGER DEFAULT 25,

            -- 보조지표 비율 (%)
            pct_sdg INTEGER DEFAULT 30,
            pct_oa INTEGER DEFAULT 30,
            pct_topic INTEGER DEFAULT 40,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 시스템 프리셋이 없으면 삽입
    cursor.execute("SELECT COUNT(*) FROM scoring_presets WHERE is_system = 1")
    if cursor.fetchone()[0] == 0:
        system_presets = [
            ('기본 설정', '균형 잡힌 기본 가중치 (권장)', 1, 1, 80, 10, 25, 25, 25, 25, 30, 30, 40),
            ('인용 중심', 'FWCI와 Top 10% 피인용 강조', 1, 0, 80, 10, 35, 35, 15, 15, 30, 30, 40),
            ('국제협력 중심', '국제공동연구 성과 강조', 1, 0, 80, 10, 20, 20, 20, 40, 30, 30, 40),
            ('품질 중심', '상위저널 게재 강조', 1, 0, 80, 10, 30, 20, 35, 15, 30, 30, 40),
            ('SDG/사회기여 중심', '사회적 기여 강조', 1, 0, 70, 30, 25, 25, 25, 25, 40, 30, 30),
            ('100점 만점', '100점 스케일 (핵심 85 + 보조 15)', 1, 0, 85, 15, 25, 25, 25, 25, 30, 30, 40),
        ]
        cursor.executemany("""
            INSERT INTO scoring_presets
            (name, description, is_system, is_default, total_core, total_supplementary,
             pct_fwci, pct_top10, pct_top_journal, pct_intl_collab, pct_sdg, pct_oa, pct_topic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, system_presets)

    conn.commit()
    conn.close()

# 앱 시작 시 테이블 초기화
try:
    init_scoring_presets_table()
except Exception as e:
    print(f"Warning: Could not initialize scoring_presets table: {e}")


@app.route('/api/scoring_presets')
def api_get_scoring_presets():
    """모든 프리셋 목록 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM scoring_presets
        ORDER BY is_default DESC, is_system DESC, name
    """)
    rows = cursor.fetchall()
    conn.close()

    presets = []
    for row in rows:
        presets.append({
            'id': row['id'],
            'name': row['name'],
            'description': row['description'],
            'is_system': row['is_system'] == 1,
            'is_default': row['is_default'] == 1,
            'total_core': row['total_core'],
            'total_supplementary': row['total_supplementary'],
            'total_score': row['total_core'] + row['total_supplementary'],
            'pct_fwci': row['pct_fwci'],
            'pct_top10': row['pct_top10'],
            'pct_top_journal': row['pct_top_journal'],
            'pct_intl_collab': row['pct_intl_collab'],
            'pct_sdg': row['pct_sdg'],
            'pct_oa': row['pct_oa'],
            'pct_topic': row['pct_topic']
        })

    return jsonify({'presets': presets})


@app.route('/api/scoring_presets/<int:preset_id>')
def api_get_scoring_preset(preset_id):
    """특정 프리셋 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scoring_presets WHERE id = ?", (preset_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Preset not found'}), 404

    return jsonify({
        'id': row['id'],
        'name': row['name'],
        'description': row['description'],
        'is_system': row['is_system'] == 1,
        'is_default': row['is_default'] == 1,
        'total_core': row['total_core'],
        'total_supplementary': row['total_supplementary'],
        'total_score': row['total_core'] + row['total_supplementary'],
        'pct_fwci': row['pct_fwci'],
        'pct_top10': row['pct_top10'],
        'pct_top_journal': row['pct_top_journal'],
        'pct_intl_collab': row['pct_intl_collab'],
        'pct_sdg': row['pct_sdg'],
        'pct_oa': row['pct_oa'],
        'pct_topic': row['pct_topic']
    })


@app.route('/api/scoring_presets', methods=['POST'])
def api_create_scoring_preset():
    """새 프리셋 생성"""
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO scoring_presets
        (name, description, is_system, is_default, total_core, total_supplementary,
         pct_fwci, pct_top10, pct_top_journal, pct_intl_collab, pct_sdg, pct_oa, pct_topic)
        VALUES (?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('name', '사용자 정의'),
        data.get('description', ''),
        data.get('total_core', 80),
        data.get('total_supplementary', 10),
        data.get('pct_fwci', 25),
        data.get('pct_top10', 25),
        data.get('pct_top_journal', 25),
        data.get('pct_intl_collab', 25),
        data.get('pct_sdg', 30),
        data.get('pct_oa', 30),
        data.get('pct_topic', 40)
    ))

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'id': new_id})


@app.route('/api/scoring_presets/<int:preset_id>', methods=['PUT'])
def api_update_scoring_preset(preset_id):
    """프리셋 수정 (사용자 정의만 가능)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 시스템 프리셋인지 확인
    cursor.execute("SELECT is_system FROM scoring_presets WHERE id = ?", (preset_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Preset not found'}), 404
    if row['is_system'] == 1:
        conn.close()
        return jsonify({'error': 'Cannot modify system preset'}), 403

    data = request.get_json()
    cursor.execute("""
        UPDATE scoring_presets SET
            name = ?, description = ?,
            total_core = ?, total_supplementary = ?,
            pct_fwci = ?, pct_top10 = ?, pct_top_journal = ?, pct_intl_collab = ?,
            pct_sdg = ?, pct_oa = ?, pct_topic = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        data.get('name'),
        data.get('description', ''),
        data.get('total_core', 80),
        data.get('total_supplementary', 10),
        data.get('pct_fwci', 25),
        data.get('pct_top10', 25),
        data.get('pct_top_journal', 25),
        data.get('pct_intl_collab', 25),
        data.get('pct_sdg', 30),
        data.get('pct_oa', 30),
        data.get('pct_topic', 40),
        preset_id
    ))

    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/api/scoring_presets/<int:preset_id>', methods=['DELETE'])
def api_delete_scoring_preset(preset_id):
    """프리셋 삭제 (사용자 정의만 가능)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT is_system FROM scoring_presets WHERE id = ?", (preset_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Preset not found'}), 404
    if row['is_system'] == 1:
        conn.close()
        return jsonify({'error': 'Cannot delete system preset'}), 403

    cursor.execute("DELETE FROM scoring_presets WHERE id = ?", (preset_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


def calculate_researcher_scores_with_preset(year_from, year_to, preset):
    """
    프리셋 기반 연구자 점수 계산
    preset: dict with total_core, total_supplementary, pct_fwci, pct_top10, etc.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    affiliation = get_institution_affiliation()

    # 프리셋에서 가중치 추출
    total_core = preset.get('total_core', 80)
    total_supp = preset.get('total_supplementary', 10)

    # 핵심지표 실제 점수 (비율 * 총점)
    max_fwci = total_core * preset.get('pct_fwci', 25) / 100
    max_top10 = total_core * preset.get('pct_top10', 25) / 100
    max_top_journal = total_core * preset.get('pct_top_journal', 25) / 100
    max_intl = total_core * preset.get('pct_intl_collab', 25) / 100

    # 보조지표 실제 점수
    max_sdg = total_supp * preset.get('pct_sdg', 30) / 100
    max_oa = total_supp * preset.get('pct_oa', 30) / 100
    max_topic = total_supp * preset.get('pct_topic', 40) / 100

    # 점수 계산 함수들 (0~1 범위로 정규화)
    def calc_fwci_ratio(fwci):
        """FWCI를 0~1 비율로 변환"""
        if fwci is None: return 0.286  # 10/35 기준
        if fwci >= 10: return 1.0
        elif fwci >= 8: return 0.857
        elif fwci >= 6: return 0.714
        elif fwci >= 4: return 0.571
        elif fwci >= 2: return 0.429
        else: return 0.286

    def calc_top_cited_ratio(is_top_10):
        """Top 10%면 1.0, 아니면 0.5"""
        return 1.0 if is_top_10 else 0.5

    def calc_top_journal_ratio(snip_pct, citescore_pct, sjr_pct):
        """Top 10% 저널이면 1.0, 아니면 0.33"""
        for pct in [snip_pct, citescore_pct, sjr_pct]:
            if pct:
                try:
                    if int(pct) <= 10:
                        return 1.0
                except:
                    pass
        return 0.33

    def calc_intl_fwci_ratio(fwci):
        """국제협력 FWCI를 0~1 비율로 변환"""
        if fwci is None: return 0
        if fwci >= 2.0: return 1.0
        elif fwci >= 1.5: return 0.7
        elif fwci >= 1.0: return 0.4
        else: return 0.1

    def calc_sdg_ratio(has_sdg):
        return 1.0 if has_sdg else 0

    def calc_oa_ratio(has_oa):
        return 1.0 if has_oa else 0

    def calc_prominence_ratio(prominence):
        if prominence is None: return 0
        return 1.0 if prominence >= 90 else 0

    def calc_median(values):
        if not values: return 0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
        return sorted_vals[mid]

    def calc_mean(values):
        if not values: return 0
        return sum(values) / len(values)

    # 1. 해당 기관 저자 목록
    cursor.execute("""
        SELECT author_id, scopus_author_id, name, scholarly_output, citations,
               field_weighted_citation_impact, h_index, output_in_top_10_percentile,
               scopus_author_profile
        FROM author
        WHERE primary_affiliation = ?
    """, (affiliation,))
    authors = cursor.fetchall()

    # 2. 연도 범위 필터된 논문 데이터
    if year_from and year_to:
        cursor.execute("""
            SELECT scopus_author_ids, field_weighted_citation_impact, is_international, is_10,
                   snip_percentile_publication_year, citescore_percentile_publication_year,
                   sjr_percentile_publication_year, sustainable_development_goals_2025,
                   open_access, topic_prominence_percentile, year,
                   field_citation_average, citations
            FROM publication
            WHERE CAST(year AS INTEGER) BETWEEN ? AND ?
        """, (year_from, year_to))
    else:
        cursor.execute("""
            SELECT scopus_author_ids, field_weighted_citation_impact, is_international, is_10,
                   snip_percentile_publication_year, citescore_percentile_publication_year,
                   sjr_percentile_publication_year, sustainable_development_goals_2025,
                   open_access, topic_prominence_percentile, year,
                   field_citation_average, citations
            FROM publication
        """)
    filtered_pubs = cursor.fetchall()

    # 3. 저자별 논문 점수 집계
    author_pub_scores = {}
    for pub in filtered_pubs:
        scopus_ids_str = pub['scopus_author_ids'] or ''
        scopus_ids = [sid.strip() for sid in scopus_ids_str.replace('|', ' ').split() if sid.strip()]

        fwci_val = None
        if pub['field_weighted_citation_impact']:
            try: fwci_val = float(pub['field_weighted_citation_impact'])
            except: pass

        prominence_val = None
        if pub['topic_prominence_percentile']:
            try: prominence_val = float(pub['topic_prominence_percentile'])
            except: pass

        pub_scores = {
            'fwci_val': fwci_val,
            'fwci_ratio': calc_fwci_ratio(fwci_val),
            'top_cited_ratio': calc_top_cited_ratio(pub['is_10'] == 1),
            'top_journal_ratio': calc_top_journal_ratio(
                pub['snip_percentile_publication_year'],
                pub['citescore_percentile_publication_year'],
                pub['sjr_percentile_publication_year']
            ),
            'is_international': pub['is_international'] == 1,
            'intl_fwci_ratio': calc_intl_fwci_ratio(fwci_val) if pub['is_international'] == 1 else None,
            'sdg_ratio': calc_sdg_ratio(bool(pub['sustainable_development_goals_2025'])),
            'oa_ratio': calc_oa_ratio(bool(pub['open_access'])),
            'prominence_ratio': calc_prominence_ratio(prominence_val),
        }

        for scopus_id in scopus_ids:
            if scopus_id not in author_pub_scores:
                author_pub_scores[scopus_id] = []
            author_pub_scores[scopus_id].append(pub_scores)

    conn.close()

    # 4. 각 저자별 점수 계산
    results = []
    for author in authors:
        author_dict = dict(author)
        scopus_id = author_dict['scopus_author_id']
        pub_scores_list = author_pub_scores.get(scopus_id, [])

        if not pub_scores_list:
            continue

        # 비율값들의 평균/중위값 계산
        fwci_ratios = [p['fwci_ratio'] for p in pub_scores_list]
        fwci_values = [p['fwci_val'] for p in pub_scores_list if p['fwci_val'] is not None]
        top_cited_ratios = [p['top_cited_ratio'] for p in pub_scores_list]
        top_journal_ratios = [p['top_journal_ratio'] for p in pub_scores_list]
        intl_fwci_ratios = [p['intl_fwci_ratio'] for p in pub_scores_list if p['intl_fwci_ratio'] is not None]
        sdg_ratios = [p['sdg_ratio'] for p in pub_scores_list]
        oa_ratios = [p['oa_ratio'] for p in pub_scores_list]
        prominence_ratios = [p['prominence_ratio'] for p in pub_scores_list]

        # FWCI는 mean/median 선택 가능
        fwci_mean_ratio = calc_mean(fwci_ratios) if fwci_ratios else 0
        fwci_median_ratio = calc_median(fwci_ratios) if fwci_ratios else 0
        fwci_mean_val = calc_mean(fwci_values) if fwci_values else 0
        fwci_median_val = calc_median(fwci_values) if fwci_values else 0

        # 실제 점수 계산 (비율 * 최대점수)
        score_fwci_mean = round(fwci_mean_ratio * max_fwci, 2)
        score_fwci_median = round(fwci_median_ratio * max_fwci, 2)
        score_top_cited = round(calc_mean(top_cited_ratios) * max_top10, 2)
        score_top_journal = round(calc_mean(top_journal_ratios) * max_top_journal, 2)
        score_intl_collab = round(calc_mean(intl_fwci_ratios) * max_intl, 2) if intl_fwci_ratios else 0
        score_sdg = round(calc_mean(sdg_ratios) * max_sdg, 2)
        score_oa = round(calc_mean(oa_ratios) * max_oa, 2)
        score_prominence = round(calc_mean(prominence_ratios) * max_topic, 2)

        score_core_mean = round(score_fwci_mean + score_top_cited + score_top_journal + score_intl_collab, 2)
        score_core_median = round(score_fwci_median + score_top_cited + score_top_journal + score_intl_collab, 2)
        score_secondary = round(score_sdg + score_oa + score_prominence, 2)
        score_total_mean = round(score_core_mean + score_secondary, 2)
        score_total_median = round(score_core_median + score_secondary, 2)

        intl_count = sum(1 for p in pub_scores_list if p['is_international'])
        intl_fwci_vals = [p['fwci_val'] for p in pub_scores_list if p['is_international'] and p['fwci_val'] is not None]
        intl_fwci_avg = calc_mean(intl_fwci_vals) if intl_fwci_vals else None
        top_journal_count = sum(1 for p in pub_scores_list if p['top_journal_ratio'] == 1.0)
        top_journal_pct = (top_journal_count / len(pub_scores_list)) * 100 if pub_scores_list else 0

        results.append({
            'author_id': author_dict['author_id'],
            'scopus_author_id': scopus_id,
            'name': author_dict['name'],
            'scholarly_output': len(pub_scores_list),
            'scholarly_output_total': author_dict['scholarly_output'],
            'citations': author_dict['citations'],
            'fwci': round(fwci_median_val, 2),
            'fwci_mean': round(fwci_mean_val, 2),
            'fwci_median': round(fwci_median_val, 2),
            'h_index': author_dict['h_index'],
            'top_10_pct_count': author_dict['output_in_top_10_percentile'],
            'primary_affiliation': affiliation,
            'profile_url': author_dict['scopus_author_profile'],
            'intl_collab_count': intl_count,
            'intl_collab_fwci': round(intl_fwci_avg, 2) if intl_fwci_avg else None,
            'top_journal_pct': round(top_journal_pct, 1),
            'has_sdg': any(p['sdg_ratio'] > 0 for p in pub_scores_list),
            'has_oa': any(p['oa_ratio'] > 0 for p in pub_scores_list),
            'avg_topic_prominence': 0,
            'score_fwci': score_fwci_median,
            'score_fwci_mean': score_fwci_mean,
            'score_fwci_median': score_fwci_median,
            'score_top_cited': score_top_cited,
            'score_top_journal': score_top_journal,
            'score_intl_collab': score_intl_collab,
            'score_core': score_core_median,
            'score_core_mean': score_core_mean,
            'score_core_median': score_core_median,
            'score_sdg': score_sdg,
            'score_oa': score_oa,
            'score_prominence': score_prominence,
            'score_secondary': score_secondary,
            'score_total': score_total_median,
            'score_total_mean': score_total_mean,
            'score_total_median': score_total_median,
            # 프리셋 정보 (UI에서 만점 표시용)
            'max_core': total_core,
            'max_secondary': total_supp,
            'max_total': total_core + total_supp
        })

    return results


@app.route('/api/researcher_scores_custom')
def api_researcher_scores_custom():
    """프리셋 기반 연구자 점수 API"""
    try:
        min_output = request.args.get('min_output', 10, type=int)
        limit = request.args.get('limit', 100, type=int)
        fwci_method = request.args.get('fwci_method', 'median')
        year_from = request.args.get('year_from', type=int)
        year_to = request.args.get('year_to', type=int)
        preset_id = request.args.get('preset_id', type=int)

        # 프리셋 로드 (없으면 기본값)
        if preset_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scoring_presets WHERE id = ?", (preset_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                preset = {
                    'total_core': row['total_core'],
                    'total_supplementary': row['total_supplementary'],
                    'pct_fwci': row['pct_fwci'],
                    'pct_top10': row['pct_top10'],
                    'pct_top_journal': row['pct_top_journal'],
                    'pct_intl_collab': row['pct_intl_collab'],
                    'pct_sdg': row['pct_sdg'],
                    'pct_oa': row['pct_oa'],
                    'pct_topic': row['pct_topic']
                }
            else:
                preset = None
        else:
            # URL 파라미터로 직접 전달된 경우
            preset = {
                'total_core': request.args.get('total_core', 80, type=int),
                'total_supplementary': request.args.get('total_supplementary', 10, type=int),
                'pct_fwci': request.args.get('pct_fwci', 25, type=int),
                'pct_top10': request.args.get('pct_top10', 25, type=int),
                'pct_top_journal': request.args.get('pct_top_journal', 25, type=int),
                'pct_intl_collab': request.args.get('pct_intl_collab', 25, type=int),
                'pct_sdg': request.args.get('pct_sdg', 30, type=int),
                'pct_oa': request.args.get('pct_oa', 30, type=int),
                'pct_topic': request.args.get('pct_topic', 40, type=int)
            }

        if not preset:
            preset = {
                'total_core': 80, 'total_supplementary': 10,
                'pct_fwci': 25, 'pct_top10': 25, 'pct_top_journal': 25, 'pct_intl_collab': 25,
                'pct_sdg': 30, 'pct_oa': 30, 'pct_topic': 40
            }

        # 점수 계산
        all_results = calculate_researcher_scores_with_preset(year_from, year_to, preset)

        # FWCI 방식에 따라 정렬
        if fwci_method == 'mean':
            sort_key = 'score_total_mean'
        else:
            sort_key = 'score_total_median'

        # 필터 및 정렬
        filtered = [r for r in all_results if r['scholarly_output'] >= min_output]
        filtered.sort(key=lambda x: x[sort_key], reverse=True)

        total_count = len(filtered)
        if limit > 0:
            filtered = filtered[:limit]

        # FWCI 방식에 따라 표시값 선택
        results = []
        for r in filtered:
            if fwci_method == 'mean':
                r['fwci'] = r['fwci_mean']
                r['score_fwci'] = r['score_fwci_mean']
                r['score_core'] = r['score_core_mean']
                r['score_total'] = r['score_total_mean']
            else:
                r['fwci'] = r['fwci_median']
                r['score_fwci'] = r['score_fwci_median']
                r['score_core'] = r['score_core_median']
                r['score_total'] = r['score_total_median']
            results.append(r)

        return jsonify({
            'total_count': total_count,
            'returned_count': len(results),
            'fwci_method': fwci_method,
            'year_from': year_from,
            'year_to': year_to,
            'preset': preset,
            'researchers': results
        })
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


# ============================================
# 연구분야분석 (Strategic Field Analysis)
# ============================================

@app.route('/strategic_field_analysis')
@login_required
def strategic_field_analysis():
    """연구분야분석 페이지"""
    log_activity('페이지 조회', '연구분야분석')
    return render_template('strategic_field_analysis.html')


@app.route('/world_ranking')
@login_required
def world_ranking():
    """세계대학평가 페이지"""
    log_activity('페이지 조회', '세계대학평가')
    return render_template('world_ranking.html',
                           institutions=INSTITUTION_NAMES,
                           current_institution=session.get('institution', 'jbnu'))


@app.route('/api/world_ranking_metrics')
@login_required
def api_world_ranking_metrics():
    """세계대학평가 지표 API"""
    try:
        institution = request.args.get('institution') or None
        conn = get_db_connection(institution=institution)
        cursor = conn.cursor()
        affiliation = get_institution_affiliation(institution=institution)
        year_from = request.args.get('year_from', type=int)
        year_to = request.args.get('year_to', type=int)

        # 연도 필터
        year_filter = ""
        year_params = []
        if year_from and year_to:
            year_filter = "AND CAST(year AS INTEGER) >= ? AND CAST(year AS INTEGER) <= ?"
            year_params = [year_from, year_to]

        # 1. 종합 지표
        cursor.execute(f"""
            SELECT
                COUNT(*) as total_pubs,
                COALESCE(SUM(CAST(citations AS REAL)), 0) as total_citations,
                COALESCE(AVG(CAST(citations AS REAL)), 0) as avg_citations,
                COALESCE(AVG(CAST(field_weighted_citation_impact AS REAL)), 0) as avg_fwci,
                SUM(CASE WHEN is_international = 1 THEN 1 ELSE 0 END) as intl_count,
                SUM(CASE WHEN is_10 = 1 THEN 1 ELSE 0 END) as top10_count,
                SUM(CASE WHEN is_25 = 1 THEN 1 ELSE 0 END) as top25_count,
                SUM(CASE WHEN open_access IS NOT NULL AND open_access != '' AND open_access != '-' THEN 1 ELSE 0 END) as oa_count,
                SUM(CASE WHEN is_SDG = 1 THEN 1 ELSE 0 END) as sdg_count,
                SUM(CASE WHEN is_1 = 1 THEN 1 ELSE 0 END) as top1_count,
                SUM(CASE WHEN is_patent_cited = 1 THEN 1 ELSE 0 END) as patent_cited_count,
                SUM(CASE WHEN is_policy_cited = 1 THEN 1 ELSE 0 END) as policy_cited_count,
                SUM(CASE WHEN is_academic_corporate = 1 THEN 1 ELSE 0 END) as corporate_count
            FROM publication
            WHERE 1=1 {year_filter}
        """, year_params)
        row = cursor.fetchone()
        overview = {k: (v if v is not None else 0) for k, v in dict(row).items()}
        total = overview['total_pubs'] or 1

        overview['intl_rate'] = round(overview['intl_count'] / total * 100, 1)
        overview['top10_rate'] = round(overview['top10_count'] / total * 100, 1)
        overview['top25_rate'] = round(overview['top25_count'] / total * 100, 1)
        overview['oa_rate'] = round(overview['oa_count'] / total * 100, 1)
        overview['sdg_rate'] = round(overview['sdg_count'] / total * 100, 1)
        overview['top1_rate'] = round(overview['top1_count'] / total * 100, 1)
        overview['patent_cited_rate'] = round(overview['patent_cited_count'] / total * 100, 1)
        overview['corporate_rate'] = round(overview['corporate_count'] / total * 100, 1)
        overview['avg_citations'] = round(overview['avg_citations'], 2)
        overview['avg_fwci'] = round(overview['avg_fwci'], 2)

        # 2. 전임교원 수 (per capita) - 공시자료 우선, 없으면 author 테이블
        faculty_count = None
        try:
            cursor.execute("SELECT metric_value FROM institution_metrics WHERE metric_key = 'full_time_faculty' ORDER BY metric_year DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                faculty_count = int(row[0])
        except Exception:
            pass
        if not faculty_count:
            cursor.execute("SELECT COUNT(*) FROM author WHERE primary_affiliation LIKE ?", (f'%{affiliation}%',))
            faculty_count = cursor.fetchone()[0]
            overview['faculty_source'] = 'author_table'
        else:
            overview['faculty_source'] = 'disclosure'
        overview['author_count'] = faculty_count
        overview['per_capita_pubs'] = round(total / faculty_count, 1) if faculty_count > 0 else 0
        overview['per_capita_citations'] = round(overview['total_citations'] / faculty_count, 1) if faculty_count > 0 else 0

        # 3. 국제협력 국가 분포
        cursor.execute(f"""
            SELECT country_region FROM publication
            WHERE is_international = 1 AND country_region IS NOT NULL AND country_region != ''
            {year_filter}
        """, year_params)
        country_counts = {}
        for r in cursor.fetchall():
            countries = r[0].replace('|', ';').split(';')
            for c in countries:
                c = c.strip()
                if c and c != '-':
                    country_counts[c] = country_counts.get(c, 0) + 1
        # 자기 국가 제외, 상위 15개
        country_counts.pop('South Korea', None)
        country_counts.pop('Korea', None)
        top_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:15]

        # 3-1. 데이터 최대 연도 (ARWU 기준연도 산정용)
        cursor.execute("SELECT MAX(CAST(year AS INTEGER)) FROM publication WHERE year IS NOT NULL")
        max_data_year = cursor.fetchone()[0] or (datetime.now().year - 1)

        # 4. 연도별 추이
        cursor.execute("""
            SELECT
                CAST(year AS INTEGER) as yr,
                COUNT(*) as pubs,
                COALESCE(SUM(CAST(citations AS REAL)), 0) as citations,
                COALESCE(AVG(CAST(field_weighted_citation_impact AS REAL)), 0) as avg_fwci,
                SUM(CASE WHEN is_international = 1 THEN 1 ELSE 0 END) as intl,
                SUM(CASE WHEN is_10 = 1 THEN 1 ELSE 0 END) as top10,
                SUM(CASE WHEN is_25 = 1 THEN 1 ELSE 0 END) as top25,
                SUM(CASE WHEN open_access IS NOT NULL AND open_access != '' AND open_access != '-' THEN 1 ELSE 0 END) as oa,
                SUM(CASE WHEN is_SDG = 1 THEN 1 ELSE 0 END) as sdg,
                SUM(CASE WHEN is_patent_cited = 1 THEN 1 ELSE 0 END) as patent_cited
            FROM publication
            WHERE year IS NOT NULL AND CAST(year AS INTEGER) > 2000
            GROUP BY yr ORDER BY yr
        """)
        trends = {'years': [], 'pubs': [], 'citations': [], 'avg_fwci': [],
                  'intl_rate': [], 'top10_rate': [], 'top25_rate': [], 'oa_rate': [],
                  'citations_per_paper': []}
        for r in cursor.fetchall():
            yr_pubs = r['pubs'] or 1
            trends['years'].append(r['yr'])
            trends['pubs'].append(r['pubs'])
            trends['citations'].append(round(r['citations'], 0))
            trends['avg_fwci'].append(round(r['avg_fwci'], 2))
            trends['intl_rate'].append(round(r['intl'] / yr_pubs * 100, 1))
            trends['top10_rate'].append(round(r['top10'] / yr_pubs * 100, 1))
            trends['top25_rate'].append(round(r['top25'] / yr_pubs * 100, 1))
            trends['oa_rate'].append(round(r['oa'] / yr_pubs * 100, 1))
            trends['citations_per_paper'].append(round(r['citations'] / yr_pubs, 2))

        # 5. 대학공시 지표 조회
        inst_metrics = {}
        try:
            cursor.execute("SELECT metric_key, metric_value, metric_unit FROM institution_metrics ORDER BY metric_year DESC")
            for r in cursor.fetchall():
                if r['metric_key'] not in inst_metrics:
                    inst_metrics[r['metric_key']] = {'value': r['metric_value'], 'unit': r['metric_unit']}
            # 비율 자동 계산 (별도 파일에서 교원수/학생수가 따로 들어온 경우)
            if 'international_faculty' in inst_metrics and 'full_time_faculty' in inst_metrics and 'international_faculty_ratio' not in inst_metrics:
                ratio = round(inst_metrics['international_faculty']['value'] / max(1, inst_metrics['full_time_faculty']['value']) * 100, 1)
                inst_metrics['international_faculty_ratio'] = {'value': ratio, 'unit': '%'}
            if 'international_students' in inst_metrics and 'total_students' in inst_metrics and 'international_student_ratio' not in inst_metrics:
                ratio = round(inst_metrics['international_students']['value'] / max(1, inst_metrics['total_students']['value']) * 100, 1)
                inst_metrics['international_student_ratio'] = {'value': ratio, 'unit': '%'}
        except Exception:
            pass

        conn.close()

        return jsonify({
            'overview': overview,
            'max_data_year': max_data_year,
            'institution_metrics': inst_metrics,
            'qs': {
                'citations_per_paper': overview['avg_citations'],
                'intl_collab_rate': overview['intl_rate'],
                'unique_countries': len(country_counts),
                'top_countries': [{'country': c, 'count': n} for c, n in top_countries]
            },
            'the': {
                'research_productivity': overview['per_capita_pubs'],
                'citation_impact_fwci': overview['avg_fwci'],
                'intl_outlook': overview['intl_rate'],
                'industry_proxy': {
                    'patent_cited_count': overview['patent_cited_count'],
                    'patent_cited_rate': overview['patent_cited_rate'],
                    'corporate_count': overview['corporate_count'],
                    'corporate_rate': overview['corporate_rate']
                }
            },
            'arwu': {
                'top1_count': overview['top1_count'],
                'top1_rate': overview['top1_rate'],
                'total_pubs': overview['total_pubs'],
                'author_count': faculty_count,
                'per_capita_output': overview['per_capita_pubs'],
                'per_capita_citations': overview['per_capita_citations']
            },
            'trends': trends
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/strategic_field_config')
def api_strategic_field_config():
    """연구분야 키워드 설정 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, category, subcategory, keywords, display_order
        FROM strategic_field_config
        ORDER BY category, display_order
    """)
    rows = cursor.fetchall()
    conn.close()

    # 카테고리별로 그룹화
    config = {}
    for row in rows:
        cat = row['category']
        if cat not in config:
            config[cat] = []
        config[cat].append({
            'id': row['id'],
            'subcategory': row['subcategory'],
            'keywords': json.loads(row['keywords']) if row['keywords'] else [],
            'display_order': row['display_order']
        })

    return jsonify(config)


@app.route('/api/strategic_field_config', methods=['POST'])
def api_strategic_field_config_save():
    """연구분야 키워드 설정 저장"""
    data = request.get_json()
    action = data.get('action')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if action == 'add_subcategory':
            # 새 집중분석 분야 추가
            category = data.get('category')
            subcategory = data.get('subcategory')
            keywords = json.dumps(data.get('keywords', []))

            # display_order 계산
            cursor.execute("""
                SELECT COALESCE(MAX(display_order), 0) + 1 FROM strategic_field_config
                WHERE category = ?
            """, (category,))
            display_order = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO strategic_field_config (category, subcategory, keywords, display_order)
                VALUES (?, ?, ?, ?)
            """, (category, subcategory, keywords, display_order))
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'id': new_id})

        elif action == 'update_keywords':
            # 키워드 업데이트
            config_id = data.get('id')
            keywords = json.dumps(data.get('keywords', []))

            cursor.execute("""
                UPDATE strategic_field_config
                SET keywords = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (keywords, config_id))
            conn.commit()
            conn.close()
            return jsonify({'success': True})

        elif action == 'delete_subcategory':
            # 집중분석 분야 삭제
            config_id = data.get('id')
            cursor.execute("DELETE FROM strategic_field_config WHERE id = ?", (config_id,))
            conn.commit()
            conn.close()
            return jsonify({'success': True})

        elif action == 'rename_subcategory':
            # 집중분석 분야 이름 변경
            config_id = data.get('id')
            new_name = data.get('subcategory')
            cursor.execute("""
                UPDATE strategic_field_config
                SET subcategory = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_name, config_id))
            conn.commit()
            conn.close()
            return jsonify({'success': True})

        else:
            conn.close()
            return jsonify({'success': False, 'error': 'Unknown action'}), 400

    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/translate_keyword', methods=['POST'])
def api_translate_keyword():
    """한글 키워드를 영어로 번역"""
    data = request.get_json()
    keyword = data.get('keyword', '').strip()

    if not keyword:
        return jsonify({'success': False, 'error': 'No keyword provided'})

    # 한글이 포함되어 있는지 확인
    import re
    has_korean = bool(re.search('[가-힣]', keyword))

    if not has_korean:
        # 영어면 그대로 반환
        return jsonify({'success': True, 'original': keyword, 'translated': keyword, 'is_korean': False})

    try:
        translator = GoogleTranslator(source='ko', target='en')
        translated = translator.translate(keyword)
        return jsonify({
            'success': True,
            'original': keyword,
            'translated': translated.lower(),
            'is_korean': True
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/strategic_field_keyword_suggestions')
def api_strategic_field_keyword_suggestions():
    """연구분야 키워드 추천 API - 해당 분야 논문에서 핫한 키워드 추출"""
    category = request.args.get('category')
    subcategory = request.args.get('subcategory')
    limit = request.args.get('limit', 10, type=int)

    if not category or not subcategory:
        return jsonify({'suggestions': [], 'error': 'category and subcategory required'})

    conn = get_db_connection()
    cursor = conn.cursor()

    # 해당 분야의 기존 키워드 조회
    cursor.execute("""
        SELECT keywords FROM strategic_field_config
        WHERE category = ? AND subcategory = ?
    """, (category, subcategory))
    row = cursor.fetchone()

    if not row or not row['keywords']:
        conn.close()
        return jsonify({'suggestions': [], 'message': 'No existing keywords'})

    # JSON 배열 또는 쉼표 구분 문자열 처리
    keywords_raw = row['keywords']
    if keywords_raw.startswith('['):
        existing_keywords = [k.lower() for k in json.loads(keywords_raw)]
    else:
        existing_keywords = [k.strip().lower() for k in keywords_raw.split(',') if k.strip()]

    # 기존 키워드로 논문 검색 (최근 5년)
    keyword_conditions = ' OR '.join(['LOWER(title) LIKE ?' for _ in existing_keywords])
    params = [f'%{kw}%' for kw in existing_keywords]

    cursor.execute(f"""
        SELECT title FROM publication
        WHERE ({keyword_conditions})
        AND CAST(year AS INTEGER) >= 2020
        LIMIT 1000
    """, params)

    titles = [row['title'] for row in cursor.fetchall()]
    conn.close()

    if not titles:
        return jsonify({'suggestions': [], 'message': 'No papers found'})

    # 불용어 정의
    stopwords = {
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has', 'had',
        'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
        'its', 'it', 'this', 'that', 'these', 'those', 'their', 'them', 'they', 'we', 'our',
        'i', 'you', 'he', 'she', 'his', 'her', 'my', 'your', 'can', 'into', 'through',
        'during', 'before', 'after', 'above', 'below', 'between', 'under', 'over', 'up',
        'down', 'out', 'off', 'about', 'than', 'such', 'only', 'other', 'new', 'used',
        'using', 'based', 'study', 'analysis', 'effect', 'effects', 'approach', 'method',
        'methods', 'results', 'research', 'application', 'applications', 'high', 'low',
        'different', 'various', 'novel', 'enhanced', 'improved', 'efficient', 'proposed',
        'paper', 'work', 'properties', 'performance', 'system', 'systems', 'development',
        'via', 'use', 'two', 'one', 'three', 'first', 'second', 'also', 'however', 'both',
        'each', 'all', 'some', 'any', 'more', 'most', 'very', 'well', 'much', 'many',
        'no', 'not', 'when', 'where', 'which', 'who', 'how', 'what', 'why', 'if', 'then'
    }

    # 제목에서 단어 추출 및 빈도 계산
    import re
    from collections import Counter

    word_counter = Counter()
    bigram_counter = Counter()

    for title in titles:
        # 단어 추출 (영문만, 소문자 변환)
        words = re.findall(r'[a-zA-Z]{3,}', title.lower())
        # 불용어 및 기존 키워드 제외
        filtered_words = [w for w in words if w not in stopwords and w not in existing_keywords]
        word_counter.update(filtered_words)

        # 바이그램(2단어 조합) 추출
        for i in range(len(filtered_words) - 1):
            bigram = f"{filtered_words[i]} {filtered_words[i+1]}"
            bigram_counter.update([bigram])

    # 단일 키워드 상위 추천
    top_words = word_counter.most_common(limit * 2)
    # 바이그램 상위 추천 (빈도 3 이상)
    top_bigrams = [(bg, cnt) for bg, cnt in bigram_counter.most_common(limit) if cnt >= 3]

    suggestions = []

    # 바이그램 우선 추가
    for bigram, count in top_bigrams[:limit // 2]:
        suggestions.append({
            'keyword': bigram,
            'count': count,
            'type': 'phrase'
        })

    # 단일 키워드 추가
    for word, count in top_words:
        if len(suggestions) >= limit:
            break
        # 이미 바이그램에 포함된 단어는 제외
        if not any(word in s['keyword'] for s in suggestions):
            suggestions.append({
                'keyword': word,
                'count': count,
                'type': 'word'
            })

    return jsonify({
        'category': category,
        'subcategory': subcategory,
        'total_papers_analyzed': len(titles),
        'suggestions': suggestions[:limit]
    })


@app.route('/api/strategic_field_analysis')
def api_strategic_field_analysis():
    """연구분야 분석 API"""
    category = request.args.get('category')
    subcategory = request.args.get('subcategory')
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)

    conn = get_db_connection()
    cursor = conn.cursor()

    # 해당 분야의 키워드 조회
    if subcategory:
        cursor.execute("""
            SELECT keywords FROM strategic_field_config
            WHERE category = ? AND subcategory = ?
        """, (category, subcategory))
    else:
        cursor.execute("""
            SELECT keywords FROM strategic_field_config
            WHERE category = ?
        """, (category,))

    rows = cursor.fetchall()
    all_keywords = []
    for row in rows:
        if row['keywords']:
            all_keywords.extend(json.loads(row['keywords']))

    if not all_keywords:
        conn.close()
        return jsonify({
            'category': category,
            'subcategory': subcategory,
            'total_papers': 0,
            'total_citations': 0,
            'avg_fwci': 0,
            'researcher_count': 0,
            'researchers': [],
            'yearly_trend': []
        })

    # 키워드로 논문 검색 (title에서 LIKE 검색)
    keyword_conditions = " OR ".join(["title LIKE ?"] * len(all_keywords))
    keyword_params = [f"%{kw}%" for kw in all_keywords]

    # 연도 조건
    year_condition = ""
    if year_from and year_to:
        year_condition = f" AND CAST(year AS INTEGER) BETWEEN {year_from} AND {year_to}"

    # 논문 통계
    query = f"""
        SELECT
            COUNT(*) as total_papers,
            SUM(CAST(citations AS INTEGER)) as total_citations,
            AVG(CAST(field_weighted_citation_impact AS REAL)) as avg_fwci
        FROM publication
        WHERE ({keyword_conditions}) {year_condition}
    """
    cursor.execute(query, keyword_params)
    stats = cursor.fetchone()

    total_papers = stats['total_papers'] or 0
    total_citations = stats['total_citations'] or 0
    avg_fwci = round(stats['avg_fwci'] or 0, 2)

    # 연구자별 집계
    query = f"""
        SELECT
            scopus_author_ids,
            COUNT(*) as paper_count,
            SUM(CAST(citations AS INTEGER)) as citations,
            AVG(CAST(field_weighted_citation_impact AS REAL)) as avg_fwci
        FROM publication
        WHERE ({keyword_conditions}) {year_condition}
        AND scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
        GROUP BY scopus_author_ids
        ORDER BY paper_count DESC
    """
    cursor.execute(query, keyword_params)
    pub_rows = cursor.fetchall()

    # 연구자 정보 수집 (scopus_author_ids가 여러 명일 수 있으므로 분해)
    # 형식: "57211432707| 55317946600" (파이프와 공백으로 구분)
    researcher_stats = {}
    for row in pub_rows:
        author_ids = row['scopus_author_ids'].split('|') if row['scopus_author_ids'] else []
        for aid in author_ids:
            aid = aid.strip()
            if not aid:
                continue
            if aid not in researcher_stats:
                researcher_stats[aid] = {'paper_count': 0, 'citations': 0, 'fwci_sum': 0, 'fwci_count': 0}
            researcher_stats[aid]['paper_count'] += 1
            researcher_stats[aid]['citations'] += row['citations'] or 0
            if row['avg_fwci']:
                researcher_stats[aid]['fwci_sum'] += row['avg_fwci']
                researcher_stats[aid]['fwci_count'] += 1

    # 전북대 소속 연구자만 필터링 (author 테이블에 있는 연구자)
    all_author_ids = list(researcher_stats.keys())
    jbnu_author_ids = set()
    if all_author_ids:
        # 1000개씩 나누어 조회 (SQLite 변수 제한)
        for i in range(0, len(all_author_ids), 1000):
            batch = all_author_ids[i:i+1000]
            placeholders = ','.join(['?'] * len(batch))
            cursor.execute(f"SELECT scopus_author_id FROM author WHERE scopus_author_id IN ({placeholders})", batch)
            jbnu_author_ids.update(r['scopus_author_id'] for r in cursor.fetchall())

    # 전북대 소속 연구자만 남기기
    jbnu_researcher_stats = {aid: stats for aid, stats in researcher_stats.items() if aid in jbnu_author_ids}

    # 상위 연구자 정보 가져오기
    top_author_ids = sorted(jbnu_researcher_stats.keys(), key=lambda x: jbnu_researcher_stats[x]['paper_count'], reverse=True)[:50]

    researchers = []
    if top_author_ids:
        placeholders = ','.join(['?'] * len(top_author_ids))
        cursor.execute(f"""
            SELECT scopus_author_id, name, h_index, scholarly_output, citations as total_citations, orcid
            FROM author
            WHERE scopus_author_id IN ({placeholders})
        """, top_author_ids)
        author_info = {r['scopus_author_id']: dict(r) for r in cursor.fetchall()}

        for aid in top_author_ids:
            stats_data = jbnu_researcher_stats[aid]
            info = author_info.get(aid, {})
            avg_fwci_val = stats_data['fwci_sum'] / stats_data['fwci_count'] if stats_data['fwci_count'] > 0 else 0
            researchers.append({
                'scopus_author_id': aid,
                'name': info.get('name', 'Unknown'),
                'paper_count': stats_data['paper_count'],
                'citations': stats_data['citations'],
                'avg_fwci': round(avg_fwci_val, 2),
                'h_index': info.get('h_index', 0),
                'total_papers': info.get('scholarly_output', 0),
                'orcid': info.get('orcid', '')
            })

    # 연도별 추이
    query = f"""
        SELECT
            year,
            COUNT(*) as paper_count,
            SUM(CAST(citations AS INTEGER)) as citations,
            AVG(CAST(field_weighted_citation_impact AS REAL)) as avg_fwci
        FROM publication
        WHERE ({keyword_conditions}) {year_condition}
        AND year IS NOT NULL AND year != ''
        GROUP BY year
        ORDER BY year
    """
    cursor.execute(query, keyword_params)
    trend_rows = cursor.fetchall()

    yearly_trend = []
    for row in trend_rows:
        try:
            year_val = int(float(row['year']))
            yearly_trend.append({
                'year': year_val,
                'paper_count': row['paper_count'],
                'citations': row['citations'] or 0,
                'avg_fwci': round(row['avg_fwci'] or 0, 2)
            })
        except (ValueError, TypeError):
            continue

    conn.close()

    return jsonify({
        'category': category,
        'subcategory': subcategory,
        'keywords_used': all_keywords,
        'total_papers': total_papers,
        'total_citations': total_citations,
        'avg_fwci': avg_fwci,
        'researcher_count': len(jbnu_researcher_stats),
        'researcher_ids': list(jbnu_researcher_stats.keys()),  # 분야 연구자 ID 목록
        'researchers': researchers,
        'yearly_trend': yearly_trend
    })


@app.route('/api/strategic_field_ranking', methods=['GET', 'POST'])
def api_strategic_field_ranking():
    """연구분야별 연구자 랭킹 API"""
    # POST 요청 시 JSON body에서, GET 요청 시 query params에서 데이터 읽기
    if request.method == 'POST':
        data = request.get_json() or {}
        researcher_ids = data.get('researcher_ids', '')
    else:
        researcher_ids = request.args.get('researcher_ids', '')

    if not researcher_ids:
        return jsonify({'count': 0, 'researchers': []})

    ids_list = [rid.strip() for rid in researcher_ids.split(',') if rid.strip()]
    if not ids_list:
        return jsonify({'count': 0, 'researchers': []})

    fwci_method = request.args.get('fwci_method', 'median')

    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ','.join(['?'] * len(ids_list))

    if fwci_method == 'mean':
        order_col = 'COALESCE(rs.score_total_mean, 0)'
        fwci_col = 'fwci_mean'
    else:
        order_col = 'COALESCE(rs.score_total_median, 0)'
        fwci_col = 'fwci_median'

    # author 테이블 기준 LEFT JOIN으로 모든 연구자 포함
    cursor.execute(f"""
        SELECT a.scopus_author_id, a.name, a.orcid, a.scholarly_output, a.citations,
               a.field_weighted_citation_impact, a.h_index,
               rs.fwci_mean, rs.fwci_median,
               rs.score_fwci_mean, rs.score_fwci_median,
               rs.score_core_mean, rs.score_core_median,
               rs.score_total_mean, rs.score_total_median,
               rs.score_top_cited, rs.score_top_journal, rs.score_intl_collab,
               rs.score_sdg, rs.score_oa, rs.score_prominence, rs.score_secondary,
               rs.top_journal_pct, rs.has_sdg, rs.has_oa
        FROM author a
        LEFT JOIN researcher_score rs ON a.scopus_author_id = rs.scopus_author_id
        WHERE a.scopus_author_id IN ({placeholders})
        ORDER BY {order_col} DESC, a.field_weighted_citation_impact DESC
    """, ids_list)

    rows = cursor.fetchall()
    conn.close()

    results = []
    for idx, row in enumerate(rows):
        row_dict = dict(row)
        if fwci_method == 'mean':
            fwci_val = row_dict.get('fwci_mean') or row_dict.get('field_weighted_citation_impact') or 0
            score_fwci = row_dict.get('score_fwci_mean', 0) or 0
            score_core = row_dict.get('score_core_mean', 0) or 0
            score_total = row_dict.get('score_total_mean', 0) or 0
        else:
            fwci_val = row_dict.get('fwci_median') or row_dict.get('field_weighted_citation_impact') or 0
            score_fwci = row_dict.get('score_fwci_median', 0) or 0
            score_core = row_dict.get('score_core_median', 0) or 0
            score_total = row_dict.get('score_total_median', 0) or 0

        results.append({
            'rank': idx + 1,
            'scopus_author_id': row_dict['scopus_author_id'],
            'name': row_dict['name'],
            'orcid': row_dict.get('orcid', ''),
            'scholarly_output': row_dict.get('scholarly_output', 0) or 0,
            'citations': row_dict.get('citations', 0) or 0,
            'fwci': round(fwci_val, 2),
            'h_index': row_dict.get('h_index', 0) or 0,
            'score_fwci': score_fwci,
            'score_top_cited': row_dict.get('score_top_cited', 0) or 0,
            'score_top_journal': row_dict.get('score_top_journal', 0) or 0,
            'score_intl_collab': row_dict.get('score_intl_collab', 0) or 0,
            'score_core': score_core,
            'score_sdg': row_dict.get('score_sdg', 0) or 0,
            'score_oa': row_dict.get('score_oa', 0) or 0,
            'score_prominence': row_dict.get('score_prominence', 0) or 0,
            'score_secondary': row_dict.get('score_secondary', 0) or 0,
            'score_total': score_total,
            'top_journal_pct': row_dict.get('top_journal_pct', 0) or 0,
            'has_sdg': row_dict.get('has_sdg', 0) or 0,
            'has_oa': row_dict.get('has_oa', 0) or 0
        })

    return jsonify({
        'count': len(results),
        'fwci_method': fwci_method,
        'researchers': results
    })


@app.route('/api/strategic_field_modules', methods=['GET', 'POST'])
def api_strategic_field_modules():
    """연구분야별 분석 모듈 API (잠재력/고피인용/협력)"""
    # POST 요청 시 JSON body에서, GET 요청 시 query params에서 데이터 읽기
    if request.method == 'POST':
        data = request.get_json() or {}
        researcher_ids = data.get('researcher_ids', '')
        module_type = data.get('module_type', 'potential')
    else:
        researcher_ids = request.args.get('researcher_ids', '')
        module_type = request.args.get('module_type', 'potential')

    if not researcher_ids:
        return jsonify({'count': 0, 'researchers': []})

    ids_list = [rid.strip() for rid in researcher_ids.split(',') if rid.strip()]
    if not ids_list:
        return jsonify({'count': 0, 'researchers': []})

    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ','.join(['?'] * len(ids_list))

    if module_type == 'potential':
        # 잠재력 연구자: 최근 3년 논문수 증가, 젊은 연구자
        cursor.execute(f"""
            SELECT a.scopus_author_id, a.name, a.orcid, a.scholarly_output, a.citations,
                   a.field_weighted_citation_impact as fwci, a.h_index,
                   a.most_recent_publication, a.oldest_publication
            FROM author a
            WHERE a.scopus_author_id IN ({placeholders})
            ORDER BY a.field_weighted_citation_impact DESC
        """, ids_list)

    elif module_type == 'citation':
        # 고피인용 잠재력: FWCI 높고 최근 활동적
        cursor.execute(f"""
            SELECT a.scopus_author_id, a.name, a.orcid, a.scholarly_output, a.citations,
                   a.field_weighted_citation_impact as fwci, a.h_index,
                   a.output_in_top_10_percentile as top_10_pct
            FROM author a
            WHERE a.scopus_author_id IN ({placeholders})
            ORDER BY a.field_weighted_citation_impact DESC
        """, ids_list)

    else:  # collaboration
        # 협력 분석: 국제협력 비율
        cursor.execute(f"""
            SELECT a.scopus_author_id, a.name, a.orcid, a.scholarly_output, a.citations,
                   a.field_weighted_citation_impact as fwci, a.h_index,
                   rs.intl_collab_count, rs.intl_collab_fwci
            FROM author a
            LEFT JOIN researcher_score rs ON a.scopus_author_id = rs.scopus_author_id
            WHERE a.scopus_author_id IN ({placeholders})
            ORDER BY rs.intl_collab_count DESC
        """, ids_list)

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        row_dict = dict(row)
        result = {
            'scopus_author_id': row_dict['scopus_author_id'],
            'name': row_dict['name'],
            'orcid': row_dict.get('orcid', ''),
            'scholarly_output': row_dict.get('scholarly_output', 0),
            'citations': row_dict.get('citations', 0),
            'fwci': round(row_dict.get('fwci', 0) or 0, 2),
            'h_index': row_dict.get('h_index', 0)
        }

        if module_type == 'potential':
            career_years = (row_dict.get('most_recent_publication', 2025) or 2025) - (row_dict.get('oldest_publication', 2020) or 2020) + 1
            result['career_years'] = career_years
        elif module_type == 'citation':
            result['top_10_pct'] = row_dict.get('top_10_pct', 0)
        else:
            intl_count = row_dict.get('intl_collab_count', 0) or 0
            total = row_dict.get('scholarly_output', 1) or 1
            result['intl_collab_count'] = intl_count
            result['intl_collab_ratio'] = round(intl_count / total * 100, 1) if total > 0 else 0
            result['intl_collab_fwci'] = round(row_dict.get('intl_collab_fwci', 0) or 0, 2)

        results.append(result)

    return jsonify({
        'count': len(results),
        'module_type': module_type,
        'researchers': results
    })


@app.route('/api/strategic_field_strategy', methods=['GET', 'POST'])
def api_strategic_field_strategy():
    """연구분야별 연구 전략 API (성장궤적/사회적기여/분야전략)"""
    # POST 요청 시 JSON body에서, GET 요청 시 query params에서 데이터 읽기
    if request.method == 'POST':
        data = request.get_json() or {}
        researcher_ids = data.get('researcher_ids', '')
        strategy_type = data.get('strategy_type', 'trajectory')
    else:
        researcher_ids = request.args.get('researcher_ids', '')
        strategy_type = request.args.get('strategy_type', 'trajectory')

    if not researcher_ids:
        return jsonify({'count': 0, 'researchers': []})

    ids_list = [rid.strip() for rid in researcher_ids.split(',') if rid.strip()]
    if not ids_list:
        return jsonify({'count': 0, 'researchers': []})

    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ','.join(['?'] * len(ids_list))

    if strategy_type == 'trajectory':
        # 성장궤적: 연속 성장 연구자
        cursor.execute(f"""
            SELECT a.scopus_author_id, a.name, a.orcid, a.scholarly_output, a.citations,
                   a.field_weighted_citation_impact as fwci, a.h_index,
                   a.most_recent_publication, a.oldest_publication
            FROM author a
            WHERE a.scopus_author_id IN ({placeholders})
            ORDER BY a.field_weighted_citation_impact DESC
        """, ids_list)

    elif strategy_type == 'societal':
        # 사회적 기여: SDG, OA 논문 편수 (한번 스캔으로 집계)
        # 먼저 publication 스캔 (author 쿼리 전에)
        target_ids = set(ids_list)
        societal_counts = {sid: {'sdg_count': 0, 'oa_count': 0, 'total': 0} for sid in ids_list}

        cursor.execute("""
            SELECT scopus_author_ids, is_SDG, open_access
            FROM publication
            WHERE scopus_author_ids IS NOT NULL AND scopus_author_ids != ''
        """)
        for pub in cursor.fetchall():
            pub_author_ids = [aid.strip() for aid in pub['scopus_author_ids'].replace(';', '|').split('|') if aid.strip()]
            is_sdg = pub['is_SDG'] == 1
            is_oa = pub['open_access'] is not None and pub['open_access'] != '' and pub['open_access'] != '-'
            for aid in pub_author_ids:
                if aid in target_ids:
                    societal_counts[aid]['total'] += 1
                    if is_sdg:
                        societal_counts[aid]['sdg_count'] += 1
                    if is_oa:
                        societal_counts[aid]['oa_count'] += 1

        # author 쿼리 (publication 스캔 후에)
        cursor.execute(f"""
            SELECT a.scopus_author_id, a.name, a.orcid, a.scholarly_output, a.citations,
                   a.field_weighted_citation_impact as fwci, a.h_index
            FROM author a
            WHERE a.scopus_author_id IN ({placeholders})
        """, ids_list)

    else:  # field
        # 분야전략: 상위저널 비율
        cursor.execute(f"""
            SELECT a.scopus_author_id, a.name, a.orcid, a.scholarly_output, a.citations,
                   a.field_weighted_citation_impact as fwci, a.h_index,
                   rs.top_journal_pct
            FROM author a
            LEFT JOIN researcher_score rs ON a.scopus_author_id = rs.scopus_author_id
            WHERE a.scopus_author_id IN ({placeholders})
            ORDER BY rs.top_journal_pct DESC
        """, ids_list)

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        row_dict = dict(row)
        result = {
            'scopus_author_id': row_dict['scopus_author_id'],
            'name': row_dict['name'],
            'orcid': row_dict.get('orcid', ''),
            'scholarly_output': row_dict.get('scholarly_output', 0),
            'citations': row_dict.get('citations', 0),
            'fwci': round(row_dict.get('fwci', 0) or 0, 2),
            'h_index': row_dict.get('h_index', 0)
        }

        if strategy_type == 'trajectory':
            career_years = (row_dict.get('most_recent_publication', 2025) or 2025) - (row_dict.get('oldest_publication', 2020) or 2020) + 1
            result['career_years'] = career_years
        elif strategy_type == 'societal':
            sc = societal_counts.get(row_dict['scopus_author_id'], {'sdg_count': 0, 'oa_count': 0, 'total': 0})
            result['sdg_count'] = sc['sdg_count']
            result['oa_count'] = sc['oa_count']
            result['sdg_rate'] = round(sc['sdg_count'] / max(1, sc['total']) * 100, 1)
            result['oa_rate'] = round(sc['oa_count'] / max(1, sc['total']) * 100, 1)
        else:
            result['top_journal_pct'] = round(row_dict.get('top_journal_pct', 0) or 0, 1)

        results.append(result)

    return jsonify({
        'count': len(results),
        'strategy_type': strategy_type,
        'researchers': results
    })


@app.route('/api/strategic_field_collaborators')
def api_strategic_field_collaborators():
    """
    전략분야별 기관 간 공동연구자 API
    - 전북대와 고려대 연구자 간의 공동 저자 관계를 분석
    - 키워드 기반 논문 검색
    """
    import sqlite3 as sqlite3_module

    category = request.args.get('category', '')
    subcategory = request.args.get('subcategory', '')
    year_from = request.args.get('year_from')
    year_to = request.args.get('year_to')

    if not category or not subcategory:
        return jsonify({'count': 0, 'collaborators': []})

    # 두 DB 모두 열기 (원본 파일 사용)
    import os as os_module
    import json as json_module
    base_dir = os_module.path.dirname(os_module.path.abspath(__file__))
    jbnu_db_path = os_module.path.join(base_dir, 'jbnu.db')
    korea_db_path = os_module.path.join(base_dir, 'korea.db')

    # 해당 분야의 키워드 조회 (jbnu.db에서 - 설정 테이블이 여기에만 있음)
    jbnu_config_conn = sqlite3_module.connect(jbnu_db_path)
    jbnu_config_conn.row_factory = sqlite3_module.Row
    config_cursor = jbnu_config_conn.cursor()

    config_cursor.execute("""
        SELECT keywords FROM strategic_field_config
        WHERE category = ? AND subcategory = ?
    """, (category, subcategory))

    row = config_cursor.fetchone()
    jbnu_config_conn.close()

    if not row or not row['keywords']:
        return jsonify({'count': 0, 'collaborators': [], 'message': '키워드 설정이 없습니다.'})

    # 키워드 파싱 (JSON 배열 또는 쉼표 구분)
    keywords_str = row['keywords']
    try:
        keywords = json_module.loads(keywords_str)
        if isinstance(keywords, list):
            keywords = [kw.strip().lower() for kw in keywords if kw.strip()]
        else:
            keywords = [keywords_str.strip().lower()]
    except (json_module.JSONDecodeError, TypeError):
        keywords = [kw.strip().lower() for kw in keywords_str.split(',') if kw.strip()]
    if not keywords:
        return jsonify({'count': 0, 'collaborators': [], 'message': '키워드가 없습니다.'})

    try:
        jbnu_conn = sqlite3_module.connect(jbnu_db_path)
        jbnu_conn.row_factory = sqlite3_module.Row
        jbnu_cursor = jbnu_conn.cursor()

        korea_conn = sqlite3_module.connect(korea_db_path)
        korea_conn.row_factory = sqlite3_module.Row
        korea_cursor = korea_conn.cursor()
    except Exception as e:
        return jsonify({'count': 0, 'collaborators': [], 'error': f'DB 연결 실패: {str(e)}'})

    # 전북대 연구자 목록 (scopus_author_id -> name)
    jbnu_cursor.execute("SELECT scopus_author_id, name FROM author WHERE scopus_author_id IS NOT NULL")
    jbnu_authors = {row['scopus_author_id']: row['name'] for row in jbnu_cursor.fetchall()}

    # 고려대 연구자 목록 (scopus_author_id -> name)
    korea_cursor.execute("SELECT scopus_author_id, name FROM author WHERE scopus_author_id IS NOT NULL AND primary_affiliation = 'Korea University'")
    korea_authors = {row['scopus_author_id']: row['name'] for row in korea_cursor.fetchall()}

    # 연도 조건
    year_condition = ""
    if year_from and year_to:
        year_condition = f"AND CAST(year AS INTEGER) >= {int(year_from)} AND CAST(year AS INTEGER) <= {int(year_to)}"

    # 전북대 논문에서 키워드 매칭 후 공동저자 찾기
    collaborations = {}  # (jbnu_id, korea_id) -> {pub_count, eids}

    jbnu_cursor.execute(f"""
        SELECT eid, title, scopus_author_ids
        FROM publication
        WHERE scopus_author_ids IS NOT NULL
              AND title IS NOT NULL
              {year_condition}
    """)

    for pub in jbnu_cursor.fetchall():
        title_lower = (pub['title'] or '').lower()

        # 키워드 매칭 확인
        matched = any(kw in title_lower for kw in keywords)
        if not matched:
            continue

        # 저자 ID 파싱 (파이프 또는 세미콜론으로 구분)
        raw_ids = (pub['scopus_author_ids'] or '').replace(';', '|')
        author_ids = [a.strip() for a in raw_ids.split('|') if a.strip()]

        # 전북대 저자와 고려대 저자 식별
        jbnu_in_pub = [aid for aid in author_ids if aid in jbnu_authors]
        korea_in_pub = [aid for aid in author_ids if aid in korea_authors and aid not in jbnu_authors]

        # 공동 저자 쌍 기록 (같은 사람 제외)
        for jbnu_id in jbnu_in_pub:
            for korea_id in korea_in_pub:
                if jbnu_id == korea_id:
                    continue
                key = (jbnu_id, korea_id)
                if key not in collaborations:
                    collaborations[key] = {
                        'jbnu_id': jbnu_id,
                        'jbnu_name': jbnu_authors.get(jbnu_id, 'Unknown'),
                        'korea_id': korea_id,
                        'korea_name': korea_authors.get(korea_id, 'Unknown'),
                        'eids': set()
                    }
                collaborations[key]['eids'].add(pub['eid'])

    jbnu_conn.close()
    korea_conn.close()

    # 결과 정리
    result = []
    for key, collab in collaborations.items():
        result.append({
            'jbnu_id': collab['jbnu_id'],
            'jbnu_name': collab['jbnu_name'],
            'korea_id': collab['korea_id'],
            'korea_name': collab['korea_name'],
            'pub_count': len(collab['eids']),
            'jbnu_profile': f"https://www.scopus.com/authid/detail.uri?authorId={collab['jbnu_id']}",
            'korea_profile': f"https://www.scopus.com/authid/detail.uri?authorId={collab['korea_id']}"
        })

    # 논문 수 기준 내림차순 정렬
    result.sort(key=lambda x: (-x['pub_count'], x['jbnu_name']))

    return jsonify({
        'count': len(result),
        'category': category,
        'subcategory': subcategory,
        'keywords': keywords,
        'collaborators': result
    })


# ========================================
# 관리자 기능
# ========================================

@app.route('/admin')
@admin_required
def admin_users():
    """사용자 관리 페이지"""
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    user_role = session.get('user_role')
    user_institution = session.get('institution')

    if user_role == 'admin':
        # 슈퍼관리자: 모든 사용자 조회
        cursor.execute('SELECT * FROM users ORDER BY id')
    else:
        # 기관관리자: 같은 기관 사용자만 조회
        cursor.execute('SELECT * FROM users WHERE institution = ? ORDER BY id', (user_institution,))

    users = cursor.fetchall()
    conn.close()

    # 기관관리자는 자신의 기관만 선택 가능
    if user_role == 'admin':
        available_institutions = INSTITUTION_NAMES
    else:
        available_institutions = {user_institution: INSTITUTION_NAMES.get(user_institution, user_institution)}

    return render_template('admin_users.html',
                           users=users,
                           institutions=INSTITUTION_NAMES,
                           available_institutions=available_institutions,
                           is_super_admin=(user_role == 'admin'))


@app.route('/admin/user/add', methods=['POST'])
@admin_required
def admin_add_user():
    """사용자 추가"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    name = request.form.get('name', '').strip()
    department = request.form.get('department', '').strip() or None
    job_description = request.form.get('job_description', '').strip() or None
    institution = request.form.get('institution', '').strip() or None
    role = request.form.get('role', 'user')

    user_role = session.get('user_role')
    user_institution = session.get('institution')

    # 기관관리자는 자신의 기관 사용자만 추가 가능
    if user_role != 'admin':
        institution = user_institution
        # 기관관리자는 슈퍼관리자나 다른 기관관리자 생성 불가
        if role == 'admin':
            role = 'user'

    if not username or not password or not name:
        flash('아이디, 비밀번호, 이름은 필수입니다.')
        return redirect(url_for('admin_users'))

    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()

    # 중복 체크
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    if cursor.fetchone():
        conn.close()
        flash('이미 존재하는 아이디입니다.')
        return redirect(url_for('admin_users'))

    cursor.execute(
        'INSERT INTO users (username, password, name, department, job_description, institution, role) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (username, password, name, department, job_description, institution, role)
    )
    conn.commit()
    conn.close()
    flash(f'사용자 "{name}"({username})가 추가되었습니다.')
    return redirect(url_for('admin_users'))


@app.route('/admin/user/<int:user_id>/edit', methods=['POST'])
@admin_required
def admin_edit_user(user_id):
    """사용자 수정"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    name = request.form.get('name', '').strip()
    department = request.form.get('department', '').strip() or None
    job_description = request.form.get('job_description', '').strip() or None
    institution = request.form.get('institution', '').strip() or None
    role = request.form.get('role', 'user')

    user_role = session.get('user_role')
    user_institution = session.get('institution')

    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 기관관리자 권한 체크
    if user_role != 'admin':
        # 수정하려는 사용자가 같은 기관인지 확인
        cursor.execute('SELECT institution FROM users WHERE id = ?', (user_id,))
        target_user = cursor.fetchone()
        if not target_user or target_user['institution'] != user_institution:
            conn.close()
            flash('권한이 없습니다.')
            return redirect(url_for('admin_users'))
        # 기관관리자는 기관 변경 불가, 슈퍼관리자 생성 불가
        institution = user_institution
        if role == 'admin':
            role = 'user'

    if not username or not password or not name:
        flash('아이디, 비밀번호, 이름은 필수입니다.')
        conn.close()
        return redirect(url_for('admin_users'))

    # 다른 사용자와 중복 체크
    cursor.execute('SELECT id FROM users WHERE username = ? AND id != ?', (username, user_id))
    if cursor.fetchone():
        conn.close()
        flash('이미 존재하는 아이디입니다.')
        return redirect(url_for('admin_users'))

    cursor.execute(
        'UPDATE users SET username = ?, password = ?, name = ?, department = ?, job_description = ?, institution = ?, role = ? WHERE id = ?',
        (username, password, name, department, job_description, institution, role, user_id)
    )
    conn.commit()
    conn.close()
    flash(f'사용자 "{name}"({username})가 수정되었습니다.')
    return redirect(url_for('admin_users'))


@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    """사용자 삭제"""
    user_role = session.get('user_role')
    user_institution = session.get('institution')

    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 삭제 전 사용자 정보 조회
    cursor.execute('SELECT username, role, institution FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        flash('사용자를 찾을 수 없습니다.')
        return redirect(url_for('admin_users'))

    # 기관관리자 권한 체크
    if user_role != 'admin':
        if user['institution'] != user_institution:
            conn.close()
            flash('권한이 없습니다.')
            return redirect(url_for('admin_users'))

    if user['role'] == 'admin':
        # 마지막 슈퍼관리자인지 확인
        cursor.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
        admin_count = cursor.fetchone()[0]
        if admin_count <= 1:
            conn.close()
            flash('최소 1명의 슈퍼관리자가 필요합니다.')
            return redirect(url_for('admin_users'))

    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

    if user:
        flash(f'사용자 "{user[0]}"가 삭제되었습니다.')
    return redirect(url_for('admin_users'))


# ========================================
# 활동 대시보드
# ========================================

@app.route('/admin/dashboard')
@super_admin_required
def admin_dashboard():
    """활동 대시보드 (슈퍼관리자 전용)"""
    log_activity('페이지 조회', '활동 대시보드')

    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 오늘 활동 수
    cursor.execute('''
        SELECT COUNT(*) FROM activity_logs
        WHERE DATE(created_at) = DATE('now', 'localtime')
    ''')
    today_count = cursor.fetchone()[0]

    # 이번 주 활동 수
    cursor.execute('''
        SELECT COUNT(*) FROM activity_logs
        WHERE DATE(created_at) >= DATE('now', '-7 days', 'localtime')
    ''')
    week_count = cursor.fetchone()[0]

    # 활성 사용자 수 (최근 7일)
    cursor.execute('''
        SELECT COUNT(DISTINCT username) FROM activity_logs
        WHERE DATE(created_at) >= DATE('now', '-7 days', 'localtime')
    ''')
    active_users = cursor.fetchone()[0]

    # 인기 메뉴 (최근 30일)
    cursor.execute('''
        SELECT action_detail, COUNT(*) as cnt
        FROM activity_logs
        WHERE action_type = '페이지 조회'
        AND DATE(created_at) >= DATE('now', '-30 days', 'localtime')
        GROUP BY action_detail
        ORDER BY cnt DESC
        LIMIT 10
    ''')
    popular_menus = cursor.fetchall()

    # 최근 활동 (최근 100건) - 기관, 이름 포함
    cursor.execute('''
        SELECT * FROM activity_logs
        ORDER BY created_at DESC
        LIMIT 100
    ''')
    recent_activities = cursor.fetchall()

    # 일별 활동 수 (최근 14일)
    cursor.execute('''
        SELECT DATE(created_at) as date, COUNT(*) as cnt
        FROM activity_logs
        WHERE DATE(created_at) >= DATE('now', '-14 days', 'localtime')
        GROUP BY DATE(created_at)
        ORDER BY date
    ''')
    daily_stats = [{'date': row['date'], 'cnt': row['cnt']} for row in cursor.fetchall()]

    # 사용자별 활동 수 (최근 30일)
    cursor.execute('''
        SELECT username, user_name, institution, COUNT(*) as cnt
        FROM activity_logs
        WHERE DATE(created_at) >= DATE('now', '-30 days', 'localtime')
        GROUP BY username
        ORDER BY cnt DESC
        LIMIT 20
    ''')
    user_stats = cursor.fetchall()

    # 다운로드 이력 (최근 30일)
    cursor.execute('''
        SELECT * FROM activity_logs
        WHERE action_type = '다운로드'
        AND DATE(created_at) >= DATE('now', '-30 days', 'localtime')
        ORDER BY created_at DESC
        LIMIT 50
    ''')
    downloads = cursor.fetchall()

    # 기관별 통계 (최근 30일)
    cursor.execute('''
        SELECT institution,
               COUNT(*) as total_activities,
               COUNT(DISTINCT username) as unique_users,
               SUM(CASE WHEN action_type = '다운로드' THEN 1 ELSE 0 END) as downloads,
               SUM(CASE WHEN action_type = '로그인' THEN 1 ELSE 0 END) as logins
        FROM activity_logs
        WHERE DATE(created_at) >= DATE('now', '-30 days', 'localtime')
        AND institution IS NOT NULL AND institution != ''
        GROUP BY institution
        ORDER BY total_activities DESC
    ''')
    institution_stats = [dict(row) for row in cursor.fetchall()]

    # 기관별 일별 활동 (비교용, 최근 14일)
    cursor.execute('''
        SELECT institution, DATE(created_at) as date, COUNT(*) as cnt
        FROM activity_logs
        WHERE DATE(created_at) >= DATE('now', '-14 days', 'localtime')
        AND institution IS NOT NULL AND institution != ''
        GROUP BY institution, DATE(created_at)
        ORDER BY institution, date
    ''')
    institution_daily = {}
    for row in cursor.fetchall():
        inst = row['institution']
        if inst not in institution_daily:
            institution_daily[inst] = []
        institution_daily[inst].append({'date': row['date'], 'cnt': row['cnt']})

    conn.close()

    return render_template('admin_dashboard.html',
                           today_count=today_count,
                           week_count=week_count,
                           active_users=active_users,
                           popular_menus=popular_menus,
                           recent_activities=recent_activities,
                           daily_stats=daily_stats,
                           user_stats=user_stats,
                           downloads=downloads,
                           institution_stats=institution_stats,
                           institution_daily=institution_daily)


@app.route('/api/log_tab_click', methods=['POST'])
@login_required
def api_log_tab_click():
    """탭 클릭 로깅 API"""
    try:
        data = request.get_json()
        page_name = data.get('page', '')
        tab_name = data.get('tab', '')

        if page_name and tab_name:
            log_activity('탭 클릭', f'{page_name} > {tab_name}')

        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/log_download', methods=['POST'])
@login_required
def api_log_download():
    """다운로드 로깅 API"""
    try:
        data = request.get_json()
        filename = data.get('filename', '')
        page_name = data.get('page', '')

        if filename:
            detail = f'{page_name} > {filename}' if page_name else filename
            log_activity('다운로드', detail)

        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/admin/activity_logs')
@admin_required
def api_activity_logs():
    """활동 로그 API"""
    user_role = session.get('user_role')
    user_institution = session.get('institution')

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    offset = (page - 1) * per_page

    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 기관 필터
    institution_filter = ""
    params = []
    if user_role != 'admin':
        institution_filter = "WHERE institution = ?"
        params = [user_institution]

    cursor.execute(f'''
        SELECT * FROM activity_logs
        {institution_filter}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    ''', params + [per_page, offset])
    logs = [dict(row) for row in cursor.fetchall()]

    cursor.execute(f'SELECT COUNT(*) FROM activity_logs {institution_filter}', params)
    total = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        'logs': logs,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    })


# ========================================
# 데이터 스냅샷 관리
# ========================================

def parse_disclosure_file(filepath, original_filename):
    """대학공시자료 엑셀 파일에서 핵심 지표 추출"""
    import unicodedata
    fname = unicodedata.normalize('NFC', original_filename)
    metrics = {}

    try:
        df = pd.read_excel(filepath, header=None)
    except Exception:
        return None

    # 기준연도 추출 (첫 행에서)
    year_str = str(df.iloc[0, 0]) if pd.notna(df.iloc[0, 0]) else ''
    metric_year = 2024  # 기본값
    import re
    year_match = re.search(r'(\d{4})년', year_str)
    if year_match:
        metric_year = int(year_match.group(1)) - 1  # 2025년 공시 = 2024년 기준

    if '전임교원 1인당 학생 수' in fname:
        # 합계 행 찾기
        for i in range(len(df)):
            if str(df.iloc[i, 0]).strip() == '합 계':
                vals = [v for v in df.iloc[i].values if pd.notna(v)]
                if len(vals) >= 13:
                    metrics['full_time_faculty'] = {'value': int(float(vals[7])), 'unit': '명'}
                    metrics['student_faculty_ratio'] = {'value': float(vals[12]), 'unit': '명/인'}
                    metrics['total_students'] = {'value': int(float(vals[6])), 'unit': '명'}  # 계 재학생(A')
                break

    elif '전공계열별 외국인 전임교원' in fname:
        for i in range(len(df)):
            if str(df.iloc[i, 0]).strip() == '합 계':
                vals = [v for v in df.iloc[i].values if pd.notna(v)]
                if len(vals) >= 2:
                    intl_faculty = int(float(vals[1])) + int(float(vals[2]))
                    metrics['international_faculty'] = {'value': intl_faculty, 'unit': '명'}
                break

    elif '외국학생 현황' in fname:
        for i in range(len(df)):
            if str(df.iloc[i, 0]).strip() == '합 계':
                vals = [v for v in df.iloc[i].values if pd.notna(v)]
                if len(vals) >= 2:
                    metrics['international_students'] = {'value': int(float(vals[1])), 'unit': '명'}
                break

    elif '재적 학생 현황' in fname:
        for i in range(len(df)):
            val0 = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ''
            if val0 in ('소계', '합 계') and i >= 5:
                vals = [v for v in df.iloc[i].values if pd.notna(v)]
                if len(vals) >= 2:
                    metrics['total_students_enrolled'] = {'value': int(float(vals[0])), 'unit': '명'}
                    if len(vals) >= 3:
                        metrics['enrolled_students'] = {'value': int(float(vals[-1])), 'unit': '명'}
                break

    elif '기술이전 수입료' in fname:
        for i in range(3, len(df)):
            vals = [v for v in df.iloc[i].values if pd.notna(v)]
            if len(vals) >= 4 and '전북대' in str(vals[1]) + str(vals[0]):
                metrics['tech_transfer_count'] = {'value': int(float(vals[2])), 'unit': '건'}
                metrics['tech_transfer_revenue'] = {'value': int(float(vals[3])), 'unit': '원'}
                break
            elif len(vals) >= 4:
                try:
                    metrics['tech_transfer_count'] = {'value': int(float(vals[2])), 'unit': '건'}
                    metrics['tech_transfer_revenue'] = {'value': int(float(vals[3])), 'unit': '원'}
                    break
                except (ValueError, TypeError):
                    continue

    elif '운영(손익) 계산서' in fname or '운영계산서' in fname:
        for i in range(len(df)):
            val0 = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ''
            val1 = df.iloc[i, 1] if len(df.columns) > 1 and pd.notna(df.iloc[i, 1]) else None
            if '산학협력수익' in val0 and val1 is not None:
                metrics['industry_revenue'] = {'value': int(float(str(val1).replace(',', ''))), 'unit': '원'}
            if ('운영수익총계' in val0 or '수익합계' in val0) and val1 is not None and 'total_revenue' not in metrics:
                metrics['total_revenue'] = {'value': int(float(str(val1).replace(',', ''))), 'unit': '원'}
            if val0 == '운영수익' and val1 is not None and 'total_revenue' not in metrics:
                metrics['total_revenue'] = {'value': int(float(str(val1).replace(',', ''))), 'unit': '원'}

    elif '연구비 수혜 실적' in fname:
        for i in range(len(df)):
            if str(df.iloc[i, 0]).strip() == '합 계':
                vals = [v for v in df.iloc[i].values if pd.notna(v)]
                if len(vals) >= 6:
                    try:
                        metrics['research_funding'] = {'value': int(float(vals[4])) + int(float(vals[5])), 'unit': '천원'}
                        metrics['research_funding_per_faculty'] = {'value': int(float(vals[-4])) + int(float(vals[-3])), 'unit': '천원'}
                    except (ValueError, TypeError, IndexError):
                        pass
                break

    elif '특허 출원 및 등록' in fname:
        for i in range(3, len(df)):
            vals = [v for v in df.iloc[i].values if pd.notna(v)]
            if len(vals) >= 6:
                try:
                    metrics['patent_domestic_filed'] = {'value': int(float(vals[2])), 'unit': '건'}
                    metrics['patent_domestic_granted'] = {'value': int(float(vals[3])), 'unit': '건'}
                    metrics['patent_intl_filed'] = {'value': int(float(vals[4])), 'unit': '건'}
                    metrics['patent_intl_granted'] = {'value': int(float(vals[5])), 'unit': '건'}
                    break
                except (ValueError, TypeError):
                    continue

    elif '졸업생의 취업 현황' in fname or '취업 현황' in fname:
        for i in range(len(df)):
            if str(df.iloc[i, 0]).strip() == '합계':
                vals = [v for v in df.iloc[i].values if pd.notna(v)]
                # 취업률 찾기
                for v in vals:
                    try:
                        fv = float(v)
                        if 10 < fv < 100:  # 취업률로 보이는 값
                            metrics['employment_rate'] = {'value': fv, 'unit': '%'}
                            break
                    except (ValueError, TypeError):
                        continue
                break

    if not metrics:
        return None

    # 비율 계산
    if 'international_faculty' in metrics and 'full_time_faculty' in metrics:
        ratio = round(metrics['international_faculty']['value'] / max(1, metrics['full_time_faculty']['value']) * 100, 1)
        metrics['international_faculty_ratio'] = {'value': ratio, 'unit': '%'}

    if 'international_students' in metrics and 'total_students' in metrics:
        ratio = round(metrics['international_students']['value'] / max(1, metrics['total_students']['value']) * 100, 1)
        metrics['international_student_ratio'] = {'value': ratio, 'unit': '%'}

    return {'year': metric_year, 'metrics': metrics}


def is_disclosure_file(filename):
    """대학공시자료 파일인지 판별"""
    import unicodedata
    normalized = unicodedata.normalize('NFC', filename)
    keywords = ['전임교원', '외국인 전임교원', '외국학생', '재적 학생', '기술이전',
                '운영(손익)', '운영계산서', '연구비 수혜', '특허 출원', '취업 현황',
                '전체 교원', '졸업생', '재무상태표', '대학회계', '발전기금', '직원 현황',
                '장서 보유', '성적 분포', '학점 교류', '예산서', '결산', '자금계산서']
    return any(kw in normalized for kw in keywords)


def detect_data_type_from_file(filepath, original_filename=''):
    """파일명 + CSV 1행 헤더로 데이터 유형 자동 감지"""
    # 1차: 파일명으로 판별
    f = original_filename.lower()
    if 'top_1_' in f or 'top_1%' in f or '_1__most_cited' in f:
        return '1%'
    if 'top_10_' in f or 'top_10%' in f or '_10__most_cited' in f or '_10__journals' in f:
        return '10%'
    if 'top_25_' in f or 'top_25%' in f or '_25__journals' in f:
        return '25%'
    if 'sdg' in f or 'sustainable_development' in f:
        return 'SDGs'
    if 'international_collaboration' in f or 'international_collab' in f:
        return 'International'
    if 'cited_by_patent' in f or 'patent_cit' in f:
        return 'patent'
    if 'cited_by_polic' in f or 'policy_cit' in f:
        return 'policy'
    if 'single_author' in f or 'coauthor' in f or 'co-author' in f:
        return 'coauthored'

    # 2차: CSV 1행(Data set 설명)으로 판별
    try:
        first_line = ''
        for enc in ['utf-8-sig', 'cp949']:
            try:
                with open(filepath, 'r', encoding=enc) as fh:
                    first_line = fh.readline().lower()
                break
            except Exception:
                continue

        if first_line:
            if 'top 1%' in first_line or 'top 1 %' in first_line:
                return '1%'
            if 'top 10%' in first_line or 'top 10 %' in first_line or '10% most cited' in first_line:
                return '10%'
            if 'top 25%' in first_line or 'top 25 %' in first_line:
                return '25%'
            if 'sdg' in first_line or 'sustainable development' in first_line:
                return 'SDGs'
            if 'international collaboration' in first_line:
                return 'International'
            if 'cited by patent' in first_line or 'patent' in first_line:
                return 'patent'
            if 'cited by polic' in first_line or 'policy' in first_line:
                return 'policy'
            if 'single author' in first_line or 'co-author' in first_line:
                return 'coauthored'
    except Exception:
        pass

    return '전체논문데이터'


# ========================================
# 기관 관리
# ========================================

@app.route('/admin/institutions')
@super_admin_required
def admin_institutions():
    """기관 관리 페이지"""
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    institutions = conn.execute("SELECT * FROM institutions ORDER BY id").fetchall()
    conn.close()
    return render_template('admin_institutions.html', institutions=[dict(i) for i in institutions])


@app.route('/api/institutions', methods=['POST'])
@super_admin_required
def api_add_institution():
    """새 기관 추가"""
    try:
        data = request.get_json()
        inst_key = data.get('inst_key', '').strip().lower()
        inst_name = data.get('inst_name', '').strip()
        affiliation = data.get('affiliation', '').strip()

        if not inst_key or not inst_name or not affiliation:
            return jsonify({'error': '기관 코드, 기관명, 영문 소속명은 필수입니다.'}), 400

        # 중복 체크
        conn = sqlite3.connect(USERS_DB)
        if conn.execute("SELECT id FROM institutions WHERE inst_key = ?", (inst_key,)).fetchone():
            conn.close()
            return jsonify({'error': '이미 존재하는 기관 코드입니다.'}), 400

        db_file = f'{inst_key}.db'
        conn.execute("INSERT INTO institutions (inst_key, inst_name, affiliation, db_file) VALUES (?, ?, ?, ?)",
                     (inst_key, inst_name, affiliation, db_file))
        conn.commit()
        conn.close()

        # DB 파일 생성 + 테이블 초기화
        init_institution_db(db_file)

        # 기관 정보 다시 로드
        reload_institutions()

        return jsonify({'success': True, 'inst_key': inst_key, 'db_file': db_file})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/institutions/<inst_key>/toggle', methods=['POST'])
@super_admin_required
def api_toggle_institution(inst_key):
    """기관 활성/비활성 토글"""
    try:
        conn = sqlite3.connect(USERS_DB)
        inst = conn.execute("SELECT * FROM institutions WHERE inst_key = ?", (inst_key,)).fetchone()
        if not inst:
            conn.close()
            return jsonify({'error': 'Institution not found'}), 404

        new_status = 0 if inst[5] == 1 else 1  # is_active 토글
        conn.execute("UPDATE institutions SET is_active = ? WHERE inst_key = ?", (new_status, inst_key))
        conn.commit()
        conn.close()

        reload_institutions()
        return jsonify({'success': True, 'is_active': new_status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def ensure_snapshot_tables(conn):
    """스냅샷 테이블이 없으면 생성"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_snapshot (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_name TEXT NOT NULL,
            description TEXT,
            collection_date TEXT NOT NULL,
            year_from INTEGER NOT NULL,
            year_to INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            applied_at TEXT,
            applied_by TEXT,
            total_publications INTEGER DEFAULT 0,
            total_authors INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            created_by TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS snapshot_files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            data_type TEXT NOT NULL DEFAULT 'publication',
            file_size INTEGER DEFAULT 0,
            record_count INTEGER DEFAULT 0,
            upload_date TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (snapshot_id) REFERENCES data_snapshot(snapshot_id)
        )
    """)
    # 기존 데이터가 있고 스냅샷이 없으면 초기 스냅샷 자동 생성
    cursor.execute("SELECT COUNT(*) FROM data_snapshot")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT COUNT(*) FROM publication")
        pub_count = cursor.fetchone()[0]
        if pub_count > 0:
            cursor.execute("SELECT COUNT(*) FROM author")
            author_count = cursor.fetchone()[0]
            cursor.execute("SELECT MIN(year), MAX(year) FROM publication WHERE year IS NOT NULL")
            year_row = cursor.fetchone()
            min_year = year_row[0] or 2020
            max_year = year_row[1] or 2026
            cursor.execute("""
                INSERT INTO data_snapshot (snapshot_name, description, collection_date, year_from, year_to,
                                           status, applied_at, total_publications, total_authors, created_by)
                VALUES (?, ?, datetime('now'), ?, ?, 'applied', datetime('now'), ?, ?, 'system')
            """, ('초기 데이터', '기존 데이터에서 자동 생성된 스냅샷', min_year, max_year, pub_count, author_count))
    conn.commit()


@app.route('/admin/snapshots')
@admin_required
def admin_snapshots():
    """데이터 스냅샷 관리 페이지"""
    log_activity('페이지 조회', '스냅샷 관리')
    conn = get_db_connection()
    ensure_snapshot_tables(conn)
    snapshots = conn.execute("""
        SELECT s.*, (SELECT COUNT(*) FROM snapshot_files WHERE snapshot_id = s.snapshot_id) as file_count
        FROM data_snapshot s ORDER BY s.created_at DESC
    """).fetchall()
    conn.close()
    return render_template('admin_snapshots.html', snapshots=[dict(s) for s in snapshots])


@app.route('/api/snapshots', methods=['POST'])
@admin_required
def api_create_snapshot():
    """새 스냅샷 생성"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        collection_date = data.get('collection_date', '')
        year_from = data.get('year_from', 2020)
        year_to = data.get('year_to', 2026)

        if not name or not collection_date:
            return jsonify({'error': '스냅샷명과 수집일은 필수입니다.'}), 400

        conn = get_db_connection()
        ensure_snapshot_tables(conn)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO data_snapshot (snapshot_name, description, collection_date, year_from, year_to, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, description, collection_date, year_from, year_to, session.get('user_id', 'admin')))
        snapshot_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # 스냅샷 파일 디렉토리 생성
        institution = session.get('institution', 'jbnu')
        snap_dir = os.path.join(app.config['SNAPSHOT_FOLDER'], institution, str(snapshot_id))
        os.makedirs(snap_dir, exist_ok=True)

        return jsonify({'success': True, 'snapshot_id': snapshot_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/snapshots/<int:snapshot_id>', methods=['GET'])
@admin_required
def api_get_snapshot(snapshot_id):
    """스냅샷 상세 정보"""
    conn = get_db_connection()
    snapshot = conn.execute("SELECT * FROM data_snapshot WHERE snapshot_id = ?", (snapshot_id,)).fetchone()
    if not snapshot:
        conn.close()
        return jsonify({'error': 'Snapshot not found'}), 404
    files = conn.execute("SELECT * FROM snapshot_files WHERE snapshot_id = ? ORDER BY upload_date", (snapshot_id,)).fetchall()
    conn.close()
    return jsonify({
        'snapshot': dict(snapshot),
        'files': [dict(f) for f in files]
    })


@app.route('/api/snapshots/<int:snapshot_id>/upload', methods=['POST'])
@admin_required
def api_snapshot_upload(snapshot_id):
    """스냅샷에 파일 업로드"""
    try:
        conn = get_db_connection()
        snapshot = conn.execute("SELECT * FROM data_snapshot WHERE snapshot_id = ?", (snapshot_id,)).fetchone()
        if not snapshot:
            conn.close()
            return jsonify({'error': 'Snapshot not found'}), 404
        file = request.files.get('file')
        if not file or not allowed_file(file.filename):
            conn.close()
            return jsonify({'error': '유효한 CSV/Excel 파일을 선택해주세요.'}), 400

        data_type = request.form.get('data_type', '').strip()
        institution = session.get('institution', 'jbnu')
        snap_dir = os.path.join(app.config['SNAPSHOT_FOLDER'], institution, str(snapshot_id))
        os.makedirs(snap_dir, exist_ok=True)

        # 파일 저장
        from werkzeug.utils import secure_filename
        import time
        safe_name = f"{int(time.time())}_{secure_filename(file.filename)}"
        filepath = os.path.join(snap_dir, safe_name)
        file.save(filepath)
        file_size = os.path.getsize(filepath)

        # 대학공시자료 파일 감지 (원본 파일명 + 확장자로 판별)
        original_name = file.filename
        disclosure_result = None
        is_xlsx = original_name.lower().endswith('.xlsx') or original_name.lower().endswith('.xls')
        if is_xlsx and is_disclosure_file(original_name):
            data_type = '대학공시자료'
            disclosure_result = parse_disclosure_file(filepath, file.filename)
            record_count = len(disclosure_result['metrics']) if disclosure_result else 0

            # 공시자료 지표를 institution_metrics에 저장
            if disclosure_result:
                cursor = conn.cursor()
                cursor.execute("""CREATE TABLE IF NOT EXISTS institution_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_year INTEGER NOT NULL, metric_key TEXT NOT NULL,
                    metric_value REAL, metric_unit TEXT,
                    source TEXT DEFAULT '대학공시',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(metric_year, metric_key))""")
                for key, val in disclosure_result['metrics'].items():
                    cursor.execute("""INSERT OR REPLACE INTO institution_metrics
                        (metric_year, metric_key, metric_value, metric_unit)
                        VALUES (?, ?, ?, ?)""",
                        (disclosure_result['year'], key, val['value'], val['unit']))
                conn.commit()
        else:
            # 논문 데이터 유형 자동 감지
            if not data_type or data_type == '전체논문데이터':
                data_type = detect_data_type_from_file(filepath, file.filename)

            # 레코드 수 추정 (CSV 라인 수)
            record_count = 0
            try:
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    record_count = max(0, sum(1 for _ in f) - 20)
            except Exception:
                try:
                    with open(filepath, 'r', encoding='cp949') as f:
                        record_count = max(0, sum(1 for _ in f) - 20)
                except Exception:
                    pass

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO snapshot_files (snapshot_id, filename, original_filename, data_type, file_size, record_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (snapshot_id, safe_name, file.filename, data_type, file_size, record_count))
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'file_id': cursor.lastrowid,
            'filename': file.filename,
            'file_size': file_size,
            'record_count': record_count,
            'data_type': data_type,
            'disclosure_metrics': len(disclosure_result['metrics']) if disclosure_result else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/snapshots/<int:snapshot_id>/apply', methods=['POST'])
@admin_required
def api_apply_snapshot(snapshot_id):
    """스냅샷 적용 - 데이터 교체"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        snapshot = cursor.execute("SELECT * FROM data_snapshot WHERE snapshot_id = ?", (snapshot_id,)).fetchone()
        if not snapshot:
            conn.close()
            return jsonify({'error': 'Snapshot not found'}), 404

        files = cursor.execute("SELECT * FROM snapshot_files WHERE snapshot_id = ?", (snapshot_id,)).fetchall()
        if not files:
            conn.close()
            return jsonify({'error': '업로드된 파일이 없습니다.'}), 400

        institution = session.get('institution', 'jbnu')
        snap_dir = os.path.join(app.config['SNAPSHOT_FOLDER'], institution, str(snapshot_id))

        # 1. 기존 적용 스냅샷 → archived
        cursor.execute("UPDATE data_snapshot SET status = 'archived' WHERE status = 'applied'")

        # 2. 기존 데이터 삭제
        cursor.execute("DELETE FROM publication")
        cursor.execute("DELETE FROM researcher_score")
        conn.commit()

        # 3. 스냅샷 파일들을 순차 처리 (전체논문데이터 먼저, 플래그 파일 나중에)
        total_insert = 0
        total_update = 0
        total_skipped = 0

        type_flags = {
            '전체논문데이터': {},
            '1%': {'is_1': 1},
            '10%': {'is_10': 1},
            '25%': {'is_25': 1},
            'SDGs': {'is_SDG': 1},
            'International': {'is_international': 1},
            'patent': {'is_patent_cited': 1},
            'policy': {'is_policy_cited': 1},
            'coauthored': {'is_coauthored': 1},
        }

        # 전체논문데이터를 먼저, 나머지(플래그) 파일을 나중에 처리
        sorted_files = sorted(files, key=lambda x: 0 if x['data_type'] == '전체논문데이터' else 1)

        for sf in sorted_files:
            filepath = os.path.join(snap_dir, sf['filename'])
            if not os.path.exists(filepath):
                continue

            data_type = sf['data_type']
            flags = type_flags.get(data_type, {})

            # 파일 읽기
            df = None
            for enc in ['utf-8-sig', 'cp949']:
                try:
                    df = pd.read_csv(filepath, encoding=enc, header=19, low_memory=False)
                    break
                except Exception:
                    continue
            if df is None:
                try:
                    df = pd.read_excel(filepath, header=19)
                except Exception:
                    continue

            if len(df.columns) < 60:
                total_skipped += 1
                continue

            # 컬럼 매핑
            if len(df.columns) >= 70:
                column_order = COLUMN_ORDER_70
            else:
                column_order = COLUMN_ORDER_67
            df.columns = column_order[:len(df.columns)]

            # EID/DOI 인덱스 구축 (한번에 로드)
            if data_type != '전체논문데이터' and flags:
                # 플래그 파일: EID 기반 일괄 업데이트
                eids = df['eid'].dropna().astype(str).str.strip().tolist()
                eids = [e for e in eids if e]
                dois = df['doi'].dropna().astype(str).str.strip().tolist()
                dois = [d for d in dois if d]

                if eids:
                    for flag_col in flags.keys():
                        # 배치 업데이트 (500개씩)
                        for i in range(0, len(eids), 500):
                            batch = eids[i:i+500]
                            placeholders = ','.join(['?' for _ in batch])
                            cursor.execute(f"UPDATE publication SET {flag_col} = 1 WHERE eid IN ({placeholders})", batch)

                if dois:
                    for flag_col in flags.keys():
                        for i in range(0, len(dois), 500):
                            batch = dois[i:i+500]
                            placeholders = ','.join(['?' for _ in batch])
                            cursor.execute(f"UPDATE publication SET {flag_col} = 1 WHERE doi IN ({placeholders}) AND doi != ''", batch)

                total_update += len(eids) + len(dois)
                conn.commit()
                continue

            # 전체논문데이터: 배치 INSERT
            # 기존 EID 세트 로드
            existing_eids = set()
            for row in cursor.execute("SELECT eid FROM publication WHERE eid IS NOT NULL AND eid != ''"):
                existing_eids.add(row[0])
            existing_dois = set()
            for row in cursor.execute("SELECT doi FROM publication WHERE doi IS NOT NULL AND doi != ''"):
                existing_dois.add(row[0])

            batch_rows = []
            for _, row in df.iterrows():
                eid = str(row.get('eid', '')).strip() if pd.notna(row.get('eid')) else ''
                doi = str(row.get('doi', '')).strip() if pd.notna(row.get('doi')) else ''

                if not eid and not doi:
                    continue

                # 메모리 기반 중복 체크 (DB 쿼리 없음)
                if eid and eid in existing_eids:
                    total_update += 1
                    continue
                if doi and doi in existing_dois:
                    total_update += 1
                    continue

                values = {}
                for col in column_order[:len(df.columns)]:
                    val = row.get(col)
                    if pd.notna(val):
                        values[col] = str(val).strip() if isinstance(val, str) else val
                    else:
                        values[col] = None

                batch_rows.append(values)
                if eid:
                    existing_eids.add(eid)
                if doi:
                    existing_dois.add(doi)

            # 배치 INSERT (1000건씩)
            if batch_rows:
                cols = list(batch_rows[0].keys())
                col_names = ', '.join(cols)
                placeholders = ', '.join(['?' for _ in cols])
                for i in range(0, len(batch_rows), 1000):
                    batch = batch_rows[i:i+1000]
                    cursor.executemany(
                        f"INSERT INTO publication ({col_names}) VALUES ({placeholders})",
                        [[r.get(c) for c in cols] for r in batch]
                    )
                total_insert += len(batch_rows)

            conn.commit()

        # 3-1. SDG 플래그 보정: SDG 파일이 요약 파일인 경우 컬럼 데이터로 세팅
        cursor.execute("""UPDATE publication SET is_SDG = 1
            WHERE sustainable_development_goals_2025 IS NOT NULL
            AND sustainable_development_goals_2025 != ''
            AND sustainable_development_goals_2025 != '-'
            AND (is_SDG IS NULL OR is_SDG = 0)""")

        # 3-2. 산학협력 플래그 보정: sector 컬럼에 Corporate 포함 시 세팅
        cursor.execute("""UPDATE publication SET is_academic_corporate = 1
            WHERE sector LIKE '%Corporate%'
            AND (is_academic_corporate IS NULL OR is_academic_corporate = 0)""")

        # 3-3. Top 1% 피인용 플래그 보정
        cursor.execute("""UPDATE publication SET is_1 = 1
            WHERE outputs_in_top_citation_percentiles_per_percentile IS NOT NULL
            AND CAST(outputs_in_top_citation_percentiles_per_percentile AS REAL) <= 1
            AND (is_1 IS NULL OR is_1 = 0)""")

        # 3-3b. Top 10% 피인용 플래그 보정
        cursor.execute("""UPDATE publication SET is_10 = 1
            WHERE outputs_in_top_citation_percentiles_per_percentile IS NOT NULL
            AND CAST(outputs_in_top_citation_percentiles_per_percentile AS REAL) <= 10
            AND (is_10 IS NULL OR is_10 = 0)""")

        # 3-4. Top 25% 저널 플래그 보정: CiteScore percentile <= 25
        cursor.execute("""UPDATE publication SET is_25 = 1
            WHERE citescore_percentile_publication_year IS NOT NULL
            AND citescore_percentile_publication_year != ''
            AND CAST(citescore_percentile_publication_year AS REAL) <= 25
            AND (is_25 IS NULL OR is_25 = 0)""")

        # 3-5. 국제협력 플래그 보정
        cursor.execute("""UPDATE publication SET is_international = 1
            WHERE country_region IS NOT NULL AND country_region != ''
            AND country_region != 'South Korea' AND country_region != '-'
            AND country_region LIKE '%|%'
            AND (is_international IS NULL OR is_international = 0)""")

        # 3-6. 특허인용 플래그 보정: main_patent_families > 0
        cursor.execute("""UPDATE publication SET is_patent_cited = 1
            WHERE main_patent_families IS NOT NULL
            AND CAST(main_patent_families AS REAL) > 0
            AND (is_patent_cited IS NULL OR is_patent_cited = 0)""")

        # 3-7. 정책인용 플래그 보정: policy_citations > 0
        cursor.execute("""UPDATE publication SET is_policy_cited = 1
            WHERE policy_citations IS NOT NULL
            AND CAST(policy_citations AS REAL) > 0
            AND (is_policy_cited IS NULL OR is_policy_cited = 0)""")

        conn.commit()

        # 4. 논문/저자 수 집계
        cursor.execute("SELECT COUNT(*) FROM publication")
        pub_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM author")
        author_count = cursor.fetchone()[0]

        # 5. 스냅샷 상태 업데이트
        cursor.execute("""
            UPDATE data_snapshot SET status = 'applied', applied_at = datetime('now'),
                   applied_by = ?, total_publications = ?, total_authors = ?
            WHERE snapshot_id = ?
        """, (session.get('user_id', 'admin'), pub_count, author_count, snapshot_id))
        conn.commit()

        # 6. 연구자 점수 재계산
        try:
            batch_calculate_researcher_scores()
        except Exception as e:
            print(f"Score recalculation warning: {e}")

        conn.close()

        return jsonify({
            'success': True,
            'total_publications': pub_count,
            'total_authors': author_count,
            'inserted': total_insert,
            'updated': total_update
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/snapshots/<int:snapshot_id>/delete', methods=['POST'])
@admin_required
def api_delete_snapshot(snapshot_id):
    """스냅샷 삭제 (draft/archived만)"""
    try:
        conn = get_db_connection()
        snapshot = conn.execute("SELECT * FROM data_snapshot WHERE snapshot_id = ?", (snapshot_id,)).fetchone()
        if not snapshot:
            conn.close()
            return jsonify({'error': 'Snapshot not found'}), 404
        if snapshot['status'] == 'applied':
            conn.close()
            return jsonify({'error': '현재 적용 중인 스냅샷은 삭제할 수 없습니다.'}), 400

        # 파일 삭제
        institution = session.get('institution', 'jbnu')
        snap_dir = os.path.join(app.config['SNAPSHOT_FOLDER'], institution, str(snapshot_id))
        import shutil
        if os.path.exists(snap_dir):
            shutil.rmtree(snap_dir)

        cursor = conn.cursor()
        cursor.execute("DELETE FROM snapshot_files WHERE snapshot_id = ?", (snapshot_id,))
        cursor.execute("DELETE FROM data_snapshot WHERE snapshot_id = ?", (snapshot_id,))
        conn.commit()
        conn.close()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/snapshots/<int:snapshot_id>/file/<int:file_id>/delete', methods=['POST'])
@admin_required
def api_delete_snapshot_file(snapshot_id, file_id):
    """스냅샷 파일 개별 삭제"""
    try:
        conn = get_db_connection()
        sf = conn.execute("SELECT * FROM snapshot_files WHERE file_id = ? AND snapshot_id = ?", (file_id, snapshot_id)).fetchone()
        if not sf:
            conn.close()
            return jsonify({'error': 'File not found'}), 404

        institution = session.get('institution', 'jbnu')
        filepath = os.path.join(app.config['SNAPSHOT_FOLDER'], institution, str(snapshot_id), sf['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)

        conn.execute("DELETE FROM snapshot_files WHERE file_id = ?", (file_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/snapshot/active')
@login_required
def api_active_snapshot():
    """현재 활성 스냅샷 정보"""
    try:
        conn = get_db_connection()
        snapshot = conn.execute(
            "SELECT * FROM data_snapshot WHERE status = 'applied' LIMIT 1"
        ).fetchone()
        conn.close()
        return jsonify({'snapshot': dict(snapshot) if snapshot else None})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 57769))
    print(f"Starting Flask app on port {port}")
    app.run(debug=True, host='0.0.0.0', port=port)