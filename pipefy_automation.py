import os
from flask import Flask
import threading
from datetime import datetime

# Cria app Flask
app = Flask(__name__)

@app.route('/')
def health_check():
    return {
        'status': 'online', 
        'service': 'Pipefy Automation',
        'timestamp': datetime.now().isoformat()
    }

def start_flask():
    """Inicia o Flask em porta aleatória para o Render"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Inicia Flask em thread separada
flask_thread = threading.Thread(target=start_flask, daemon=True)
flask_thread.start()

import time
import json
import requests

# Configurações (via variáveis de ambiente no Render)
TOKEN = os.environ.get('PIPEFY_TOKEN')
PHASE_ID_ORIGEM = int(os.environ.get('PHASE_ID_ORIGEM', 339844827))
PHASE_ID_DESTINO = int(os.environ.get('PHASE_ID_DESTINO', 339844842))
PIPE_ID_DESTINO = int(os.environ.get('PIPE_ID_DESTINO', 306600600))
INTERVALO_MINUTOS = int(os.environ.get('INTERVALO_MINUTOS', 5))

# Arquivo onde vamos salvar os IDs já copiados
ARQUIVO_IDS = "cards_copiados.json"

url = "https://api.pipefy.com/graphql"
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def carregar_ids_copiados():
    """Carrega os IDs já copiados."""
    try:
        if os.path.exists(ARQUIVO_IDS):
            with open(ARQUIVO_IDS, "r") as f:
                return set(json.load(f))
    except:
        pass
    return set()

def salvar_ids_copiados(ids):
    """Salva os IDs copiados."""
    try:
        with open(ARQUIVO_IDS, "w") as f:
            json.dump(list(ids), f)
    except Exception as e:
        print(f"Erro ao salvar IDs: {e}")

def buscar_cards_novos():
    """Busca os cards na fase de origem."""
    query_busca = f"""
    query {{
      phase(id: {PHASE_ID_ORIGEM}) {{
        cards(first: 50) {{
          edges {{
            node {{
              id
              title
            }}
          }}
        }}
      }}
    }}
    """
    try:
        res = requests.post(url, json={"query": query_busca}, headers=headers)
        data = res.json()

        if "errors" in data:
            print("Erro na busca:", data["errors"])
            return []

        return data["data"]["phase"]["cards"]["edges"]
    except Exception as e:
        print(f"Erro ao buscar cards: {e}")
        return []

def criar_card_destino(titulo):
    """Cria um card no destino."""
    titulo_seguro = titulo.replace('"', '\\"')

    query_cria = f"""
    mutation {{
      createCard(
        input: {{
          pipe_id: {PIPE_ID_DESTINO},
          phase_id: {PHASE_ID_DESTINO},
          title: "{titulo_seguro}"
        }}
      ) {{
        card {{
          id
          title
          current_phase {{ name }}
        }}
      }}
    }}
    """
    try:
        res = requests.post(url, json={"query": query_cria}, headers=headers)
        data = res.json()

        if "errors" in data:
            print("Erro ao criar card:", data["errors"])
            return False
        else:
            print("✅ Card criado:", data["data"]["createCard"]["card"]["title"])
            return True
    except Exception as e:
        print(f"Erro ao criar card: {e}")
        return False

def executar_automacao():
    """Executa uma iteração da automação."""
    print(f"🔍 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Verificando novos cards...")
    
    ids_copiados = carregar_ids_copiados()
    cards = buscar_cards_novos()
    novos_cards = 0

    for edge in cards:
        card = edge["node"]
        card_id = card["id"]

        if card_id not in ids_copiados:
            sucesso = criar_card_destino(card["title"])
            if sucesso:
                ids_copiados.add(card_id)
                novos_cards += 1

    if novos_cards > 0:
        salvar_ids_copiados(ids_copiados)
        print(f"✅ {novos_cards} novo(s) card(s) copiado(s)")
    else:
        print("ℹ️ Nenhum novo card para copiar")

def main_loop():
    """Loop principal da automação."""
    print("🚀 Iniciando automação Pipefy no Render")
    
    # Verifica se as variáveis de ambiente estão configuradas
    if not TOKEN:
        print("❌ Erro: Variável de ambiente PIPEFY_TOKEN não configurada")
        return
    
    while True:
        try:
            executar_automacao()
            print(f"⏳ Aguardando {INTERVALO_MINUTOS} minutos...")
            time.sleep(INTERVALO_MINUTOS * 60)
        except KeyboardInterrupt:
            print("🛑 Automação interrompida pelo usuário")
            break
        except Exception as e:
            print(f"💥 Erro inesperado: {e}")
            time.sleep(60)  # Espera 1 minuto antes de continuar

# Iniciar em thread separada para não bloquear
def start_automation():
    thread = threading.Thread(target=main_loop)
    thread.daemon = True
    thread.start()

if __name__ == "__main__":
    start_automation()
    
    # Manter o script rodando
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("👋 Encerrando aplicação")
