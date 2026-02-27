import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

class DatabaseManager:
    def __init__(self):
        pass

    def get_connection(self):
        try:
            return pymysql.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASS,
                database=DB_NAME,
                charset='utf8mb4',
                connect_timeout=10,
                autocommit=True
            )
        except Exception as e:
            print(f"!!! DATABASE CONNECTION ERROR !!!")
            print(f"Host: {DB_HOST}")
            print(f"User: {DB_USER}")
            print(f"Error Detail: {str(e)}")
            raise e

    # --- Configurações (Persistence for APIs) ---
    def set_config(self, chave, valor):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = """
                    INSERT INTO configuracoes (chave, valor)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE valor = VALUES(valor)
                """
                cursor.execute(query, (chave, str(valor)))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_config(self, chave, default=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT valor FROM configuracoes WHERE chave = %s", (chave,))
                res = cursor.fetchone()
                return res[0] if res else default
        finally:
            conn.close()

    def get_all_configs(self):
        conn = self.get_connection()
        configs = {}
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT chave, valor FROM configuracoes")
                for row in cursor.fetchall():
                    configs[row[0]] = row[1]
                return configs
        finally:
            conn.close()

    # --- Frota ---
    def add_moto(self, placa, modelo, data_compra, valor_compra, despesas, manutencao, revisao, troca_oleo, disponibilidade, locatario, 
                 doc_file=None, doc_name=None, doc_type=None, 
                 ipva_file=None, ipva_name=None, ipva_type=None, 
                 crlv_file=None, crlv_name=None, crlv_type=None,
                 odometro=0.0):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = """
                    INSERT INTO motos (
                        placa, modelo, data_compra, valor_compra, 
                        despesas, manutencao, revisao, troca_oleo, disponibilidade, locatario,
                        doc_file, doc_name, doc_type,
                        ipva_file, ipva_name, ipva_type,
                        crlv_file, crlv_name, crlv_type,
                        odometro
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    placa, modelo, data_compra, valor_compra,
                    despesas, manutencao, revisao, troca_oleo, disponibilidade, locatario,
                    doc_file, doc_name, doc_type,
                    ipva_file, ipva_name, ipva_type,
                    crlv_file, crlv_name, crlv_type,
                    odometro
                ))
            conn.commit()
            return True
        except pymysql.IntegrityError:
            return False # Already exists
        finally:
            conn.close()

    def update_moto(self, placa, modelo, data_compra, valor_compra, despesas, manutencao, revisao, troca_oleo, disponibilidade, locatario, 
                 doc_file=None, doc_name=None, doc_type=None, 
                 ipva_file=None, ipva_name=None, ipva_type=None, 
                 crlv_file=None, crlv_name=None, crlv_type=None,
                 odometro=0.0):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                # Base update query
                updates = [
                    "modelo = %s", "data_compra = %s", "valor_compra = %s",
                    "despesas = %s", "manutencao = %s", "revisao = %s", "troca_oleo = %s",
                    "disponibilidade = %s", "locatario = %s", "odometro = %s"
                ]
                params = [modelo, data_compra, valor_compra, despesas, manutencao, revisao, troca_oleo, disponibilidade, locatario, odometro]

                # Conditionally update files if provided
                if doc_file is not None or doc_name is not None:
                     updates.extend(["doc_file = %s", "doc_name = %s", "doc_type = %s"])
                     params.extend([doc_file, doc_name, doc_type])
                
                if ipva_file is not None or ipva_name is not None:
                     updates.extend(["ipva_file = %s", "ipva_name = %s", "ipva_type = %s"])
                     params.extend([ipva_file, ipva_name, ipva_type])
                     
                if crlv_file is not None or crlv_name is not None:
                     updates.extend(["crlv_file = %s", "crlv_name = %s", "crlv_type = %s"])
                     params.extend([crlv_file, crlv_name, crlv_type])

                params.append(placa)
                query = f"UPDATE motos SET {', '.join(updates)} WHERE placa = %s"
                cursor.execute(query, tuple(params))
            conn.commit()
            return True
        finally:
            conn.close()

    def update_moto_odometer(self, placa, odometro):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE motos SET odometro = %s WHERE placa = %s", (odometro, placa))
            return True
        finally:
            conn.close()

    def update_moto_status(self, placa, status):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE motos SET disponibilidade = %s WHERE placa = %s", (status, placa))
            conn.commit()
            return True
        finally:
            conn.close()

    def sync_moto_association(self, placa, locatario_nome, move_to_status="Alugado"):
        """
        Links a moto to a locatario and updates both tables.
        If locatario_nome is None, it unlinks and sets moto to 'Disponível'.
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                if locatario_nome:
                    # 1. Unlink this moto from any previous locatario's record
                    cursor.execute("UPDATE locatarios SET placa_associada = NULL WHERE placa_associada = %s", (placa,))
                    # 2. Update Moto: Set locatario and status
                    cursor.execute("UPDATE motos SET locatario = %s, disponibilidade = %s WHERE placa = %s", (locatario_nome, move_to_status, placa))
                    # 3. Update new Locatario record: link to this placa
                    cursor.execute("UPDATE locatarios SET placa_associada = %s WHERE nome = %s", (placa, locatario_nome))
                else:
                    # Unlinking: Clear moto locatario and reset status to Disponivel
                    cursor.execute("UPDATE motos SET locatario = NULL, disponibilidade = 'Disponível' WHERE placa = %s", (placa,))
                    # Clear any locatario record that still points to this placa
                    cursor.execute("UPDATE locatarios SET placa_associada = NULL WHERE placa_associada = %s", (placa,))
            return True
        finally:
            conn.close()

    def delete_moto(self, placa):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM motos WHERE placa = %s", (placa,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
            
    def get_moto_details(self, placa):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                # Return everything EXCEPT the heavy binary blobs to avoid massive memory usage on listings
                # We will fetch blobs in a separate method only when user clicks 'download/view'
                query = """
                SELECT 
                    placa, modelo, data_compra, valor_compra, despesas, manutencao, revisao, troca_oleo, disponibilidade, locatario,
                    doc_name, doc_type, ipva_name, ipva_type, crlv_name, crlv_type, odometro
                FROM motos WHERE placa = %s
                """
                cursor.execute(query, (placa,))
                return cursor.fetchone()
        finally:
            conn.close()

    def get_moto_file(self, placa, file_col_prefix):
        """ Fetch the raw binary data for a moto file. file_col_prefix should be 'doc', 'ipva', or 'crlv' """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = f"SELECT {file_col_prefix}_file, {file_col_prefix}_name, {file_col_prefix}_type FROM motos WHERE placa = %s"
                cursor.execute(query, (placa,))
                return cursor.fetchone()
        finally:
            conn.close()
            
    def get_motos_list(self):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = """
                SELECT 
                    placa, modelo, disponibilidade, locatario, valor_compra, odometro
                FROM motos
                ORDER BY placa ASC
                """
                cursor.execute(query)
                return cursor.fetchall()
        finally:
            conn.close()

    def start_rental(self, cpf_cliente, placa_moto, data_inicio):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT placa FROM motos WHERE placa = %s", (placa_moto,))
                if not cursor.fetchone():
                    print(f"Moto {placa_moto} not found.")
                    return
                cursor.execute("INSERT INTO locacoes (cpf_cliente, placa_moto, data_inicio) VALUES (%s, %s, %s)", 
                               (cpf_cliente, placa_moto, data_inicio))
            conn.commit()
            print(f"Rental started for CPF {cpf_cliente} with moto {placa_moto}.")
        finally:
            conn.close()

    def end_rental(self, placa_moto, data_fim):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE locacoes 
                    SET data_fim = %s 
                    WHERE placa_moto = %s AND data_fim IS NULL
                """, (data_fim, placa_moto))
            conn.commit()
            print(f"Rental ended for moto {placa_moto}.")
        finally:
            conn.close()

    def get_active_moto_for_cpf(self, cpf_cliente, transaction_date):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = """
                    SELECT placa_moto 
                    FROM locacoes 
                    WHERE cpf_cliente = %s 
                    AND data_inicio <= %s 
                    AND (data_fim IS NULL OR data_fim >= %s)
                    ORDER BY data_inicio DESC
                    LIMIT 1
                """
                cursor.execute(query, (cpf_cliente, transaction_date, transaction_date))
                result = cursor.fetchone()
                if result:
                    return result[0]
                return None
        finally:
            conn.close()

    def get_active_rentals(self):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = """
                    SELECT l.placa_moto, l.cpf_cliente, l.data_inicio 
                    FROM locacoes l
                    WHERE l.data_fim IS NULL
                """
                cursor.execute(query)
                return cursor.fetchall()
        finally:
            conn.close()

    def add_transaction(self, origem, tipo, valor, data, status='pago', cpf_cliente=None, placa_moto=None):
        placa = placa_moto if placa_moto else self.get_active_moto_for_cpf(cpf_cliente, data)
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO transacoes (origem, tipo, valor, data, status, cpf_cliente, placa_moto)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (origem, tipo, valor, data, status, cpf_cliente, placa))
            conn.commit()
        finally:
            conn.close()

    def get_all_motos(self):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT placa FROM motos")
                return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_transactions(self):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM transacoes")
                return cursor.fetchall()
        finally:
            conn.close()

    def update_transaction(self, tx_id, origem, valor, data, status, cpf_cliente=None, placa_moto=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE transacoes 
                    SET origem=%s, valor=%s, data=%s, status=%s, cpf_cliente=%s, placa_moto=%s
                    WHERE id=%s
                """, (origem, valor, data, status, cpf_cliente, placa_moto, tx_id))
            conn.commit()
        finally:
            conn.close()

    def delete_transaction(self, tx_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM transacoes WHERE id=%s", (tx_id,))
            conn.commit()
        finally:
            conn.close()

    def create_user(self, nome, username, email, senha_hash, papel, status, permissoes="Dashboard"):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO usuarios (nome, username, email, senha_hash, papel, status, permissoes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (nome, username, email, senha_hash, papel, status, permissoes))
            conn.commit()
            return True
        except pymysql.IntegrityError:
            return False
        finally:
            conn.close()

    def get_user_by_username(self, username):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, nome, username, email, senha_hash, papel, status, permissoes, created_at FROM usuarios WHERE username = %s", (username,))
                return cursor.fetchone()
        finally:
            conn.close()

    def get_all_users(self):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, nome, username, email, papel, status, permissoes, created_at FROM usuarios")
                return cursor.fetchall()
        finally:
            conn.close()

    def update_user_access(self, user_id, nome, status, papel, permissoes):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE usuarios SET nome = %s, status = %s, papel = %s, permissoes = %s WHERE id = %s", (nome, status, papel, permissoes, user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
            
    def update_user_password(self, user_id, new_senha_hash):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE usuarios SET senha_hash = %s WHERE id = %s", (new_senha_hash, user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def count_users(self):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM usuarios")
                return cursor.fetchone()[0]
        finally:
            conn.close()

    def record_accountant_export(self, mes_referencia, data_envio, status="sucesso", enviado_por="Sistema"):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO envios_contador (mes_referencia, data_envio, status, enviado_por)
                    VALUES (%s, %s, %s, %s)
                """, (mes_referencia, data_envio, status, enviado_por))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_accountant_exports(self):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                # Assuming schema was altered to include enviado_por. 
                # Use a safe query that returns it or 'Sistema' if missing just in case
                cursor.execute("SELECT id, mes_referencia, data_envio, status, enviado_por FROM envios_contador ORDER BY id DESC")
                return cursor.fetchall()
        finally:
            conn.close()

    def has_sent_export_for_month(self, mes_referencia):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM envios_contador WHERE mes_referencia = %s AND status = 'sucesso'", (mes_referencia,))
                return cursor.fetchone()[0] > 0
        finally:
            conn.close()

    # --- Locatarios (Renters) ---
    def add_locatario(self, nome, cpf, endereco, telefone, email, cnh, placa_associada,
                      cnh_file=None, cnh_name=None, cnh_type=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = """
                    INSERT INTO locatarios (
                        nome, cpf, endereco, telefone, email, cnh,
                        placa_associada, cnh_file, cnh_name, cnh_type
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    nome, cpf, endereco, telefone, email, cnh,
                    placa_associada, cnh_file, cnh_name, cnh_type
                ))
            conn.commit()
            return True
        except pymysql.IntegrityError:
            return False # CPF already exists
        finally:
            conn.close()

    def update_locatario(self, locatario_id, nome, cpf, endereco, telefone, email, cnh, placa_associada,
                        cnh_file=None, cnh_name=None, cnh_type=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                updates = [
                    "nome = %s", "cpf = %s", "endereco = %s", "telefone = %s",
                    "email = %s", "cnh = %s", "placa_associada = %s"
                ]
                params = [nome, cpf, endereco, telefone, email, cnh, placa_associada]

                if cnh_file is not None:
                    updates.extend(["cnh_file = %s", "cnh_name = %s", "cnh_type = %s"])
                    params.extend([cnh_file, cnh_name, cnh_type])

                params.append(locatario_id)
                query = f"UPDATE locatarios SET {', '.join(updates)} WHERE id = %s"
                cursor.execute(query, tuple(params))
            conn.commit()
            return True
        finally:
            conn.close()

    def delete_locatario(self, locatario_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM locatarios WHERE id = %s", (locatario_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
            
    def upsert_asaas_customers(self, customers):
        """
        Receives a list of dicts from Asaas and UPSERTS them using CPF/CNPJ.
        """
        conn = self.get_connection()
        count_inserted = 0
        count_updated = 0
        
        try:
            with conn.cursor() as cursor:
                for c in customers:
                    nome = c.get('name', '')
                    cpf_cnpj = c.get('cpfCnpj', '')
                    
                    if not cpf_cnpj:
                        continue
                        
                    email = c.get('email', '')
                    telefone = c.get('mobilePhone') or c.get('phone') or ''
                    
                    endereco = ""
                    if c.get('address'):
                        parts = [
                            f"{c.get('address')}, {c.get('addressNumber')}",
                            c.get('complement') or "",
                            c.get('province') or "",
                            f"{c.get('city')}-{c.get('state')}",
                            c.get('postalCode') or ""
                        ]
                        endereco = " | ".join([p for p in parts if p])
                        
                    query = """
                        INSERT INTO locatarios (nome, cpf, endereco, telefone, email)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        nome = VALUES(nome),
                        endereco = VALUES(endereco),
                        telefone = VALUES(telefone),
                        email = VALUES(email)
                    """
                    affected = cursor.execute(query, (nome, cpf_cnpj, endereco, telefone, email))
                    if affected == 1:
                        count_inserted += 1
                    elif affected == 2:
                        count_updated += 1
            conn.commit()
            return count_inserted, count_updated
        finally:
            conn.close()

    def get_locatarios_list(self):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = """
                SELECT id, nome, cpf, telefone, placa_associada 
                FROM locatarios 
                ORDER BY nome ASC
                """
                cursor.execute(query)
                return cursor.fetchall()
        finally:
            conn.close()

    def get_locatario_details(self, locatario_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = """
                SELECT id, nome, cpf, endereco, telefone, email, cnh, placa_associada, cnh_name, cnh_type
                FROM locatarios
                WHERE id = %s
                """
                cursor.execute(query, (locatario_id,))
                return cursor.fetchone()
        finally:
            conn.close()

    def get_locatario_file(self, locatario_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = "SELECT cnh_file, cnh_name, cnh_type FROM locatarios WHERE id = %s"
                cursor.execute(query, (locatario_id,))
                return cursor.fetchone()
        finally:
            conn.close()
