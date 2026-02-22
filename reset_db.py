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

def reset_and_recreate():
    try:
        with conn.cursor() as cursor:
            # 1. Truncate financial and log tables
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            cursor.execute("TRUNCATE TABLE transacoes;")
            cursor.execute("TRUNCATE TABLE locacoes;")
            cursor.execute("TRUNCATE TABLE envios_contador;")
            print("Truncated transacoes, locacoes, envios_contador.")
            
            # 2. Drop and Recreate motos
            cursor.execute("DROP TABLE IF EXISTS motos;")
            cursor.execute("""
            CREATE TABLE motos (
                placa VARCHAR(20) PRIMARY KEY,
                modelo VARCHAR(100),
                data_compra DATE,
                valor_compra DECIMAL(10, 2),
                despesas TEXT,
                manutencao TEXT,
                revisao TEXT,
                disponibilidade VARCHAR(50) DEFAULT 'Disponível',
                locatario VARCHAR(150),
                doc_file MEDIUMBLOB,
                doc_name VARCHAR(255),
                doc_type VARCHAR(100),
                ipva_file MEDIUMBLOB,
                ipva_name VARCHAR(255),
                ipva_type VARCHAR(100),
                crlv_file MEDIUMBLOB,
                crlv_name VARCHAR(255),
                crlv_type VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            print("Table 'motos' recreated successfully with BLOB columns.")
        
        conn.commit()
    except Exception as e:
        print("Error during reset:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    reset_and_recreate()
