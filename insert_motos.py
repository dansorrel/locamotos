from database_manager import DatabaseManager

db = DatabaseManager()

motos = [
    ("UBD8C81", "SHINERAY SHI 175S S 2026", "Alugado"),
    ("UBF5F97", "HAOJUE JTZ/DK160 2026", "Indisponível"),
    ("UBF5G15", "SUZUKI JTZ/DK160 2026", "Indisponível"),
    ("UBD8I47", "SHINERAY SHI 175S S 2026", "Indisponível"),
    ("UBF5G16", "SUZUKI JTZ/DK160 2026", "Indisponível")
]

for placa, modelo, status in motos:
    # Use "Oficina" for "Indisponível" since the form only has ["Disponível", "Alugada", "Oficina", "Vendida"]
    # or we can update the DB directly with the exact string. The DB accepts any string.
    db.add_moto(
        placa=placa,
        modelo=modelo,
        data_compra="2025-01-01",  # Dummy data, user said "restante eu faço"
        valor_compra=0.0,
        despesas="",
        manutencao="",
        revisao="",
        troca_oleo="",
        disponibilidade=status,
        locatario=""
    )
    print(f"Moto {placa} inserida.")

print("Todas as motos inseridas!")
