import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

conn = pymysql.connect(
    host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, charset='utf8mb4'
)

def add_status_column():
    try:
        with conn.cursor() as cursor:
            # Check if column exists first
            cursor.execute("SHOW COLUMNS FROM transacoes LIKE 'status'")
            result = cursor.fetchone()
            if not result:
                cursor.execute("""
                ALTER TABLE transacoes 
                ADD COLUMN status ENUM('pago', 'pendente') DEFAULT 'pago' AFTER data;
                """)
                print("Column 'status' added successfully to transacoes table.")
            else:
                print("Column 'status' already exists.")
        conn.commit()
    except Exception as e:
        print("Error updating transacoes table:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    add_status_column()
