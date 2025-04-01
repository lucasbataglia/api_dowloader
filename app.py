import os
import sys
import requests
import random
import re # Importa regex para checar URL do YouTube
import yt_dlp # Importa yt-dlp
from flask import Flask, request, jsonify, send_from_directory, url_for
from urllib.parse import unquote, urlparse

app = Flask(__name__)

# --- Bloco para determinar IP de Saída ---
try:
    print("DEBUG: Tentando determinar o IP de saída...")
    # Usa um timeout razoável para a chamada externa
    ip_response = requests.get('https://api.ipify.org?format=json', timeout=10)
    ip_response.raise_for_status() # Verifica se houve erro na requisição HTTP
    public_ip = ip_response.json().get('ip')
    print(f"############################################")
    print(f"DEBUG: IP de Saída Detectado (Render): {public_ip}")
    print(f"############################################")
except Exception as e:
    print(f"DEBUG: Não foi possível determinar o IP de Saída: {e}")
# --- Fim Bloco IP de Saída ---

DOWNLOAD_FOLDER = 'downloads'
# Lê o caminho do arquivo de proxy da variável de ambiente, com um fallback local
PROXY_FILE_PATH = os.environ.get('PROXY_FILE_PATH', 'webshare 50 proxies.txt') # Fallback com espaço
print(f"DEBUG: Caminho do arquivo de proxy determinado: {PROXY_FILE_PATH}") # Add debug print
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
                    # Formato esperado: user:pwd@host:port
                    match = re.match(r"([^:]+):([^@]+)@([^:]+):(\d+)", line)
                    if match:
                        user, pwd, host, port = match.groups()
                        proxy_url = f"http://{user}:{pwd}@{host}:{port}"
                        loaded_proxies.append(proxy_url)
                    else:
                        # Tenta formato alternativo ou loga erro
                        if '@' in line and ':' in line: # Verifica se parece um proxy
                             # Assume http://proxy_string se não corresponder ao formato user:pwd@host:port
                             # Isso pode ser útil para proxies sem autenticação ou formatos diferentes
                             # Mas para webshare, o formato acima é o esperado.
                             # Considerar logar um aviso mais específico se o formato for inesperado.
                             print(f"Formato de proxy não reconhecido automaticamente, tentando usar como está: {line}")
                             # Poderia adicionar 'http://' + line aqui se quisesse tentar usá-lo diretamente
                             # loaded_proxies.append(f"http://{line}") # Descomente se quiser tentar usar formatos desconhecidos
                        else:
                            print(f"Formato inválido ou linha não reconhecida como proxy: {line}")

        print(f"Carregados {len(loaded_proxies)} proxies de {filename}")
        return loaded_proxies
    except FileNotFoundError:
        print(f"Erro: Arquivo de proxy '{filename}' não encontrado.")
        return []
    except Exception as e:
        print(f"Erro ao ler arquivo de proxy '{filename}': {e}")
        return []

proxies_list = load_proxies(PROXY_FILE_PATH)
# --- Fim Carregamento dos Proxies ---

# --- Funções Auxiliares ---
def sanitize_filename(filename):
    """Remove caracteres inválidos e limita o tamanho do nome do arquivo."""
    sanitized = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
    return sanitized[:200]

def is_youtube_url(url):
    """Verifica se a URL pertence ao YouTube."""
    # Usando raw string (r"...") para evitar SyntaxWarning com escapes
    youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    return re.match(youtube_regex, url)

def get_unique_filepath(directory, filename):
    """Gera um caminho de arquivo único no diretório, adicionando sufixo se necessário."""
    output_path = os.path.join(directory, filename)
    counter = 1
    base_name, extension = os.path.splitext(filename)
    while os.path.exists(output_path):
        filename = f"{base_name}_{counter}{extension}"
        output_path = os.path.join(directory, filename)
        counter += 1
    return output_path, filename
# --- Fim Funções Auxiliares ---


