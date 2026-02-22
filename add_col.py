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
try:
    with conn.cursor() as cursor:
        cursor.execute("ALTER TABLE envios_contador ADD COLUMN enviado_por VARCHAR(100) DEFAULT 'Sistema';")
    conn.commit()
    print("Column added.")
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
