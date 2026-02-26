import sqlite3

DB_NAME = 'fleet.db'

def main():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Wipe all existing motos, locacoes, and visiun transactions
    cursor.execute("DELETE FROM locacoes")
    cursor.execute("DELETE FROM motos")
    cursor.execute("DELETE FROM transacoes WHERE origem = 'VISIUN'")
    print("Dados antigos de motos, locações e transações Visiun foram apagados.")

    # 2. Insert 5 Motos (R$74.605,88 / 5 = R$14.921,17 each)
    placas = ['UBD8C81', 'UBF5F97', 'UBF5G15', 'UBD8I47', 'UBF5G16']
    valor_unitario = 14921.17
    
    for placa in placas:
        cursor.execute("INSERT INTO motos (placa, valor_compra) VALUES (?, ?)", (placa, valor_unitario))
    print(f"{len(placas)} motos reais inseridas.")

    # 3. Create a single 'Cliente Único Visiun'
    cpf_cliente = "000.000.000-00"
    data_insercao = "2026-02-01"

    for placa in placas:
        cursor.execute("INSERT INTO locacoes (cpf_cliente, placa_moto, data_inicio) VALUES (?, ?, ?)", 
                       (cpf_cliente, placa, "2025-01-01"))
    print("Locações ativas vinculadas ao contrato Visiun.")

    # 4. Insert Receitas (Entradas Visiun)
    receitas = [
        ("VISIUN", "entrada", 1593.20, data_insercao, cpf_cliente, None), # Aluguel
        ("VISIUN", "entrada", 700.00, data_insercao, cpf_cliente, None),  # Caução
    ]
    for r in receitas:
        cursor.execute("INSERT INTO transacoes (origem, tipo, valor, data, cpf_cliente, placa_moto) VALUES (?, ?, ?, ?, ?, ?)", r)

    # 5. Insert Despesas (Saídas Visiun)
    despesas = [
        ("VISIUN", "saida", 74605.88, data_insercao, None, None), # Compra de Moto
        ("VISIUN", "saida", 258.06, data_insercao, None, None),   # Taxa de espaço
        ("VISIUN", "saida", 79.66, data_insercao, None, None),    # Royalties
    ]
    for d in despesas:
        cursor.execute("INSERT INTO transacoes (origem, tipo, valor, data, cpf_cliente, placa_moto) VALUES (?, ?, ?, ?, ?, ?)", d)

    conn.commit()
    conn.close()
    print("Database reiniciada com sucesso. Apenas as 5 motos reais da Visiun e suas transações constam no sistema.")

if __name__ == '__main__':
    main()
