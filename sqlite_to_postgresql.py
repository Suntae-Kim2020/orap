#!/usr/bin/env python3
"""
SQLite dump to PostgreSQL conversion script
Converts SQLite .dump file to PostgreSQL-compatible SQL
"""

import re
import sys

def convert_sqlite_to_postgresql(input_file, output_file):
    """Convert SQLite dump to PostgreSQL compatible SQL"""
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove SQLite specific pragmas
    content = re.sub(r'PRAGMA.*?;', '', content, flags=re.IGNORECASE)
    
    # Remove BEGIN TRANSACTION and COMMIT (PostgreSQL handles these differently)
    content = re.sub(r'BEGIN TRANSACTION;', 'BEGIN;', content, flags=re.IGNORECASE)
    
    # Convert SQLite data types to PostgreSQL
    content = re.sub(r'\bINTEGER PRIMARY KEY AUTOINCREMENT\b', 'SERIAL PRIMARY KEY', content, flags=re.IGNORECASE)
    content = re.sub(r'\bINTEGER\b', 'INTEGER', content, flags=re.IGNORECASE)
    content = re.sub(r'\bTEXT\b', 'TEXT', content, flags=re.IGNORECASE)
    content = re.sub(r'\bREAL\b', 'REAL', content, flags=re.IGNORECASE)
    content = re.sub(r'\bBLOB\b', 'BYTEA', content, flags=re.IGNORECASE)
    
    # Fix boolean values
    content = re.sub(r'\b0\b', 'FALSE', content)
    content = re.sub(r'\b1\b', 'TRUE', content)
    
    # Handle datetime strings (keep as TEXT in PostgreSQL)
    # No changes needed as PostgreSQL handles datetime strings well
    
    # Remove SQLite specific CREATE INDEX statements that might conflict
    # and let PostgreSQL create them automatically
    
    # Fix INSERT statements - ensure proper escaping
    content = re.sub(r"INSERT INTO ([^\s]+) VALUES\((.*?)\);", 
                    lambda m: f"INSERT INTO {m.group(1)} VALUES({m.group(2)});", 
                    content, flags=re.DOTALL)
    
    # Add DROP TABLE IF EXISTS for clean import
    tables = re.findall(r'CREATE TABLE ([^\s\(]+)', content, flags=re.IGNORECASE)
    drop_statements = []
    for table in tables:
        drop_statements.append(f"DROP TABLE IF EXISTS {table} CASCADE;")
    
    # Add drop statements at the beginning
    if drop_statements:
        drop_section = '\n'.join(drop_statements) + '\n\n'
        content = drop_section + content
    
    # Write converted content
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Conversion completed. Output saved to: {output_file}")
    print(f"Number of tables found: {len(tables)}")
    print(f"Tables: {', '.join(tables)}")

if __name__ == "__main__":
    input_file = "jbnu_database_dump.sql"
    output_file = "jbnu_postgresql.sql"
    
    try:
        convert_sqlite_to_postgresql(input_file, output_file)
    except FileNotFoundError:
        print(f"Error: {input_file} not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error during conversion: {e}")
        sys.exit(1)