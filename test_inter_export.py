import sys
from inter_client import InterClient

def test():
    client = InterClient()
    client.get_token()
    
    import requests
    url = f"{client.base_url}/banking/v2/extrato/exportar"
    headers = {"Authorization": f"Bearer {client.access_token}"}
    
    params_ofx = {"dataInicio": "2026-02-01", "dataFim": "2026-02-22", "tipoArquivo": "OFX"}
    res_ofx = requests.get(url, headers=headers, params=params_ofx, cert=(client.cert_path, client.key_path))
    print("OFX Status:", res_ofx.status_code)
    try:
         print("OFX Keys:", res_ofx.json().keys())
    except:
         print("No JSON, raw text len:", len(res_ofx.text))

if __name__ == '__main__':
    test()
