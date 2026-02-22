import os
import requests
from dotenv import load_dotenv

load_dotenv()

class InterClient:
    def __init__(self):
        # Base URL for Banco Inter API v2
        self.base_url = "https://cdpj.partners.bancointer.com.br"
        
        # Paths to the Mtls certificates stored locally
        self.cert_path = os.getenv("INTER_CERT", "certs/inter.crt")
        self.key_path = os.getenv("INTER_KEY", "certs/inter.key")
        
        # Read raw string from env (Streamlit Secrets)
        self.cert_content = os.getenv("INTER_CERT_RAW")
        self.key_content = os.getenv("INTER_KEY_RAW")
        
        # For simplicity in this foundation, we expect an auth token or client_id/secret to fetch it.
        # Banco Inter requires an OAuth2 token flow using MTLS. 
        # This requires Client ID and Client Secret, which the user should also add via UI if needed.
        self.client_id = os.getenv("INTER_CLIENT_ID")
        self.client_secret = os.getenv("INTER_CLIENT_SECRET")
        
        self.access_token = None

    def _check_certs(self):
        # If certificates don't exist in the file system but we have the raw string in ENV (Streamlit Cloud),
        # create them on the fly.
        os.makedirs("certs", exist_ok=True)
        if not os.path.exists(self.cert_path) and self.cert_content:
            with open(self.cert_path, "w") as f:
                f.write(self.cert_content.replace("\\n", "\n"))
        if not os.path.exists(self.key_path) and self.key_content:
            with open(self.key_path, "w") as f:
                f.write(self.key_content.replace("\\n", "\n"))

        if not self.cert_path or not self.key_path:
            raise ValueError("Inter Digital Certificate paths are not defined in the .env file.")
        if not os.path.exists(self.cert_path) or not os.path.exists(self.key_path):
             raise FileNotFoundError("Inter Certificates not found at the specified paths. Check your Streamlit Secrets.")

    def get_token(self):
        """Fetches the OAuth2 access token using MTLS"""
        self._check_certs()
        if not self.client_id or not self.client_secret:
            raise ValueError("Inter Client ID and Secret are missing. Please add them to .env")

        url = f"{self.base_url}/oauth/v2/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "extrato.read",
            "grant_type": "client_credentials"
        }

        response = requests.post(
            url, 
            headers=headers, 
            data=data, 
            cert=(self.cert_path, self.key_path)
        )
        response.raise_for_status()
        self.access_token = response.json().get("access_token")
        return self.access_token

    def get_bank_statement(self, data_inicio, data_fim):
        """
        Queries the PJ bank statement.
        data_inicio, data_fim in YYYY-MM-DD
        If the date range is >90 days, it automatically chunks the requests.
        """
        if not self.access_token:
            self.get_token()

        from datetime import datetime, timedelta

        start_dt = datetime.strptime(data_inicio, "%Y-%m-%d")
        end_dt = datetime.strptime(data_fim, "%Y-%m-%d")

        all_transacoes = []
        base_response = {}

        current_start = start_dt
        while current_start <= end_dt:
            # Add up to 89 days so the interval is 90 days inclusive
            current_end = current_start + timedelta(days=89)
            if current_end > end_dt:
                current_end = end_dt
                
            url = f"{self.base_url}/banking/v2/extrato"
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            params = {
                "dataInicio": current_start.strftime("%Y-%m-%d"),
                "dataFim": current_end.strftime("%Y-%m-%d")
            }

            response = requests.get(
                url, 
                headers=headers, 
                params=params, 
                cert=(self.cert_path, self.key_path)
            )
            response.raise_for_status()
            data = response.json()
            
            if not base_response:
                base_response = data
                all_transacoes = data.get("transacoes", [])
            else:
                all_transacoes.extend(data.get("transacoes", []))

            # Move to the day after the current end
            current_start = current_end + timedelta(days=1)

        base_response["transacoes"] = all_transacoes
        return base_response

    def get_balance(self, data_saldo=None):
        """
        Queries the PJ account balance.
        data_saldo in YYYY-MM-DD (optional, defaults to current day if None)
        """
        if not self.access_token:
            self.get_token()

        url = f"{self.base_url}/banking/v2/saldo"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        params = {}
        if data_saldo:
            params["dataSaldo"] = data_saldo

        response = requests.get(
            url, 
            headers=headers, 
            params=params, 
            cert=(self.cert_path, self.key_path)
        )
        response.raise_for_status()
        return response.json()

    def get_extrato_export(self, data_inicio, data_fim, tipo_arquivo="PDF"):
        """
        Exports the bank statement directly from Banco Inter.
        tipo_arquivo can be "PDF" or "OFX".
        Returns the base64 encoded string directly.
        """
        if not self.access_token:
            self.get_token()

        url = f"{self.base_url}/banking/v2/extrato/exportar"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        params = {
            "dataInicio": data_inicio,
            "dataFim": data_fim,
            "tipoArquivo": tipo_arquivo
        }

        response = requests.get(
            url, 
            headers=headers, 
            params=params, 
            cert=(self.cert_path, self.key_path)
        )
        response.raise_for_status()
        
        # Inter API usually returns the base64 string under the 'pdf' key regardless of the requested type
        data = response.json()
        return data.get("pdf", "")
