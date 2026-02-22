import os
from asaas_client import AsaasClient
from velo_client import VeloClient
from inter_client import InterClient

# Mock environment variables for testing 
os.environ["ASAAS_API_KEY"] = "mock_asaas_key"
os.environ["VELO_API_KEY"] = "mock_velo_key"
os.environ["INTER_CERT"] = "mock_cert.crt"
os.environ["INTER_KEY"] = "mock_key.key"
os.environ["INTER_CLIENT_ID"] = "mock_client_id"
os.environ["INTER_CLIENT_SECRET"] = "mock_client_secret"

# Create mock files to pass the file existence checks
open("mock_cert.crt", "w").close()
open("mock_key.key", "w").close()

def run_tests():
    print("--- Testing API Configurations ---")
    
    try:
        asaas = AsaasClient()
        asaas._check_config()
        print("✅ AsaasClient loaded mock key successfully.")
        print(f"   Headers prepared: {asaas.headers}")
    except Exception as e:
        print(f"❌ AsaasClient failed: {e}")

    try:
        velo = VeloClient()
        velo._check_config()
        print("✅ VeloClient loaded mock key successfully.")
        print(f"   Headers prepared: {velo.headers}")
    except Exception as e:
        print(f"⚠️ VeloClient (Optional) not configured or failed: {e}")

    try:
        inter = InterClient()
        inter._check_certs()
        print("✅ InterClient found mock certificate files.")
    except Exception as e:
        print(f"❌ InterClient failed: {e}")

    # Cleanup
    os.remove("mock_cert.crt")
    os.remove("mock_key.key")

if __name__ == "__main__":
    run_tests()
