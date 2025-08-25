import time
import json
import os
import requests

# Configurações (usando variáveis de ambiente)
TOKEN = os.environ["PIPEFY_TOKEN"]           # Vamos colocar no Render
PHASE_ID_ORIGEM = 339844827                  # Fase do Pipe A
PHASE_ID_DESTINO = 339844842                 # Fase do Pipe B
PIPE_ID_DESTINO = 306600600                 # Pipe do Pipe B
INTERVALO_MINUTOS = 5                        # Tempo entre verificações
ARQUIVO_IDS = "cards_copiados.json"

# URL corrigida (sem espaços no final!)
url = "https://api.pipefy.com/graphql"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Carrega histórico de IDs já copiados
if os.path.exists(ARQUIVO_IDS):
    with open(ARQUIVO_IDS, "r") as f:
        ids_copiados = set(json.load(f))
else:
    ids_copiados = set()

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
        res.raise_for_status()
        data = res.json()

        if "errors" in data:
            print("❌ Erro na busca:", data["errors"])
            return []

        return data["data"]["phase"]["cards"]["edges"]
    except Exception as e:
        print("❌ Falha na conexão:", e)
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
        res.raise_for_status()
        data = res.json()

        if "errors" in data:
            print("❌ Erro ao criar card:", data["errors"])
        else:
            print("✅ Card criado:", data["data"]["createCard"]["card"]["title"])
    except Exception as e:
        print("❌ Falha ao criar card:", e)

# Loop infinito
while True:
    print("🔍 Verificando novos cards...")
    cards = buscar_cards_novos()

    for edge in cards:
        card = edge["node"]
        card_id = card["id"]

        if card_id not in ids_copiados:
            criar_card_destino(card["title"])
            ids_copiados.add(card_id)

            # Salva o histórico
            with open(ARQUIVO_IDS, "w") as f:
                json.dump(list(ids_copiados), f)

    print(f"⏳ Aguardando {INTERVALO_MINUTOS} minutos...")
    time.sleep(INTERVALO_MINUTOS * 60)