#!/usr/bin/env python3
"""
CSV 파일에서 빈 행들의 정확한 위치 찾기
"""

import pandas as pd

def find_empty_rows_detailed(filepath):
    print(f"=== 빈 행 상세 분석: {filepath} ===")
    
    # 1. 원본 파일의 모든 행 읽기 (raw text)
    print("\n1. 원본 파일 행별 분석:")
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
        total_lines = len(lines)
        print(f"   전체 행 수: {total_lines}")
        
        # 마지막 50행 검사
        start_idx = max(0, total_lines - 50)
        print(f"\n   마지막 50행 분석 ({start_idx+1}행부터 {total_lines}행까지):")
        
        empty_rows = []
        for i in range(start_idx, total_lines):
            line = lines[i]
            line_content = line.strip()
            is_empty = len(line_content) == 0
            
            if is_empty:
                empty_rows.append(i + 1)  # 1-based index
                
            # 마지막 50행 모두 출력
            if len(line_content) == 0:
                print(f"     {i+1:4d}: [빈 행]")
            else:
                preview = line_content[:100]
                print(f"     {i+1:4d}: {preview}{'...' if len(line_content) > 100 else ''}")
        
        print(f"\n   발견된 빈 행들: {empty_rows}")
        print(f"   빈 행 개수: {len(empty_rows)}")
    
    # 2. pandas로 읽었을 때와 비교
    print(f"\n2. pandas 처리 결과:")
    df = pd.read_csv(filepath, encoding='utf-8-sig', header=19, skiprows=None, keep_default_na=False)
    print(f"   pandas가 읽은 데이터 행 수: {len(df)}")
    print(f"   예상 데이터 행 수 (21행~{total_lines}행): {total_lines - 20}")
    print(f"   실제 유효 데이터: {len(df)}")
    print(f"   제외된 행 수: {(total_lines - 20) - len(df)}")
    
    # 3. 상세 분석
    print(f"\n3. 상세 분석:")
    print(f"   20행: 헤더")
    print(f"   21행~{len(df)+20}행: 유효 데이터 ({len(df)}개)")
    
    expected_data_end = 20 + len(df)
    if expected_data_end < total_lines:
        print(f"   {expected_data_end+1}행~{total_lines}행: 제외된 행들")
        excluded_lines = []
        for i in range(expected_data_end, total_lines):
            line_content = lines[i].strip()
            excluded_lines.append({
                'row': i + 1,
                'content': line_content if line_content else '[빈 행]',
                'is_empty': len(line_content) == 0
            })
        
        print(f"   제외된 행들의 상세:")
        for item in excluded_lines:
            print(f"     {item['row']:4d}행: {item['content'][:100]}")
        
        empty_excluded = [item['row'] for item in excluded_lines if item['is_empty']]
        non_empty_excluded = [item['row'] for item in excluded_lines if not item['is_empty']]
        
        print(f"\n   제외된 행 중 빈 행: {empty_excluded}")
        print(f"   제외된 행 중 내용 있는 행: {non_empty_excluded}")

if __name__ == "__main__":
    filepath = '/Users/suntaekim/Downloads/Publications_at_Jeonbuk_National_University_2020_-_2025.csv'
    find_empty_rows_detailed(filepath)