import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import datetime
import calendar
from apscheduler.schedulers.background import BackgroundScheduler

from asaas_client import AsaasClient
from database_manager import DatabaseManager
from inter_client import InterClient
from exports import generate_csv_summary
from mailer import send_accountant_email

load_dotenv()

app = Flask(__name__)

# Initialize clients
asaas_client = AsaasClient()
db_manager = DatabaseManager()

@app.route('/asaas-webhook', methods=['POST'])
def asaas_webhook():
    """
    Endpoint to receive Asaas Webhooks.
    We are specifically interested in the 'PAYMENT_RECEIVED' event.
    """
    data = request.json
    
    if not data:
        return jsonify({"message": "No data received"}), 400

    event_type = data.get('event')
    
    # We only care when the payment is confirmed received
    if event_type == 'PAYMENT_RECEIVED':
        payment_data = data.get('payment', {})
        
        payment_id = payment_data.get('id')
        net_value = float(payment_data.get('netValue', 0.0))
        customer_id = payment_data.get('customer') # Asaas customer ID, might need mapping to CPF
        payment_date = payment_data.get('paymentDate') or payment_data.get('clientPaymentDate')
        
        print(f"--- WEBHOOK RECEIVED: PAYMENT_RECEIVED ---")
        print(f"Payment ID: {payment_id} | Net Value: R${net_value}")
        
        # 1. Retrieve the configured Banco Inter Pix Key
        inter_pix_key = os.getenv("INTER_PIX_KEY")
        inter_pix_key_type = os.getenv("INTER_PIX_KEY_TYPE")
        
        if not inter_pix_key:
            print("ERROR: INTER_PIX_KEY is not configured in .env. Cannot auto-transfer.")
            return jsonify({"message": "Transfer aborted, Pix Key missing."}), 500

        try:
            # 2. Check Available Balance in Asaas
            balance = asaas_client.get_balance()
            print(f"Current Asaas Balance: R${balance}")
            
            if balance >= net_value:
                # 3. Create Pix Transfer to Banco Inter
                print(f"Initiating auto-transfer of R${net_value} to {inter_pix_key}...")
                transfer_response = asaas_client.create_pix_transfer(
                    pix_key=inter_pix_key,
                    pix_key_type=inter_pix_key_type,
                    value=net_value,
                    description=f"Auto-Transfer for Payment {payment_id}"
                )
                print(f"Pix Transfer Created successfully. Response: {transfer_response.get('id')}")
                
                # 4. Record the net profit transaction in our Database
                # Note: Ideally, we should fetch the actual CPF from Asaas using customer_id. 
                # For this MVP, we assume customer_cpf is either in the payload or we log it generically if missing.
                # If 'cpfCnpj' is not in the webhook payload, an extra API call to /customers/{id} would be needed. 
                customer_cpf = payment_data.get('cpfCnpj') 
                
                # Using 'entrada_liquida' to distinguish from gross
                db_manager.add_transaction(
                    origem="ASAAS",
                    tipo="entrada_liquida",
                    valor=net_value,
                    data=payment_date,
                    cpf_cliente=customer_cpf 
                )
                print(f"Net Profit of R${net_value} saved to Database.")
                
            else:
                print(f"INSUFFICIENT FUNDS: Balance (R${balance}) is less than Net Value (R${net_value}).")
        
        except Exception as e:
            print(f"Error processing automation: {e}")
            return jsonify({"message": "Error processing automation", "details": str(e)}), 500

    return jsonify({"message": "Webhook processed successfully."}), 200

def auto_send_accountant_export_job():
    print("[APScheduler] Executing monthly accountant export job...")
    
    # Reload env vars inside job to catch any updates made via UI
    load_dotenv(override=True)
    contador_email = os.getenv("EMAIL_CONTADOR", "")
    
    if not contador_email:
        print("[APScheduler] EMAIL_CONTADOR not configured. Aborting execution.")
        return
        
    hoje = datetime.date.today()
    mes_anterior = (hoje.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
    
    db = DatabaseManager()
    
    if not db.has_sent_export_for_month(mes_anterior):
        print(f"[APScheduler] Generating reports for {mes_anterior}...")
        year_str, month_str = mes_anterior.split('-')
        last_day = calendar.monthrange(int(year_str), int(month_str))[1]
        data_inicio = f"{mes_anterior}-01"
        data_fim = f"{mes_anterior}-{last_day:02d}"
        
        try:
            client = InterClient()
            pdf_b64 = client.get_extrato_export(data_inicio, data_fim, "PDF")
            ofx_b64 = client.get_extrato_export(data_inicio, data_fim, "OFX")
            
            success, msg = send_accountant_email(contador_email, mes_anterior, ofx_b64=ofx_b64, pdf_b64=pdf_b64)
            if success:
                db.record_accountant_export(mes_anterior, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "sucesso", "Worker Automático")
                print(f"[APScheduler] SUCCESS: Reports sent to {contador_email}")
            else:
                db.record_accountant_export(mes_anterior, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "falha", "Worker Automático")
                print(f"[APScheduler] ERROR sending email: {msg}")
        except Exception as e:
            print(f"[APScheduler] EXCEPTION in integration: {str(e)}")
    else:
        print(f"[APScheduler] Reports for {mes_anterior} have already been sent. Skipping.")

if __name__ == '__main__':
    # Initialize Scheduler
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    # Schedule the job to run at 08:00 AM on the 5th day of every month
    scheduler.add_job(
        auto_send_accountant_export_job, 
        'cron', 
        day='5', 
        hour='8', 
        minute='0'
    )
    scheduler.start()
    print("Background Scheduler Started. Job configured for 5th of the month at 08:00 AM.")

    try:
        # Run the Flask app on port 5001
        print("Starting Asaas Webhook Server on port 5001...")
        app.run(host='0.0.0.0', port=5001)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("Scheduler safely shut down.")
