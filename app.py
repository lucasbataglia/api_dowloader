import os
import sys
import requests
import random # Importa o módulo random
from flask import Flask, request, jsonify, send_from_directory, url_for
from urllib.parse import unquote, urlparse

app = Flask(__name__)
DOWNLOAD_FOLDER = 'downloads'
PROXY_FILE = 'webshare_50_proxies.txt'
proxies_list = []

# Garante que o diretório de downloads exista
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# --- Carregamento dos Proxies ---
def load_proxies(filename):
    """Lê o arquivo de proxies e formata para uso com requests."""
    loaded_proxies = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split(':')
                    if len(parts) == 4:
                        ip, port, user, pwd = parts
                        # Formato: http://usuario:senha@host:porta
                        proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
                        loaded_proxies.append(proxy_url)
                    else:
                        print(f"Formato inválido na linha do proxy: {line}")
        print(f"Carregados {len(loaded_proxies)} proxies de {filename}")
        return loaded_proxies
    except FileNotFoundError:
        print(f"Erro: Arquivo de proxy '{filename}' não encontrado.")
        return []
    except Exception as e:
        print(f"Erro ao ler arquivo de proxy '{filename}': {e}")
        return []

# Carrega os proxies na inicialização da aplicação
proxies_list = load_proxies(PROXY_FILE)
# --- Fim Carregamento dos Proxies ---


def sanitize_filename(filename):
    """Remove caracteres inválidos e limita o tamanho do nome do arquivo."""
    # Remove caracteres potencialmente perigosos ou inválidos em nomes de arquivo
    sanitized = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
    # Limita o comprimento para evitar nomes de arquivo excessivamente longos
    return sanitized[:200] # Limita a 200 caracteres

def extract_filename_from_url(url):
    """Tenta extrair um nome de arquivo significativo da URL."""
    try:
        parsed_url = urlparse(url)
        path_filename = os.path.basename(parsed_url.path)

        # Tenta extrair do parâmetro 'n' como no script original
        query_params = dict(qc.split("=") for qc in parsed_url.query.split("&") if "=" in qc)
        if 'n' in query_params:
            decoded_name = unquote(query_params['n'])
            # Adiciona .mp3 se não tiver, como no script original
            if not decoded_name.lower().endswith(('.mp3', '.mp4', '.avi', '.mkv', '.zip', '.rar')): # Adicione outras extensões comuns se necessário
                 # Tenta pegar a extensão do path se houver
                 _, ext = os.path.splitext(path_filename)
                 if ext and len(ext) <= 5: # Verifica se é uma extensão válida
                     return sanitize_filename(f"{decoded_name}{ext}")
                 else:
                     return sanitize_filename(f"{decoded_name}.mp3") # Default para mp3 se não conseguir extrair extensão
            else:
                return sanitize_filename(decoded_name)

        # Se não houver parâmetro 'n', usa o nome do arquivo no path da URL
        if path_filename:
            # Decodifica o nome do arquivo do path
            decoded_path_filename = unquote(path_filename)
            # Remove potenciais parâmetros após a extensão (ex: file.mp3?token=...)
            cleaned_filename = decoded_path_filename.split('?')[0]
            if cleaned_filename:
                 # Sanitiza antes de retornar
                 return sanitize_filename(cleaned_filename)

    except Exception as e:
        print(f"Erro ao extrair nome do arquivo da URL {url}: {e}")

    # Fallback para um nome genérico se tudo falhar
    return sanitize_filename("downloaded_file")

