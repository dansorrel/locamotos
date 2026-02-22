import os
import sys

# Ensure we're in the right directory to import auth and database_manager
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database_manager import DatabaseManager
from auth import hash_password

def create_admin_user():
    db = DatabaseManager()
    
    # Check if user already exists
    existing_user = db.get_user_by_username("dansorrel")
    if existing_user:
        print("User 'dansorrel' already exists.")
        
    # Optionally, update password just in case
    admin_pass = os.getenv("ADMIN_PASSWORD") # Suggestion: define this in .env or provide manually
    if admin_pass:
        new_hash = hash_password(admin_pass)
        db.update_user_password(existing_user[0], new_hash)
        print("Updated password for existing 'dansorrel' user using ADMIN_PASSWORD env var.")
    else:
        print("ADMIN_PASSWORD not set. Password not updated.")
    return

# Create new admin user
nome = "Dan Sorrel"
username = "dansorrel"
email = "admin@locamotos.dansorrel.com"
admin_pass = os.getenv("ADMIN_PASSWORD")
if not admin_pass:
    print("Error: ADMIN_PASSWORD environment variable not set.")
    return
senha_hash = hash_password(admin_pass)
papel = "admin"
status = "aprovado"
permissoes = "Dashboard, Dashboard Contábil, Despesas, Clientes, Frota, Tabela de Locações, Transações, Exportar OFX, Configurações"

success = db.create_user(nome, username, email, senha_hash, papel, status, permissoes)
    
if success:
    print(f"Successfully created admin user: {username}")
else:
    print(f"Failed to create admin user: {username}")

if __name__ == "__main__":
    create_admin_user()