@app.route('/download', methods=['POST'])
def download_file():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL não fornecida no corpo da requisição JSON"}), 400

    url = data['url']

    if is_youtube_url(url):
        # --- Lógica de Download do YouTube com yt-dlp ---
        print(f"URL detectada como YouTube: {url}")
        # Define um nome de arquivo temporário baseado no ID do vídeo (yt-dlp renomeará)
        # Usamos 'NA' como placeholder para o nome final que yt-dlp definirá
        temp_filename_base = "youtube_audio"
        output_template = os.path.join(DOWNLOAD_FOLDER, f'{temp_filename_base}.%(ext)s')

        ydl_opts = {
            'format': 'bestaudio/best', # Baixa o melhor áudio
            'outtmpl': output_template, # Template de saída inicial
            'noplaylist': True, # Não baixa playlists inteiras
            'postprocessors': [{ # Garante que seja um formato de áudio comum (ex: mp3)
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192', # Qualidade do MP3
            }],
            'quiet': True, # Suprime a maioria dos logs do yt-dlp
            'no_warnings': True,
            'noprogress': True,
            # Adicionar configuração de proxy se necessário para yt-dlp
            'proxy': random.choice(proxies_list) if proxies_list else None, # Usa um proxy aleatório da lista
        }

        final_filename = None
        try:
            print("Iniciando download com yt-dlp...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                # yt-dlp já salvou o arquivo com o nome correto baseado no título + ID + extensão final (mp3)
                # Precisamos descobrir qual foi esse nome.
                # O nome do arquivo final estará em info_dict após o download e pós-processamento.
                # No entanto, o nome exato pode variar. Uma forma mais segura é listar o diretório
                # ou usar hooks, mas vamos tentar pegar do info_dict primeiro.
                # O nome do arquivo pós-processado pode não estar diretamente no info_dict principal.
                # Vamos usar o título e a extensão esperada (mp3).
                base_filename = ydl.prepare_filename(info_dict)
                # Remove a extensão original e adiciona a extensão do pós-processador (mp3)
                final_filename_base, _ = os.path.splitext(base_filename)
                final_filename = f"{os.path.basename(final_filename_base)}.mp3"
                final_filepath = os.path.join(DOWNLOAD_FOLDER, final_filename)

                # Verifica se o arquivo final realmente existe
                if not os.path.exists(final_filepath):
                     # Fallback: tenta encontrar o arquivo mp3 mais recente na pasta
                     print(f"WARN: Arquivo esperado {final_filename} não encontrado diretamente. Tentando localizar...")
                     list_of_files = [os.path.join(DOWNLOAD_FOLDER, f) for f in os.listdir(DOWNLOAD_FOLDER) if f.endswith('.mp3')]
                     if list_of_files:
                         latest_file = max(list_of_files, key=os.path.getctime)
                         final_filename = os.path.basename(latest_file)
                         print(f"INFO: Arquivo localizado: {final_filename}")
                     else:
                         raise FileNotFoundError("Não foi possível localizar o arquivo MP3 baixado.")

            print(f"Download do YouTube concluído para: {final_filename}")
            file_url = url_for('serve_file', filename=final_filename, _external=True)
            return jsonify({"download_link": file_url})

        except yt_dlp.utils.DownloadError as dl_err:
            print(f"Erro de Download do yt-dlp: {dl_err}")
            # Tenta remover arquivo parcial se existir
            if final_filename and os.path.exists(os.path.join(DOWNLOAD_FOLDER, final_filename)):
                 try: os.remove(os.path.join(DOWNLOAD_FOLDER, final_filename))
                 except OSError: pass
            return jsonify({"error": f"Erro ao baixar do YouTube: {dl_err}"}), 500
        except Exception as e:
            print(f"Erro inesperado no processamento do YouTube: {e}")
            if final_filename and os.path.exists(os.path.join(DOWNLOAD_FOLDER, final_filename)):
                 try: os.remove(os.path.join(DOWNLOAD_FOLDER, final_filename))
                 except OSError: pass
            return jsonify({"error": f"Erro inesperado no servidor: {e}"}), 500
        # --- Fim Lógica YouTube ---

    else:
        # --- Lógica de Download Genérico com Requests e Proxies ---
        print(f"URL não detectada como YouTube, usando download genérico: {url}")
        output_filename_base = sanitize_filename(urlparse(url).path.split('/')[-1] or "downloaded_file")
        if '.' not in output_filename_base:
             output_filename_base += ".mp3" # Ou outra extensão padrão

        # Garante um nome de arquivo único
        output_path, output_filename = get_unique_filepath(DOWNLOAD_FOLDER, output_filename_base)

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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
        }

        max_retries = 3
        available_proxies = list(proxies_list)
        last_error = None

        for attempt in range(max_retries):
            selected_proxy_url = None
            proxies_config = None
            if available_proxies:
                selected_proxy_url = random.choice(available_proxies)
                available_proxies.remove(selected_proxy_url)
                proxies_config = {"http": selected_proxy_url, "https": selected_proxy_url}
                print(f"Tentativa {attempt + 1}/{max_retries}. Usando proxy: {selected_proxy_url.split('@')[1] if '@' in selected_proxy_url else selected_proxy_url}")
            elif proxies_list:
                 print(f"Tentativa {attempt + 1}/{max_retries}. Esgotados proxies disponíveis. Tentando sem proxy.")
            else:
                print(f"Tentativa {attempt + 1}/{max_retries}. Nenhuma lista de proxies carregada. Tentando sem proxy.")
                if attempt > 0: break

            try:
                print(f"Tentando baixar de: {url}")
                response = requests.get(url, headers=headers, stream=True, timeout=30, proxies=proxies_config)
                response.raise_for_status()

                total_size = response.headers.get('content-length')
                print(f"Salvando como: {output_filename}")
                with open(output_path, 'wb') as f:
                    if total_size is None:
                        print("Baixando (tamanho desconhecido)...")
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    else:
                        total_size = int(total_size)
                        downloaded_size = 0
                        print(f"Baixando (Tamanho total: {total_size / (1024*1024):.2f} MB)...")
                        for chunk in response.iter_content(chunk_size=8192):
                             if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                if downloaded_size % (1024*1024) < 8192:
                                    progress = (downloaded_size / total_size) * 100
                                    print(f"Progresso: {downloaded_size / (1024*1024):.2f} MB / {total_size / (1024*1024):.2f} MB ({progress:.1f}%)")

                print(f"\nDownload concluído para: {output_filename}")
                file_url = url_for('serve_file', filename=output_filename, _external=True)
                return jsonify({"download_link": file_url})

            except requests.exceptions.HTTPError as http_err:
                print(f"Tentativa {attempt + 1} falhou com Erro HTTP: {http_err}")
                last_error = http_err
                if http_err.response.status_code not in (403, 404) and not (500 <= http_err.response.status_code < 600):
                    break
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as conn_timeout_err:
                print(f"Tentativa {attempt + 1} falhou com Erro de Conexão/Timeout: {conn_timeout_err}")
                last_error = conn_timeout_err
            except requests.exceptions.RequestException as req_err:
                print(f"Tentativa {attempt + 1} falhou com Erro Geral na Requisição: {req_err}")
                last_error = req_err
                break
            except Exception as e:
                 print(f"Tentativa {attempt + 1} falhou com Erro Inesperado: {e}")
                 last_error = e
                 if os.path.exists(output_path):
                     try: os.remove(output_path)
                     except OSError: pass
                 break

        print(f"Todas as {max_retries} tentativas falharam.")
        if os.path.exists(output_path):
            try: os.remove(output_path)
            except OSError: pass

        if isinstance(last_error, requests.exceptions.HTTPError):
            return jsonify({"error": f"Erro HTTP após {max_retries} tentativas: {last_error.response.status_code}"}), 502
        elif isinstance(last_error, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
             return jsonify({"error": f"Erro de Conexão/Timeout após {max_retries} tentativas"}), 504
        elif isinstance(last_error, requests.exceptions.RequestException):
             return jsonify({"error": f"Erro na requisição após {max_retries} tentativas: {last_error}"}), 500
        else:
            return jsonify({"error": f"Erro inesperado no servidor após {max_retries} tentativas: {last_error}"}), 500
        # --- Fim Lógica Genérica ---

@app.route('/files/<path:filename>')
def serve_file(filename):
    """Serve os arquivos baixados do diretório DOWNLOAD_FOLDER."""
    print(f"Tentando servir o arquivo: {filename}")
    try:
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    except FileNotFoundError:
         print(f"Arquivo não encontrado: {filename}")
         return jsonify({"error": "Arquivo não encontrado"}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
