import datetime
from asaas_client import AsaasClient
import sys

client = AsaasClient()
today = datetime.date.today()
start = (today - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
end = today.strftime("%Y-%m-%d")

payments = client.get_all_payments(start, end)
if payments:
    print(payments[0])
    print(payments[0].keys())
else:
    print("No payments in last 90 days")
