import sqlite3
import datetime

DB_NAME = 'fleet.db'

def main():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Insert 5 Motos (R$74.605,88 / 5 = R$14.921,17 each)
    placas = ['UBD8C81', 'UBF5F97', 'UBF5G15', 'UBD8I47', 'UBF5G16']
    valor_unitario = 14921.17
    
    for placa in placas:
        try:
            cursor.execute("INSERT INTO motos (placa, valor_compra) VALUES (?, ?)", (placa, valor_unitario))
        except sqlite3.IntegrityError:
            pass # Already exists

    # 2. Insert Client/Locacoes (Placeholder client since name was not provided)
    # Using a fake CPF to link
    cpf_cliente = "000.000.000-00"
    nome_cliente = "Cliente Único Velo"
    data_insercao = "2026-02-01"

    for placa in placas:
        cursor.execute("INSERT INTO locacoes (cpf_cliente, placa_moto, data_inicio) VALUES (?, ?, ?)", 
                       (cpf_cliente, placa, "2025-01-01")) # Assuming rented since 2025

    # 3. Insert Receitas (Entradas Velo)
    receitas = [
        ("VELO", "entrada", 1593.20, data_insercao, cpf_cliente, None), # Aluguel
        ("VELO", "entrada", 700.00, data_insercao, cpf_cliente, None),  # Caução
    ]
    
    for r in receitas:
        cursor.execute("INSERT INTO transacoes (origem, tipo, valor, data, cpf_cliente, placa_moto) VALUES (?, ?, ?, ?, ?, ?)", r)

    # 4. Insert Despesas (Saídas Velo)
    despesas = [
        ("VELO", "saida", 74605.88, data_insercao, None, None), # Compra de Moto (Total)
        ("VELO", "saida", 258.06, data_insercao, None, None),   # Taxa de espaço
        ("VELO", "saida", 79.66, data_insercao, None, None),    # Royalties
    ]
    
    for d in despesas:
        cursor.execute("INSERT INTO transacoes (origem, tipo, valor, data, cpf_cliente, placa_moto) VALUES (?, ?, ?, ?, ?, ?)", d)

    conn.commit()
    conn.close()
    print("Dados inseridos com sucesso no banco de dados!")

if __name__ == '__main__':
    main()
