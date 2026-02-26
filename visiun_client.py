import os
import requests
from dotenv import load_dotenv

load_dotenv()

class VisiunClient:
    def __init__(self):
        self.api_key = os.getenv("VISIUN_API_KEY")
        # Using a placeholder URL until proper Visiun API documentation is provided
        self.base_url = "https://api.visiun.com.br/v1" 
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _check_config(self):
        if not self.api_key:
            raise ValueError("VISIUN_API_KEY is not defined in the .env file.")

    def get_expenses(self, date_from, date_to):
        """
        Reads maintenance, fines, and royalty fees.
        date_from, date_to should be YYYY-MM-DD.
        """
        self._check_config()
        
        # Placeholder endpoint - adjust based on actual Visiun API docs
        url = f"{self.base_url}/expenses" 
        
        params = {
            "start_date": date_from,
            "end_date": date_to
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"Failed to fetch expenses from Visiun: {e}")
            # If it's a 404 because the placeholder URL is wrong, just return empty list for now
            if response.status_code == 404:
                return []
            raise
