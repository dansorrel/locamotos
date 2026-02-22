import pandas as pd
from datetime import datetime

def generate_ofx(transactions_df, mes_referencia):
    """
    Generates an OFX format string from a DataFrame of transactions.
    transactions_df must have: 'Data', 'Tipo', 'Valor', 'Origem', 'Placa da Moto'
    """
    agora = datetime.now().strftime("%Y%m%d%H%M%S")
    
    ofx_lines = [
        "OFXHEADER:100",
        "DATA:OFXSGML",
        "VERSION:102",
        "SECURITY:NONE",
        "ENCODING:UTF-8",
        "CHARSET:NONE",
        "COMPRESSION:NONE",
        "OLDFILEUID:NONE",
        "NEWFILEUID:NONE",
        "",
        "<OFX>",
        "  <SIGNONMSGSRSV1>",
        "    <SONRS>",
        "      <STATUS>",
        "        <CODE>0</CODE>",
        "        <SEVERITY>INFO</SEVERITY>",
        "      </STATUS>",
        f"      <DTSERVER>{agora}</DTSERVER>",
        "      <LANGUAGE>POR</LANGUAGE>",
        "    </SONRS>",
        "  </SIGNONMSGSRSV1>",
        "  <BANKMSGSRSV1>",
        "    <STMTTRNRS>",
        "      <TRNUID>1001</TRNUID>",
        "      <STATUS>",
        "        <CODE>0</CODE>",
        "        <SEVERITY>INFO</SEVERITY>",
        "      </STATUS>",
        "      <STMTRS>",
        "        <CURDEF>BRL</CURDEF>",
        "        <BANKACCTFROM>",
        "          <BANKID>Locamotos</BANKID>",
        "          <ACCTID>1</ACCTID>",
        "          <ACCTTYPE>CHECKING</ACCTTYPE>",
        "        </BANKACCTFROM>",
        "        <BANKTRANLIST>",
        # Let's declare start and end date based on reference month. Simplified for now.
        f"          <DTSTART>{agora[:8]}</DTSTART>",
        f"          <DTEND>{agora[:8]}</DTEND>"
    ]
    
    for idx, row in transactions_df.iterrows():
        # format date YYYYMMDD
        dt_trans = row['Data'].strftime("%Y%m%d120000")
        
        # Determine sign and type
        if row['Tipo'] in ('entrada', 'entrada_liquida'):
            trn_type = "CREDIT"
            val = abs(row['Valor'])
        else:
            trn_type = "DEBIT"
            val = -abs(row['Valor'])
            
        memo = f"{row['Origem']} - Moto: {row.get('Placa da Moto', 'N/A')}"
            
        ofx_lines.extend([
            "          <STMTTRN>",
            f"            <TRNTYPE>{trn_type}</TRNTYPE>",
            f"            <DTPOSTED>{dt_trans}</DTPOSTED>",
            f"            <TRNAMT>{val:.2f}</TRNAMT>",
            f"            <FITID>{idx}{dt_trans}</FITID>",
            f"            <MEMO>{memo}</MEMO>",
            "          </STMTTRN>"
        ])
        
    ofx_lines.extend([
        "        </BANKTRANLIST>",
        "        <LEDGERBAL>",
        "          <BALAMT>0.00</BALAMT>",
        f"          <DTASOF>{agora}</DTASOF>",
        "        </LEDGERBAL>",
        "      </STMTRS>",
        "    </STMTTRNRS>",
        "  </BANKMSGSRSV1>",
        "</OFX>"
    ])
    
    return "\n".join(ofx_lines)

def generate_csv_summary(transactions_df):
    """
    Returns the DataFrame exported as a CSV string,
    acting as the replacement for a PDF summary for easier integration.
    """
    return transactions_df.to_csv(index=False)
