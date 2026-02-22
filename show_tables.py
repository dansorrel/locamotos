import pymysql
import os
from dotenv import load_dotenv

load_dotenv()
conn = pymysql.connect(
    host=os.getenv("DB_HOST"), 
    user=os.getenv("DB_USER"), 
    password=os.getenv("DB_PASS"), 
    database=os.getenv("DB_NAME")
)
with conn.cursor() as cursor:
    cursor.execute("SHOW TABLES;")
    for row in cursor.fetchall():
        print(row[0])
        cursor.execute(f"DESCRIBE {row[0]};")
        for col in cursor.fetchall():
            print(f"  {col[0]} ({col[1]})")
conn.close()
