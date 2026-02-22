from database_manager import DatabaseManager
import os

def run_verification():
    db = DatabaseManager()
    
    # 1. Setup Data
    print("--- Setting up Data ---")
    db.add_moto("ABC-1234", 15000.00)
    db.add_moto("XYZ-9876", 18000.00)
    
    # 2. Start Rentals
    # Client 1 rents ABC-1234 starting Jan 1st 2024
    db.start_rental("111.222.333-44", "ABC-1234", "2024-01-01")
    
    # Client 2 rents XYZ-9876 starting Feb 1st 2024
    db.start_rental("999.888.777-66", "XYZ-9876", "2024-02-01")

    # 3. Process Transactions (The Core Test)
    print("\n--- Processing Transactions ---")
    
    # Case A: Transaction for Client 1 on Jan 15th (Should link to ABC-1234)
    print("Test A: Transaction for 111.222.333-44 on 2024-01-15 (Expect: ABC-1234)")
    db.add_transaction("ASAAS", "entrada", 500.00, "2024-01-15", "111.222.333-44")
    
    # Case B: Transaction for Client 1 on Dec 31st 2023 (Should NOT link, before rental)
    print("Test B: Transaction for 111.222.333-44 on 2023-12-31 (Expect: None)")
    db.add_transaction("ASAAS", "entrada", 500.00, "2023-12-31", "111.222.333-44")
    
    # Case C: Transaction for Client 2 on Feb 5th (Should link to XYZ-9876)
    print("Test C: Transaction for 999.888.777-66 on 2024-02-05 (Expect: XYZ-9876)")
    db.add_transaction("VELO", "saida", 200.00, "2024-02-05", "999.888.777-66")

    # 4. Verify Results
    print("\n--- Verifying Database State ---")
    transactions = db.get_transactions()
    
    for t in transactions:
        # t structure: (id, origem, tipo, valor, data, cpf, placa)
        t_id, origem, tipo, valor, data, cpf, placa = t
        print(f"ID: {t_id} | Date: {data} | CPF: {cpf} | Linked Plate: {placa}")

    # Clean up (Optional, but good for potential reruns of this script specifically)
    # os.remove('fleet.db') 

if __name__ == "__main__":
    run_verification()
