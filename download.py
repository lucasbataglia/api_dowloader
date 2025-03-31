import requests
import sys

url = 'https://beta.123tokyo.xyz/get.php/2/55/cswHBeqNGt0.mp3?n=Introdu%C3%A7%C3%A3o%20Pr%C3%A1tica%20ao%20ChatGPT%20para%20Iniciantes&uT=R&uN=Y29udGFzLThHcDNxQ1Fmcg%3D%3D&h=Mp7z4QgwP-L9nhGZDn_-yw&s=1743430596&uT=R&uN=Y29udGFzLThHcDNxQ1Fmcg%3D%3D'

output_filename = "downloaded_audio.mp3"
try:
    from urllib.parse import unquote
    query_params = dict(qc.split("=") for qc in url.split("?")[-1].split("&"))
    if 'n' in query_params:
        decoded_name = unquote(query_params['n'])
        if not decoded_name.lower().endswith('.mp3'):
            output_filename = f"{decoded_name}.mp3"
        else:
            output_filename = decoded_name
        output_filename = "".join(c for c in output_filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
except Exception:
    print("Não foi possível extrair o nome do arquivo da URL, usando 'downloaded_audio.mp3'")
    output_filename = "downloaded_audio.mp3"

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
}

print(f"Tentando baixar de: {url}")
print(f"Salvando como: {output_filename}")

try:
    response = requests.get(url, headers=headers, stream=True, timeout=300)

    response.raise_for_status()

    total_size = response.headers.get('content-length')

    with open(output_filename, 'wb') as f:
        if total_size is None:
            print("Baixando (tamanho desconhecido)...")
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        else:
            total_size = int(total_size)
            downloaded_size = 0
            print(f"Baixando (Tamanho total: {total_size / (1024*1024):.2f} MB)...")
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded_size += len(chunk)
                if downloaded_size % (1024*1024) < 8192:
                     progress = (downloaded_size / total_size) * 100
                     sys.stdout.write(f"\rProgresso: {downloaded_size / (1024*1024):.2f} MB / {total_size / (1024*1024):.2f} MB ({progress:.1f}%)")
                     sys.stdout.flush()
            print("\nDownload concluído!")

except requests.exceptions.HTTPError as http_err:
    print(f"Erro HTTP: {http_err}")
    print(f"Status Code: {http_err.response.status_code}")
except requests.exceptions.ConnectionError as conn_err:
    print(f"Erro de Conexão: {conn_err}")
except requests.exceptions.Timeout as timeout_err:
    print(f"Erro: Timeout da requisição: {timeout_err}")
except requests.exceptions.RequestException as req_err:
    print(f"Erro geral na requisição: {req_err}")
except Exception as e:
    print(f"Ocorreu um erro inesperado: {e}")
