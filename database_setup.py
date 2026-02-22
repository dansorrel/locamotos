import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

def create_connection():
    """Create a database connection to the MySQL database."""
    conn = None
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            charset='utf8mb4'
        )
        return conn
    except pymysql.Error as e:
        print(f"Error connecting to MySQL: {e}")
    return conn

def create_table(conn, create_table_sql):
    """Create a table from the create_table_sql statement."""
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
        conn.commit()
    except pymysql.Error as e:
        print(f"Error creating table: {e}")

def main():
    sql_create_motos_table = """
    CREATE TABLE IF NOT EXISTS motos (
        placa VARCHAR(50) PRIMARY KEY,
        valor_compra FLOAT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );"""

    sql_create_link_cpf_placa_table = """
    CREATE TABLE IF NOT EXISTS locacoes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        cpf_cliente VARCHAR(50) NOT NULL,
        placa_moto VARCHAR(50) NOT NULL,
        data_inicio VARCHAR(50) NOT NULL,
        data_fim VARCHAR(50),
        FOREIGN KEY (placa_moto) REFERENCES motos (placa) ON DELETE CASCADE
    );"""

    sql_create_transacoes_table = """
    CREATE TABLE IF NOT EXISTS transacoes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        origem ENUM('ASAAS', 'VELO', 'ASAAS_LUCRO', 'OUTROS') NOT NULL,
        tipo ENUM('entrada', 'saida', 'entrada_liquida') NOT NULL,
        valor FLOAT NOT NULL,
        data VARCHAR(50) NOT NULL,
        cpf_cliente VARCHAR(50),
        placa_moto VARCHAR(50),
        FOREIGN KEY (placa_moto) REFERENCES motos (placa) ON DELETE SET NULL
    );"""

    sql_create_usuarios_table = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        username VARCHAR(100) UNIQUE NOT NULL,
        email VARCHAR(100),
        senha_hash VARCHAR(255) NOT NULL,
        papel ENUM('admin', 'user', 'viewer') NOT NULL,
        status ENUM('aprovado', 'pendente', 'bloqueado') NOT NULL,
        permissoes VARCHAR(255) DEFAULT 'Receitas',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );"""

    sql_create_envios_contador_table = """
    CREATE TABLE IF NOT EXISTS envios_contador (
        id INT AUTO_INCREMENT PRIMARY KEY,
        mes_referencia VARCHAR(20) NOT NULL,
        data_envio VARCHAR(50) NOT NULL,
        status VARCHAR(20) NOT NULL
    );"""

    conn = create_connection()
    if conn is not None:
        create_table(conn, sql_create_motos_table)
        create_table(conn, sql_create_link_cpf_placa_table)
        create_table(conn, sql_create_transacoes_table)
        create_table(conn, sql_create_usuarios_table)
        create_table(conn, sql_create_envios_contador_table)
        print("MySQL Database tables initialized successfully.")
        conn.close()
    else:
        print("Error! cannot create the database connection.")

if __name__ == '__main__':
    main()
