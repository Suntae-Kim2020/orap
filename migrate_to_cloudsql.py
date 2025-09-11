#!/usr/bin/env python3
"""
Direct migration from SQLite to Cloud SQL PostgreSQL
"""

import sqlite3
import psycopg2
import sys
import os
from psycopg2.extras import RealDictCursor

# Cloud SQL connection parameters
CLOUD_SQL_HOST = "35.216.126.143"  # Cloud SQL instance public IP
CLOUD_SQL_DB = "jbnu"
CLOUD_SQL_USER = "jbnu-user"
CLOUD_SQL_PASSWORD = "JBNUorap2025!"
CLOUD_SQL_PORT = 5432

def connect_sqlite():
    """Connect to local SQLite database"""
    try:
        conn = sqlite3.connect('jbnu.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Error connecting to SQLite: {e}")
        return None

def connect_postgresql():
    """Connect to Cloud SQL PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=CLOUD_SQL_HOST,
            database=CLOUD_SQL_DB,
            user=CLOUD_SQL_USER,
            password=CLOUD_SQL_PASSWORD,
            port=CLOUD_SQL_PORT
        )
        return conn
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None

def get_table_schema(sqlite_conn, table_name):
    """Get table schema from SQLite"""
    cursor = sqlite_conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()

def create_postgresql_table(pg_conn, table_name, schema):
    """Create table in PostgreSQL"""
    cursor = pg_conn.cursor()
    
    # Map SQLite types to PostgreSQL
    type_mapping = {
        'INTEGER': 'INTEGER',
        'TEXT': 'TEXT',
        'REAL': 'REAL',
        'BLOB': 'BYTEA'
    }
    
    columns = []
    for col in schema:
        col_name = col[1]
        col_type = col[2].upper()
        is_pk = col[5] == 1
        not_null = col[3] == 1
        
        pg_type = type_mapping.get(col_type, 'TEXT')
        
        if is_pk and col_type == 'INTEGER':
            pg_type = 'SERIAL PRIMARY KEY'
        
        col_def = f"{col_name} {pg_type}"
        if not_null and not is_pk:
            col_def += " NOT NULL"
        
        columns.append(col_def)
    
    create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns)})"
    print(f"Creating table {table_name}: {create_sql}")
    
    cursor.execute(create_sql)
    pg_conn.commit()

def migrate_table_data(sqlite_conn, pg_conn, table_name):
    """Migrate data from SQLite to PostgreSQL"""
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    # Get all data from SQLite
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()
    
    if not rows:
        print(f"No data to migrate for table {table_name}")
        return
    
    # Get column names
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    columns_info = sqlite_cursor.fetchall()
    column_names = [col[1] for col in columns_info]
    
    # Prepare insert statement
    placeholders = ', '.join(['%s'] * len(column_names))
    insert_sql = f"INSERT INTO {table_name} ({', '.join(column_names)}) VALUES ({placeholders})"
    
    print(f"Migrating {len(rows)} rows to table {table_name}")
    
    # Insert data
    for row in rows:
        try:
            pg_cursor.execute(insert_sql, tuple(row))
        except Exception as e:
            print(f"Error inserting row {row}: {e}")
            continue
    
    pg_conn.commit()
    print(f"Successfully migrated {len(rows)} rows to {table_name}")

def main():
    """Main migration function"""
    print("Starting SQLite to PostgreSQL migration...")
    
    # Connect to databases
    sqlite_conn = connect_sqlite()
    if not sqlite_conn:
        print("Failed to connect to SQLite database")
        sys.exit(1)
    
    pg_conn = connect_postgresql()
    if not pg_conn:
        print("Failed to connect to PostgreSQL database")
        sys.exit(1)
    
    # Get list of tables
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in sqlite_cursor.fetchall()]
    
    print(f"Found tables: {tables}")
    
    # Migrate each table
    for table_name in tables:
        print(f"\n--- Migrating table: {table_name} ---")
        
        # Get schema
        schema = get_table_schema(sqlite_conn, table_name)
        
        # Create table in PostgreSQL
        create_postgresql_table(pg_conn, table_name, schema)
        
        # Migrate data
        migrate_table_data(sqlite_conn, pg_conn, table_name)
    
    # Close connections
    sqlite_conn.close()
    pg_conn.close()
    
    print("\nMigration completed successfully!")

if __name__ == "__main__":
    main()