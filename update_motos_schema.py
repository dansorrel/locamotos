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

def update_schema():
    try:
        with conn.cursor() as cursor:
            # Check if troca_oleo exists, if not add it
            cursor.execute("ALTER TABLE motos ADD COLUMN troca_oleo TEXT AFTER revisao;")
            print("Added troca_oleo column.")
        conn.commit()
    except Exception as e:
        print("Error or column already exists:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    update_schema()
