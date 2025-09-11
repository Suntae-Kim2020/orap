#!/usr/bin/env python3
"""
CSV 파일 분석 스크립트
- 실제 행 수
- 빈 행 개수
- 중복 EID 개수
- 전체 구조 분석
"""

import pandas as pd
import sys
import os

def analyze_csv_file(filepath):
    print(f"=== CSV 파일 분석: {filepath} ===")
    
    if not os.path.exists(filepath):
        print("❌ 파일이 존재하지 않습니다.")
        return
    
    print("\n1. 파일 기본 정보:")
    file_size = os.path.getsize(filepath) / (1024*1024)  # MB
    print(f"   파일 크기: {file_size:.2f} MB")
    
    print("\n2. 원본 파일 구조 분석:")
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
        total_file_lines = len(lines)
        print(f"   전체 파일 행 수: {total_file_lines}")
        
        # 처음 25행과 마지막 5행 확인
        print(f"   첫 25행 미리보기:")
        for i, line in enumerate(lines[:25], 1):
            line_preview = line.strip()[:100]
            if line_preview:
                print(f"     {i:2d}: {line_preview}{'...' if len(line.strip()) > 100 else ''}")
            else:
                print(f"     {i:2d}: [빈 행]")
        
        if total_file_lines > 25:
            print(f"   마지막 5행:")
            for i, line in enumerate(lines[-5:], total_file_lines-4):
                line_preview = line.strip()[:100]
                if line_preview:
                    print(f"     {i:2d}: {line_preview}{'...' if len(line.strip()) > 100 else ''}")
                else:
                    print(f"     {i:2d}: [빈 행]")

    print("\n3. pandas로 데이터 읽기 (header=19):")
    try:
        # 현재 앱과 동일한 방식으로 읽기
        df = pd.read_csv(filepath, encoding='utf-8-sig', header=19, skiprows=None, keep_default_na=False)
        original_len = len(df)
        print(f"   pandas 원본 데이터프레임 크기: {original_len}")
        
        # 빈 행 제거 전후 비교
        print(f"   완전히 빈 행 개수: {df.isnull().all(axis=1).sum()}")
        df_cleaned = df.dropna(how='all').reset_index(drop=True)
        cleaned_len = len(df_cleaned)
        print(f"   빈 행 제거 후 크기: {cleaned_len}")
        print(f"   제거된 행 수: {original_len - cleaned_len}")
        
        # 컬럼 정보
        print(f"   컬럼 수: {len(df_cleaned.columns)}")
        print(f"   첫 5개 컬럼명: {list(df_cleaned.columns[:5])}")
        
        # EID 컬럼 분석
        if 'EID' in df_cleaned.columns:
            eid_col = df_cleaned['EID']
            total_eids = len(eid_col)
            non_empty_eids = eid_col.astype(str).str.strip().ne('').sum()
            unique_eids = eid_col.dropna().astype(str).str.strip().nunique()
            duplicate_eids = non_empty_eids - unique_eids
            
            print(f"\n4. EID 분석:")
            print(f"   전체 EID 값: {total_eids}")
            print(f"   비어있지 않은 EID: {non_empty_eids}")
            print(f"   고유 EID 개수: {unique_eids}")
            print(f"   중복 EID 개수: {duplicate_eids}")
            
            if duplicate_eids > 0:
                # 중복 EID 상세 분석
                eid_counts = eid_col.astype(str).str.strip().value_counts()
                duplicates = eid_counts[eid_counts > 1]
                print(f"   중복되는 EID 종류: {len(duplicates)}")
                print(f"   가장 많이 중복된 EID (상위 5개):")
                for eid, count in duplicates.head().items():
                    if eid and eid != '':
                        print(f"     {eid}: {count}번")
        else:
            print(f"\n4. EID 컬럼을 찾을 수 없습니다.")
            print(f"   사용 가능한 컬럼: {list(df_cleaned.columns)}")
        
        # 기대값과 실제값 비교
        expected_records = 13857 - 21 + 1  # 13837
        print(f"\n5. 레코드 수 분석:")
        print(f"   기대 레코드 수 (13857 - 21 + 1): {expected_records}")
        print(f"   실제 처리된 레코드 수: {cleaned_len}")
        print(f"   차이: {expected_records - cleaned_len}")
        
        if expected_records != cleaned_len:
            print(f"   ⚠️  차이 원인 분석:")
            print(f"      - 파일 마지막 부분에 빈 행이 {expected_records - cleaned_len}개 있을 가능성")
            print(f"      - 또는 행 번호 계산에 오류가 있을 가능성")
            
    except Exception as e:
        print(f"   ❌ 파일 읽기 오류: {e}")

if __name__ == "__main__":
    # 업로드 폴더에서 가장 최근 파일 찾기
    upload_dir = "/Users/suntaekim/ORA/uploads"
    if os.path.exists(upload_dir):
        files = [f for f in os.listdir(upload_dir) if f.endswith('.csv')]
        if files:
            latest_file = os.path.join(upload_dir, sorted(files)[-1])
            analyze_csv_file(latest_file)
        else:
            print("업로드 폴더에 CSV 파일이 없습니다.")
    else:
        print("업로드 폴더가 존재하지 않습니다.")