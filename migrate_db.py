import sqlite3
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

SQLITE_DB = 'fleet.db'

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

def migrate_data():
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_cursor = sqlite_conn.cursor()

    mysql_conn = pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, charset='utf8mb4'
    )
    mysql_cursor = mysql_conn.cursor()

    # Get valid motos
    mysql_cursor.execute("SELECT placa FROM motos")
    valid_motos = [row[0] for row in mysql_cursor.fetchall()]

    print("\n--- Migrating Transações ---")
    sqlite_cursor.execute("SELECT origem, tipo, valor, data, cpf_cliente, placa_moto FROM transacoes")
    transacoes = sqlite_cursor.fetchall()
    count_trans = 0
    for t in transacoes:
        origem = str(t[0]).upper()
        if origem not in ['ASAAS', 'VISIUN', 'ASAAS_LUCRO', 'OUTROS']:
            origem = 'OUTROS'
            
        placa = t[5]
        if placa and placa not in valid_motos:
            print(f"Skipping foreign key link for Placa {placa} (Not found in DB)")
            placa = None

        try:
            mysql_cursor.execute(
                "INSERT INTO transacoes (origem, tipo, valor, data, cpf_cliente, placa_moto) VALUES (%s, %s, %s, %s, %s, %s)", 
                (origem, t[1], t[2], t[3], t[4], placa)
            )
            mysql_conn.commit()
            count_trans += 1
        except pymysql.Error as e:
            print(f"Error migrating transação {t}: {e}")
            
    print(f"  Migrated {count_trans} transações.")
    mysql_conn.close()

if __name__ == '__main__':
    migrate_data()
