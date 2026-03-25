#!/usr/bin/env python3
"""
고려대학교 연구자 점수 계산 스크립트
researcher_score 테이블에 점수 저장
"""

import sqlite3
import time

DB_PATH = 'korea.db'
AFFILIATION = 'Korea University'


def main():
    start = time.time()
    print("=" * 60)
    print("Korea University Researcher Score Calculation")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 점수 계산 함수들
    def calc_fwci_score(fwci):
        if fwci is None:
            return 10
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
        return 3 if has_sdg else 0

    def calc_oa_score(has_oa):
        return 2 if has_oa else 0

    def calc_prominence_score(prominence):
        if prominence is None:
            return 0
        return 5 if prominence >= 90 else 0

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

    # 1. 고려대 저자 목록 가져오기
    print(f"\n[1] Loading {AFFILIATION} authors...")
    cursor.execute("""
        SELECT author_id, scopus_author_id, name, scholarly_output, citations,
               field_weighted_citation_impact, h_index, output_in_top_10_percentile,
               primary_affiliation, scopus_author_profile
        FROM author
        WHERE primary_affiliation = ?
    """, (AFFILIATION,))
    authors = cursor.fetchall()
    print(f"    Found {len(authors)} authors")

    # 2. 논문 데이터 가져오기
    print("\n[2] Loading publication data...")
    cursor.execute("""
        SELECT scopus_author_ids, field_weighted_citation_impact, is_international, is_10,
               snip_percentile_publication_year, citescore_percentile_publication_year,
               sjr_percentile_publication_year, sustainable_development_goals_2025,
               open_access, topic_prominence_percentile
        FROM publication
    """)
    all_publications = cursor.fetchall()
    print(f"    Found {len(all_publications)} publications")

    # 저자별 논문 점수 수집
    print("\n[3] Calculating per-paper scores...")
    author_pub_scores = {}

    for pub in all_publications:
        scopus_ids_str = pub['scopus_author_ids'] or ''
        scopus_ids = [sid.strip() for sid in scopus_ids_str.replace('|', ' ').split() if sid.strip()]

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
    print("\n[4] Clearing old scores...")
    cursor.execute("DELETE FROM researcher_score")

    # 4. 저자별 점수 계산 및 저장
    print("\n[5] Calculating and saving researcher scores...")
    insert_count = 0

    for idx, author in enumerate(authors):
        if idx % 1000 == 0 and idx > 0:
            print(f"    {idx}/{len(authors)} processed...")
            conn.commit()

        scopus_id = author['scopus_author_id']
        pubs = author_pub_scores.get(scopus_id, [])

        if not pubs:
            continue

        # 각 점수 항목별 리스트 수집
        fwci_vals = [p['fwci_val'] for p in pubs if p['fwci_val'] is not None]
        fwci_scores = [p['fwci_score'] for p in pubs]
        top_cited_scores = [p['top_cited_score'] for p in pubs]
        top_journal_scores = [p['top_journal_score'] for p in pubs]
        intl_fwci_scores = [p['intl_fwci_score'] for p in pubs if p['intl_fwci_score'] is not None]
        sdg_scores = [p['sdg_score'] for p in pubs]
        oa_scores = [p['oa_score'] for p in pubs]
        prominence_scores = [p['prominence_score'] for p in pubs]

        intl_count = sum(1 for p in pubs if p['is_international'])
        has_sdg = any(p['sdg_score'] > 0 for p in pubs)
        has_oa = any(p['oa_score'] > 0 for p in pubs)

        # Top 저널 비율
        top_journal_count = sum(1 for s in top_journal_scores if s >= 15)
        top_journal_pct = (top_journal_count / len(pubs) * 100) if pubs else 0

        # 평균/중위값 계산
        fwci_mean = calc_mean(fwci_vals) if fwci_vals else 0
        fwci_median = calc_median(fwci_vals) if fwci_vals else 0

        score_fwci_mean = calc_mean(fwci_scores)
        score_fwci_median = calc_median(fwci_scores)
        score_top_cited = calc_mean(top_cited_scores)
        score_top_journal = calc_mean(top_journal_scores)
        score_intl_collab = calc_mean(intl_fwci_scores) if intl_fwci_scores else 0
        score_sdg = calc_mean(sdg_scores)
        score_oa = calc_mean(oa_scores)
        score_prominence = calc_mean(prominence_scores)

        # 핵심지표 합산
        score_core_mean = score_fwci_mean + score_top_cited + score_top_journal + score_intl_collab
        score_core_median = score_fwci_median + score_top_cited + score_top_journal + score_intl_collab

        # 보조지표
        score_secondary = score_sdg + score_oa + score_prominence

        # 총점
        score_total_mean = score_core_mean + score_secondary
        score_total_median = score_core_median + score_secondary

        # 저장
        cursor.execute("""
            INSERT INTO researcher_score (
                scopus_author_id, scholarly_output, citations, h_index,
                fwci_mean, fwci_median, top_journal_pct,
                intl_collab_count, intl_collab_fwci, has_sdg, has_oa,
                score_fwci_mean, score_fwci_median, score_top_cited, score_top_journal,
                score_intl_collab, score_core_mean, score_core_median,
                score_sdg, score_oa, score_prominence, score_secondary,
                score_total_mean, score_total_median
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scopus_id, author['scholarly_output'], author['citations'], author['h_index'],
            fwci_mean, fwci_median, top_journal_pct,
            intl_count, calc_mean([p['fwci_val'] for p in pubs if p['is_international'] and p['fwci_val']]) if intl_count > 0 else 0,
            1 if has_sdg else 0, 1 if has_oa else 0,
            score_fwci_mean, score_fwci_median, score_top_cited, score_top_journal,
            score_intl_collab, score_core_mean, score_core_median,
            score_sdg, score_oa, score_prominence, score_secondary,
            score_total_mean, score_total_median
        ))
        insert_count += 1

    conn.commit()
    conn.close()

    elapsed = time.time() - start
    print(f"\n[6] Done! Inserted {insert_count} researcher scores in {elapsed:.1f}s")
    print("=" * 60)


if __name__ == '__main__':
    main()
