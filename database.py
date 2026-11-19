# database.py
import pyodbc
from config import DB_SERVER, DB_NAME

def get_db_connection():
    # Use for Windows Authentication 
    conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};DATABASE={DB_NAME};Trusted_Connection=yes;'
    try:
        conn = pyodbc.connect(conn_str)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None