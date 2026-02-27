import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

def send_accountant_email(to_email, mes_referencia, ofx_b64=None, pdf_b64=None, clientes_csv_bytes=None):
    """
    Sends an email with the Inter OFX and Inter PDF attachments to the accountant.
    Optionally includes a CSV with client payment data for invoice issuance (NF).
    Expects base64 encoded strings for OFX and PDF from Banco Inter API.
    clientes_csv_bytes: raw bytes of a CSV file with client payment data.
    """
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT", 587)
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    
    if not smtp_server or not smtp_user or not smtp_pass:
        print(f"SMTP Credentials missing. SIMULATING email send to {to_email} for {mes_referencia}.")
        return True, "Email simulado com sucesso (credenciais SMTP ausentes)."

    msg = EmailMessage()
    msg['Subject'] = f"Relatório Financeiro Locamotos - {mes_referencia}"
    msg['From'] = smtp_user
    msg['To'] = to_email
    
    body = f"Olá,\n\nSegue em anexo os relatórios financeiros consolidados referentes ao mês {mes_referencia}.\n\nAnexos:\n- Extrato Oficial Banco Inter (PDF)\n- Histórico de Transações Banco Inter (OFX)"
    
    if clientes_csv_bytes:
        body += "\n- Relatório de Clientes com Recebimentos no Mês (CSV) — para emissão de Notas Fiscais"
         
    body += "\n\nAtenciosamente,\nLocamotos."
    
    msg.set_content(body)
    
    import base64
    
    # Attach Inter OFX
    if ofx_b64:
        try:
            ofx_bytes = base64.b64decode(ofx_b64)
            msg.add_attachment(ofx_bytes, maintype='application', subtype='ofx', filename=f"extrato_inter_{mes_referencia}.ofx")
        except Exception as e:
            print(f"Error decoding OFX: {e}")
            
    # Attach Inter PDF
    if pdf_b64:
        try:
            pdf_bytes = base64.b64decode(pdf_b64)
            msg.add_attachment(pdf_bytes, maintype='application', subtype='pdf', filename=f"extrato_inter_{mes_referencia}.pdf")
        except Exception as e:
            print(f"Error decoding PDF: {e}")
    
    # Attach Clients CSV for NF issuance
    if clientes_csv_bytes:
        msg.add_attachment(clientes_csv_bytes, maintype='text', subtype='csv', filename=f"clientes_recebimentos_{mes_referencia}.csv")
            
    try:
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True, "Email com extratos e dados de clientes enviado com sucesso."
    except Exception as e:
        return False, f"Erro ao enviar email: {str(e)}"

def send_password_recovery_email(to_email, username, temp_password):
    """
    Sends an email with a temporary password to the user.
    """
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT", 587)
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    
    if not smtp_server or not smtp_user or not smtp_pass:
        print(f"SMTP Credentials missing. SIMULATING password recovery email to {to_email} for {username}. Temp Pass: {temp_password}")
        return True, "Email simulado com sucesso (credenciais SMTP ausentes)."

    msg = EmailMessage()
    msg['Subject'] = f"Locamotos - Recuperação de Senha"
    msg['From'] = smtp_user
    msg['To'] = to_email
    
    body = f"Olá {username},\n\nSua senha foi redefinida.\n\nAqui está a sua nova senha temporária: {temp_password}\n\nPor favor, faça o login no sistema com essa senha.\n\nAtenciosamente,\nLocamotos."
    msg.set_content(body)
    
    try:
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True, "Email enviado com sucesso."
    except Exception as e:
        return False, f"Erro ao enviar email: {str(e)}"
