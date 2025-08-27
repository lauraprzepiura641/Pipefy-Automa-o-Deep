import os
import time
import json
import requests
from datetime import datetime

# ========================================
# CONFIGURAÇÕES
# ========================================
TOKEN = os.environ.get('PIPEFY_TOKEN')
PHASE_ID_ORIGEM = int(os.environ.get('PHASE_ID_ORIGEM', 339844827))
PHASE_ID_DESTINO = int(os.environ.get('PHASE_ID_DESTINO', 339844842))
PIPE_ID_DESTINO = int(os.environ.get('PIPE_ID_DESTINO', 306600600))

# Arquivo onde vamos salvar os IDs já copiados
ARQUIVO_IDS = "cards_copiados.json"

url = "https://api.pipefy.com/graphql"
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# ========================================
# FUNÇÕES PRINCIPAIS
# ========================================

def carregar_ids_copiados():
    """Carrega os IDs já copiados."""
    try:
        if os.path.exists(ARQUIVO_IDS):
            with open(ARQUIVO_IDS, "r") as f:
                return set(json.load(f))
    except Exception as e:
        print(f"⚠️ Erro ao carregar IDs: {e}")
    return set()

def salvar_ids_copiados(ids):
    """Salva os IDs copiados."""
    try:
        with open(ARQUIVO_IDS, "w") as f:
            json.dump(list(ids), f)
        print(f"💾 Histórico salvo: {len(ids)} cards copiados")
    except Exception as e:
        print(f"❌ Erro ao salvar IDs: {e}")

def buscar_cards_novos():
    """Busca os cards na fase de origem com todos os campos."""
    query_busca = f"""
    query {{
      phase(id: {PHASE_ID_ORIGEM}) {{
        cards(first: 50) {{
          edges {{
            node {{
              id
              title
              fields {{
                name
                value
                field {{
                  id
                  internal_id
                }}
              }}
              createdAt
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
            print("❌ Erro na busca:", data["errors"])
            return []

        cards = data["data"]["phase"]["cards"]["edges"]
        print(f"📊 {len(cards)} cards encontrados na fase origem")
        return cards

    except Exception as e:
        print(f"❌ Erro ao buscar cards: {e}")
        return []

def criar_card_destino(card_node):
    """Cria um card no destino copiando todos os campos."""
    card = card_node["node"]
    titulo_seguro = card["title"].replace('"', '\\"')
    
    print(f"🔄 Processando: {card['title']}")
    
    # Prepara os campos para copiar
    fields_attributes = []
    
    for field in card.get("fields", []):
        field_name = field["name"].lower().replace(" ", "_")
        field_value = field["value"]
        
        # Só copia campos com valor
        if field_value not in [None, "", "null", []]:
            fields_attributes.append({
                "field_id": field["field"]["id"],
                "field_value": str(field_value)
            })
    
    # Converte para formato GraphQL
    if fields_attributes:
        fields_str = json.dumps(fields_attributes).replace('"', '')
        print(f"   📋 {len(fields_attributes)} campos para copiar")
    else:
        fields_str = "[]"
        print("   ℹ️ Nenhum campo para copiar")

    query_cria = f"""
    mutation {{
      createCard(
        input: {{
          pipe_id: {PIPE_ID_DESTINO},
          phase_id: {PHASE_ID_DESTINO},
          title: "{titulo_seguro}",
          fields_attributes: {fields_str}
        }}
      ) {{
        card {{
          id
          title
          url
          current_phase {{ name }}
        }}
      }}
    }}
    """
    
    try:
        res = requests.post(url, json={"query": query_cria}, headers=headers)
        data = res.json()

        if "errors" in data:
            print(f"❌ Erro ao criar card '{card['title']}':", data["errors"])
            return False
        else:
            card_criado = data["data"]["createCard"]["card"]
            print(f"✅ Card criado: {card_criado['title']}")
            print(f"   📎 URL: {card_criado['url']}")
            return True
            
    except Exception as e:
        print(f"❌ Erro ao criar card: {e}")
        return False

def executar_automacao():
    """Executa uma iteração da automação."""
    print(f"🔍 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Verificando novos cards...")
    print(f"📍 Fase Origem: {PHASE_ID_ORIGEM}")
    print(f"📍 Fase Destino: {PHASE_ID_DESTINO}")
    
    ids_copiados = carregar_ids_copiados()
    cards = buscar_cards_novos()
    novos_cards = 0

    for edge in cards:
        card = edge["node"]
        card_id = card["id"]

        if card_id not in ids_copiados:
            sucesso = criar_card_destino(edge)
            if sucesso:
                ids_copiados.add(card_id)
                novos_cards += 1
                # Pequena pausa entre cards para evitar rate limit
                time.sleep(1)

    if novos_cards > 0:
        salvar_ids_copiados(ids_copiados)
        print(f"🎉 {novos_cards} novo(s) card(s) copiado(s) com sucesso!")
    else:
        print("ℹ️ Nenhum novo card para copiar")
    
    return novos_cards

# ========================================
# EXECUÇÃO PRINCIPAL
# ========================================

def main():
    """Função principal executada a cada 5 minutos."""
    print("=" * 50)
    print("🚀 INICIANDO AUTOMAÇÃO PIPEFY")
    print("=" * 50)
    
    # Verifica se as variáveis de ambiente estão configuradas
    if not TOKEN:
        print("❌ ERRO: Variável PIPEFY_TOKEN não configurada")
        print("💡 Configure no GitHub: Settings → Secrets → Actions")
        return
    
    try:
        total_copiados = executar_automacao()
        print("=" * 50)
        print(f"✅ AUTOMAÇÃO CONCLUÍDA: {total_copiados} cards processados")
        print(f"⏰ Próxima execução: ~5 minutos")
        print("=" * 50)
        
    except Exception as e:
        print(f"💥 ERRO NA AUTOMAÇÃO: {e}")
        print("=" * 50)

if __name__ == "__main__":
    main()