@app.route('/download', methods=['POST'])
def download_file():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL não fornecida no corpo da requisição JSON"}), 400

    url = data['url']
    output_filename = extract_filename_from_url(url)
    # Garante uma extensão padrão se a extração falhar completamente
    if '.' not in output_filename:
        output_filename += ".mp3" # Ou outra extensão padrão

    output_path = os.path.join(DOWNLOAD_FOLDER, output_filename)

    # Evita sobrescrever arquivos existentes adicionando um sufixo numérico
    counter = 1
    base_name, extension = os.path.splitext(output_filename)
    while os.path.exists(output_path):
        output_filename = f"{base_name}_{counter}{extension}"
        output_path = os.path.join(DOWNLOAD_FOLDER, output_filename)
        counter += 1

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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36', # User agent do script original
    }

    # --- Seleção do Proxy ---
    selected_proxy_url = None
    proxies_config = None
    if proxies_list:
        selected_proxy_url = random.choice(proxies_list)
        proxies_config = {
            "http": selected_proxy_url,
            "https": selected_proxy_url,
        }
        print(f"Usando proxy selecionado: {selected_proxy_url.split('@')[1] if '@' in selected_proxy_url else selected_proxy_url}") # Não logar credenciais
    else:
        print("Nenhuma lista de proxies carregada. Tentando sem proxy.")
    # --- Fim Seleção do Proxy ---

    try:
        print(f"Tentando baixar de: {url}")
        print(f"Salvando como: {output_filename}")
        # Adiciona o parâmetro 'proxies' à requisição com o proxy selecionado
        response = requests.get(url, headers=headers, stream=True, timeout=300, proxies=proxies_config) # Timeout de 5 minutos
        response.raise_for_status() # Verifica se houve erro HTTP (status code >= 400)

        total_size = response.headers.get('content-length')

        with open(output_path, 'wb') as f:
            if total_size is None:
                print("Baixando (tamanho desconhecido)...")
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk: # Filtra keep-alive new chunks
                        f.write(chunk)
            else:
                total_size = int(total_size)
                downloaded_size = 0
                print(f"Baixando (Tamanho total: {total_size / (1024*1024):.2f} MB)...")
                for chunk in response.iter_content(chunk_size=8192):
                     if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        # Atualiza o progresso a cada MB baixado para não sobrecarregar o log
                        if downloaded_size % (1024*1024) < 8192:
                            progress = (downloaded_size / total_size) * 100
                            # Usando print em vez de sys.stdout.write para simplificar no contexto do servidor
                            print(f"Progresso: {downloaded_size / (1024*1024):.2f} MB / {total_size / (1024*1024):.2f} MB ({progress:.1f}%)")

        print(f"\nDownload concluído para: {output_filename}")
        # Gera a URL pública para o arquivo baixado
        # _external=True gera a URL absoluta (ex: http://127.0.0.1:5000/files/...)
        file_url = url_for('serve_file', filename=output_filename, _external=True)
        return jsonify({"download_link": file_url})

    except requests.exceptions.HTTPError as http_err:
        print(f"Erro HTTP ao baixar {url}: {http_err}")
        return jsonify({"error": f"Erro HTTP: {http_err.response.status_code}"}), 502 # Bad Gateway
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Erro de Conexão ao baixar {url}: {conn_err}")
        return jsonify({"error": "Erro de conexão ao tentar baixar o arquivo"}), 502
    except requests.exceptions.Timeout as timeout_err:
        print(f"Timeout ao baixar {url}: {timeout_err}")
        return jsonify({"error": "Timeout ao tentar baixar o arquivo"}), 504 # Gateway Timeout
    except requests.exceptions.RequestException as req_err:
        print(f"Erro geral na requisição ao baixar {url}: {req_err}")
        return jsonify({"error": f"Erro na requisição: {req_err}"}), 500
    except Exception as e:
        print(f"Erro inesperado ao processar {url}: {e}")
        # Remove o arquivo parcialmente baixado em caso de erro inesperado
        if os.path.exists(output_path):
            os.remove(output_path)
        return jsonify({"error": f"Ocorreu um erro inesperado no servidor: {e}"}), 500

@app.route('/files/<path:filename>')
def serve_file(filename):
    """Serve os arquivos baixados do diretório DOWNLOAD_FOLDER."""
    print(f"Tentando servir o arquivo: {filename}")
    try:
        # send_from_directory lida com segurança de caminho
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    except FileNotFoundError:
         print(f"Arquivo não encontrado: {filename}")
         return jsonify({"error": "Arquivo não encontrado"}), 404

if __name__ == '__main__':
    # Roda o servidor Flask. debug=True é útil para desenvolvimento.
    # host='0.0.0.0' torna o servidor acessível na rede local.
    # Mudando para a porta 5001 para evitar conflito
    app.run(debug=True, host='0.0.0.0', port=5001)
