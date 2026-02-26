import sqlite3
import pymysql
import os
from dotenv import load_dotenv

def make_vania_admin():
    load_dotenv()
    
    # Check if there's a mysql connection configured
    if os.getenv("DB_HOST"):
        conn = pymysql.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            database=os.getenv("DB_NAME"),
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        query = "UPDATE usuarios SET papel = 'admin', status = 'aprovado', permissoes = 'Dashboard, ASAAS, Inter, Motos, Locatários, Despesas, Configurações' WHERE nome LIKE '%Vania%' OR username LIKE '%vania%'"
        cursor.execute(query)
        conn.commit()
        print(f"Updated {cursor.rowcount} rows for Vania in MySQL.")
        conn.close()
    else:
        print("No MySQL credentials found.")

if __name__ == '__main__':
    make_vania_admin()
