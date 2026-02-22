import os
import requests
from dotenv import load_dotenv

load_dotenv()

class AsaasClient:
    def __init__(self):
        self.api_key = os.getenv("ASAAS_API_KEY")
        # Base URL for Asaas Production API 
        self.base_url = "https://api.asaas.com/v3"
        self.headers = {
            "access_token": self.api_key,
            "Content-Type": "application/json"
        }

    def _check_config(self):
        if not self.api_key:
            raise ValueError("ASAAS_API_KEY is not defined in the .env file.")

    def get_received_payments(self, date_from, date_to):
        """
        Monitors incoming payments.
        date_from, date_to should be YYYY-MM-DD
        """
        self._check_config()
        url = f"{self.base_url}/payments"
        
        params = {
            "paymentDate[ge]": date_from,
            "paymentDate[le]": date_to,
            "status": "RECEIVED"
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json().get('data', [])

    def get_balance(self):
        """
        Retrieves the current available balance in the Asaas account.
        """
        self._check_config()
        url = f"{self.base_url}/finance/balance"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json().get('balance', 0.0)

    def create_pix_transfer(self, pix_key, pix_key_type, value, description=""):
        """
        Executes an outgoing Pix transfer.
        """
        self._check_config()
        url = f"{self.base_url}/transfers"
        
        payload = {
            "value": value,
            "pixAddressKey": pix_key,
            "pixAddressKeyType": pix_key_type,
            "description": description,
            "operationType": "PIX"
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()

    def get_customers(self):
        """
        Retrieves all customers (locatários) from Asaas.
        Handles pagination to get the complete list.
        """
        self._check_config()
        url = f"{self.base_url}/customers"
        
        all_customers = []
        offset = 0
        limit = 100
        
        while True:
            params = {
                "offset": offset,
                "limit": limit
            }
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            customers = data.get('data', [])
            all_customers.extend(customers)
            
            if not data.get('hasMore'):
                break
                
            offset += limit
            
        return all_customers

    def get_all_payments(self, date_from, date_to):
        """
        Retrieves all payments generated between two creation dates using pagination.
        date_from, date_to should be YYYY-MM-DD
        """
        self._check_config()
        url = f"{self.base_url}/payments"
        
        all_payments = []
        offset = 0
        limit = 100
        
        while True:
            params = {
                "dateCreated[ge]": date_from,
                "dateCreated[le]": date_to,
                "offset": offset,
                "limit": limit
            }
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            payments = data.get('data', [])
            all_payments.extend(payments)
            
            if not data.get('hasMore'):
                break
                
            offset += limit
            
        return all_payments
