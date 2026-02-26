from database_manager import DatabaseManager

db = DatabaseManager()
try:
    with db.get_connection() as conn:
        with conn.cursor() as cursor:
            # Let's check if odometro exists, if not, create it.
            cursor.execute("SHOW COLUMNS FROM motos LIKE 'odometro'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE motos ADD COLUMN odometro DECIMAL(10,2) DEFAULT 0")
                print("Column 'odometro' added to motos.")
            else:
                print("Column 'odometro' already exists.")
        conn.commit()
except Exception as e:
    print(f"Error: {e}")
