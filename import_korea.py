#!/usr/bin/env python3
"""
고려대학교 rawdata001 폴더의 CSV 파일을 korea.db로 import하는 스크립트
- 2015-2024년 전체 논문 데이터
- 분류별 CSV로 불리언 플래그 설정
- 저자 데이터 import
- EID 기반 전역 중복 체크
"""

import sqlite3
import pandas as pd
import os
import sys
import time

DB_PATH = 'korea.db'
RAWDATA_DIR = 'rawdata001'

# 70컬럼 CSV → DB 컬럼 매핑 (위치 기반)
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

# 불리언 플래그 skip 키
ALL_FLAGS = [
    'is_paper', 'is_1', 'is_10', 'is_25', 'is_SDG', 'is_international',
    'is_top_cited', 'is_funded', 'is_national_collab', 'is_institutional_collab',
    'is_single_author', 'is_academic_only', 'is_academic_corporate',
    'is_academic_government', 'is_academic_medical',
    'is_patent_cited', 'is_policy_cited', 'is_coauthored'
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_database():
    """데이터베이스 및 테이블 생성"""
    conn = get_connection()
    cursor = conn.cursor()

    # publication 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS publication (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER DEFAULT 5,
            title TEXT,
            authors TEXT,
            number_of_authors TEXT,
            scopus_author_ids TEXT,
            year TEXT,
            full_date TEXT,
            scopus_source_title TEXT,
            volume TEXT,
            issue TEXT,
            pages TEXT,
            article_number TEXT,
            issn TEXT,
            source_id TEXT,
            source_type TEXT,
            publisher TEXT,
            language TEXT,
            snip_publication_year TEXT,
            snip_percentile_publication_year TEXT,
            citescore_publication_year TEXT,
            citescore_percentile_publication_year TEXT,
            sjr_publication_year TEXT,
            sjr_percentile_publication_year TEXT,
            field_weighted_view_impact TEXT,
            views TEXT,
            citations TEXT,
            field_weighted_citation_impact TEXT,
            field_citation_average TEXT,
            outputs_in_top_citation_percentiles_per_percentile TEXT,
            field_weighted_outputs_in_top_citation_percentiles_per_percentile TEXT,
            main_patent_families TEXT,
            policy_citations TEXT,
            reference TEXT,
            abstract TEXT,
            doi TEXT,
            publication_type TEXT,
            open_access TEXT,
            eid TEXT UNIQUE,
            pubmed_id TEXT,
            institutions TEXT,
            institution_ids TEXT,
            sector TEXT,
            number_of_institutions TEXT,
            scopus_affiliation_ids TEXT,
            scopus_affiliation_names TEXT,
            scopus_author_id_first_author TEXT,
            scopus_author_id_last_author TEXT,
            scopus_author_id_corresponding_author TEXT,
            scopus_author_id_single_author TEXT,
            country_region TEXT,
            number_of_countries_regions TEXT,
            all_science_journal_classification_asjc_code TEXT,
            all_science_journal_classification_asjc_field_name TEXT,
            quacquarelli_symonds_qs_subject_area_code TEXT,
            quacquarelli_symonds_qs_subject_area_field_name TEXT,
            quacquarelli_symonds_qs_subject_code TEXT,
            quacquarelli_symonds_qs_subject_field_name TEXT,
            times_higher_education_the_code TEXT,
            times_higher_education_the_field_name TEXT,
            anzsrc_for_2020_parent_code TEXT,
            anzsrc_for_2020_parent_name TEXT,
            anzsrc_for_2020_code TEXT,
            anzsrc_for_2020_name TEXT,
            sustainable_development_goals_2025 TEXT,
            topic_cluster_name TEXT,
            topic_cluster_number TEXT,
            topic_cluster_prominence_percentile TEXT,
            topic_name TEXT,
            topic_number TEXT,
            topic_prominence_percentile TEXT,
            publication_link_to_topic_strength TEXT,
            j_point REAL DEFAULT 0.0,
            a_point REAL DEFAULT 0.0,
            s_point REAL DEFAULT 0.0,
            t_point REAL DEFAULT 0.0,
            is_paper INTEGER DEFAULT 0,
            is_1 INTEGER DEFAULT 0,
            is_10 INTEGER DEFAULT 0,
            is_25 INTEGER DEFAULT 0,
            is_SDG INTEGER DEFAULT 0,
            is_international INTEGER DEFAULT 0,
            is_top_cited INTEGER DEFAULT 0,
            is_funded INTEGER DEFAULT 0,
            is_national_collab INTEGER DEFAULT 0,
            is_institutional_collab INTEGER DEFAULT 0,
            is_single_author INTEGER DEFAULT 0,
            is_academic_only INTEGER DEFAULT 0,
            is_academic_corporate INTEGER DEFAULT 0,
            is_academic_government INTEGER DEFAULT 0,
            is_academic_medical INTEGER DEFAULT 0,
            is_patent_cited INTEGER DEFAULT 0,
            is_policy_cited INTEGER DEFAULT 0,
            is_coauthored INTEGER DEFAULT 0
        )
    """)

    # author 테이블 생성
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

    # researcher_score 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS researcher_score (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scopus_author_id TEXT UNIQUE,
            scholarly_output INTEGER,
            citations INTEGER,
            h_index INTEGER,
            fwci_mean REAL,
            fwci_median REAL,
            top_journal_pct REAL,
            intl_collab_count INTEGER,
            intl_collab_fwci REAL,
            has_sdg INTEGER DEFAULT 0,
            has_oa INTEGER DEFAULT 0,
            score_fwci_mean REAL,
            score_fwci_median REAL,
            score_top_cited REAL,
            score_top_journal REAL,
            score_intl_collab REAL,
            score_core_mean REAL,
            score_core_median REAL,
            score_sdg REAL,
            score_oa REAL,
            score_prominence REAL,
            score_secondary REAL,
            score_total_mean REAL,
            score_total_median REAL,
            updated_at TEXT
        )
    """)

    # strategic_field_config 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategic_field_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL,
            keywords TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 기타 필요한 테이블들
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS room (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_name TEXT,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS survey_response (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            responses TEXT,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("  Database and tables created.")


def import_publication_csv(filepath, boolean_flags, room_id=5, full_update=False):
    """
    단일 Publication CSV 파일을 DB에 import.
    """
    print(f"  Loading: {os.path.basename(filepath)}")

    df = pd.read_csv(filepath, encoding='utf-8-sig', header=19,
                      keep_default_na=False, on_bad_lines='skip')
    df = df.dropna(how='all').reset_index(drop=True)

    num_cols = len(df.columns)
    if num_cols < 67:
        print(f"  WARNING: Only {num_cols} columns found, expected 67-70. Skipping.")
        return 0, 0, 0

    column_order = COLUMN_ORDER_70

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    total = len(df)
    insert_count = 0
    update_count = 0
    error_count = 0

    skip_keys = set(ALL_FLAGS) | {'room_id'}

    for idx, (_, row) in enumerate(df.iterrows()):
        try:
            if idx % 2000 == 0 and idx > 0:
                print(f"    {idx}/{total} processed...")
                conn.commit()

            # 매핑
            mapped_data = {}
            for i, db_col in enumerate(column_order):
                if i < num_cols:
                    value = row.iloc[i] if i < len(row) else None
                    if pd.isna(value):
                        value = None
                    elif isinstance(value, str):
                        value = value.strip() if value else None
                    mapped_data[db_col] = value

            mapped_data['room_id'] = room_id
            for flag_name in ALL_FLAGS:
                mapped_data[flag_name] = boolean_flags.get(flag_name, 0)

            # 빈 데이터 건너뛰기
            if not any(v for k, v in mapped_data.items() if k not in skip_keys):
                continue

            # EID 기반 중복 확인
            eid = mapped_data.get('eid', '')
            existing = None

            if eid and str(eid).strip():
                existing = cursor.execute(
                    'SELECT record_id FROM publication WHERE eid = ?',
                    (str(eid).strip(),)
                ).fetchone()
            else:
                doi = mapped_data.get('doi', '')
                if doi and str(doi).strip():
                    existing = cursor.execute(
                        'SELECT record_id FROM publication WHERE doi = ?',
                        (str(doi).strip(),)
                    ).fetchone()

            if existing:
                record_id = existing[0]
                update_parts = []

                if full_update:
                    for db_col in column_order:
                        if db_col in ('eid', 'doi'):
                            continue
                        val = mapped_data.get(db_col)
                        if val is not None:
                            update_parts.append((f"{db_col} = ?", val))

                update_parts.append(("room_id = ?", room_id))

                for flag_name in ALL_FLAGS:
                    new_val = boolean_flags.get(flag_name, 0)
                    if new_val == 1:
                        update_parts.append((f"{flag_name} = 1", None))

                set_clause_parts = []
                params = []
                for part, val in update_parts:
                    if val is not None:
                        set_clause_parts.append(part)
                        params.append(val)
                    else:
                        set_clause_parts.append(part)

                params.append(record_id)
                cursor.execute(
                    f"UPDATE publication SET {', '.join(set_clause_parts)} WHERE record_id = ?",
                    params
                )
                update_count += 1
            else:
                columns = list(mapped_data.keys())
                values = list(mapped_data.values())
                placeholders = ', '.join(['?' for _ in columns])
                column_names = ', '.join(columns)
                cursor.execute(
                    f'INSERT INTO publication ({column_names}) VALUES ({placeholders})',
                    values
                )
                insert_count += 1

        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"    Row {idx} error: {e}")

    conn.commit()
    conn.close()

    print(f"    Done: {insert_count} inserted, {update_count} updated, {error_count} errors (total: {total})")
    return insert_count, update_count, error_count


def import_authors_csv(filepath):
    """Authors CSV를 author 테이블에 import"""
    print(f"  Loading: {os.path.basename(filepath)}")

    df = pd.read_csv(filepath, encoding='utf-8-sig', header=11,
                      keep_default_na=False, on_bad_lines='skip')
    df = df.dropna(how='all').reset_index(drop=True)

    print(f"  {len(df)} author records found")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    insert_count = 0
    update_count = 0
    error_count = 0

    for idx, (_, row) in enumerate(df.iterrows()):
        try:
            name = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else None
            scholarly_output = int(row.iloc[1]) if not pd.isna(row.iloc[1]) and str(row.iloc[1]).strip() else None
            most_recent = int(row.iloc[2]) if not pd.isna(row.iloc[2]) and str(row.iloc[2]).strip() else None
            citations = int(row.iloc[3]) if not pd.isna(row.iloc[3]) and str(row.iloc[3]).strip() else None
            cpp = float(row.iloc[4]) if not pd.isna(row.iloc[4]) and str(row.iloc[4]).strip() else None
            fwci = float(row.iloc[5]) if not pd.isna(row.iloc[5]) and str(row.iloc[5]).strip() else None
            h_index = int(row.iloc[6]) if not pd.isna(row.iloc[6]) and str(row.iloc[6]).strip() else None
            top10 = int(row.iloc[7]) if not pd.isna(row.iloc[7]) and str(row.iloc[7]).strip() else None
            oldest = int(row.iloc[8]) if not pd.isna(row.iloc[8]) and str(row.iloc[8]).strip() else None
            scopus_id = str(row.iloc[9]).strip() if not pd.isna(row.iloc[9]) and str(row.iloc[9]).strip() else None
            profile_url = str(row.iloc[10]).strip() if not pd.isna(row.iloc[10]) and str(row.iloc[10]).strip() else None
            affiliation = str(row.iloc[11]).strip() if len(row) > 11 and not pd.isna(row.iloc[11]) and str(row.iloc[11]).strip() else None
            orcid = str(row.iloc[12]).strip() if len(row) > 12 and not pd.isna(row.iloc[12]) and str(row.iloc[12]).strip() else None

            if not name or not scopus_id:
                continue

            existing = cursor.execute(
                'SELECT author_id FROM author WHERE scopus_author_id = ?',
                (scopus_id,)
            ).fetchone()

            if existing:
                cursor.execute("""
                    UPDATE author SET name=?, scholarly_output=?, most_recent_publication=?,
                    citations=?, citations_per_publication=?, field_weighted_citation_impact=?, h_index=?,
                    output_in_top_10_percentile=?, oldest_publication=?, scopus_author_profile=?,
                    primary_affiliation=?, orcid=?
                    WHERE scopus_author_id=?
                """, (name, scholarly_output, most_recent, citations, cpp, fwci,
                      h_index, top10, oldest, profile_url, affiliation, orcid, scopus_id))
                update_count += 1
            else:
                cursor.execute("""
                    INSERT INTO author (name, scholarly_output, most_recent_publication,
                    citations, citations_per_publication, field_weighted_citation_impact, h_index,
                    output_in_top_10_percentile, oldest_publication, scopus_author_id,
                    scopus_author_profile, primary_affiliation, orcid)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, scholarly_output, most_recent, citations, cpp, fwci,
                      h_index, top10, oldest, scopus_id, profile_url, affiliation, orcid))
                insert_count += 1

        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"    Row {idx} error: {e}")

    conn.commit()
    conn.close()
    print(f"    Done: {insert_count} inserted, {update_count} updated, {error_count} errors")
    return insert_count, update_count, error_count


def main():
    start = time.time()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 60)
    print("Korea University Data Import Script")
    print("=" * 60)

    # 1. 데이터베이스 생성
    print("\n[1] Creating database...")
    create_database()

    # 2. 기존 데이터 상태 확인
    conn = sqlite3.connect(DB_PATH)
    before_count = conn.execute('SELECT COUNT(*) FROM publication').fetchone()[0]
    conn.close()
    print(f"\n  Current publication records: {before_count}")

    # 3. 메인 출판물 데이터 import
    print("\n[2] Importing main publication data (2015-2024)...")
    main_csv = os.path.join(RAWDATA_DIR, 'Publications_at_Korea_University_2015_-_2024.csv')
    if os.path.exists(main_csv):
        flags = {f: 0 for f in ALL_FLAGS}
        flags['is_paper'] = 1
        import_publication_csv(main_csv, flags, room_id=5, full_update=True)
    else:
        print(f"  ERROR: Main CSV not found: {main_csv}")
        return

    # 4. 분류별 CSV import
    print("\n[3] Importing categorized CSVs for boolean flags...")

    categorized_files = [
        ('Publications_at_Korea_University_that_fall_within_the_top_25__journals_by_CiteScore_2015_-_2024.csv', 'is_25'),
        ('Publications_at_Korea_University_with_international_collaboration_2015_-_2024.csv', 'is_international'),
        ('Publications_at_Korea_University_with_a_single_author_2015_-_2024.csv', 'is_single_author'),
        ('Publications_at_Korea_University_with_national_collaboration_2015_-_2024.csv', 'is_national_collab'),
        ('Publications_at_Korea_University_with_institutional_collaboration_2015_-_2024.csv', 'is_institutional_collab'),
        ('Publications_at_Korea_University_with_author_s__with_both_academic_and_corporate_affiliation_2015_-_2024.csv', 'is_academic_corporate'),
        ('Publications_at_Korea_University_without_author_s__with_both_academic_and_corporate_affiliation_2015_-_2024.csv', 'is_academic_only'),
        ('Scholarly_Output_cited_by_Patents_at_Korea_University_2015_-_2024.csv', 'is_patent_cited'),
        ('Scholarly_Output_cited_by_Policies_at_Korea_University_2015_-_2024.csv', 'is_policy_cited'),
    ]

    for filename, flag_name in categorized_files:
        filepath = os.path.join(RAWDATA_DIR, filename)
        if os.path.exists(filepath):
            flags = {f: 0 for f in ALL_FLAGS}
            flags[flag_name] = 1
            import_publication_csv(filepath, flags, room_id=5, full_update=False)
        else:
            print(f"  SKIP (not found): {filename}")

    # 5. 저자 데이터 import
    print("\n[4] Importing author data...")
    author_csv = os.path.join(RAWDATA_DIR, 'All_Authors_Korea+University_20260308.csv')
    if os.path.exists(author_csv):
        import_authors_csv(author_csv)
    else:
        print(f"  SKIP (not found): {author_csv}")

    # 6. 최종 상태 확인
    print("\n[5] Final verification...")
    conn = sqlite3.connect(DB_PATH)

    after_count = conn.execute('SELECT COUNT(*) FROM publication').fetchone()[0]
    print(f"  Publication records: {before_count} → {after_count} (net +{after_count - before_count})")

    print("\n  Year distribution:")
    rows = conn.execute('SELECT year, COUNT(*) FROM publication GROUP BY year ORDER BY year').fetchall()
    for r in rows:
        print(f"    {r[0]}: {r[1]} records")

    try:
        author_count = conn.execute('SELECT COUNT(*) FROM author').fetchone()[0]
        print(f"\n  Author records: {author_count}")
    except:
        pass

    conn.close()

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"Import completed in {elapsed:.1f} seconds")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
