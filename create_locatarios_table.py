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

def create_locatarios_table():
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS locatarios (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome VARCHAR(150) NOT NULL,
                cpf VARCHAR(20) UNIQUE NOT NULL,
                endereco TEXT,
                telefone VARCHAR(20),
                email VARCHAR(100),
                cnh VARCHAR(50),
                cnh_file MEDIUMBLOB,
                cnh_name VARCHAR(255),
                cnh_type VARCHAR(100),
                placa_associada VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            print("Table 'locatarios' created successfully.")
        conn.commit()
    except Exception as e:
        print("Error creating locatarios table:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    create_locatarios_table()
