import os
import time
import json
import requests
from datetime import datetime
from flask import Flask
import threading

# ========================================
# CONFIGURAÇÃO DO FLASK (Para Health Check)
# ========================================
app = Flask(__name__)

@app.route('/')
def health_check():
    return {
        'status': 'online', 
        'service': 'Pipefy Automation',
        'timestamp': datetime.now().isoformat(),
        'message': 'Automação rodando 24/7'
    }

@app.route('/health')
def health():
    return {'status': 'healthy', 'time': datetime.now().isoformat()}

def start_flask():
    """Inicia o Flask em porta aleatória para o Render"""
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Servidor health check iniciado na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Inicia Flask em thread separada
flask_thread = threading.Thread(target=start_flask, daemon=True)
flask_thread.start()

# ========================================
# SUA AUTOMAÇÃO PIPEFY (Código Otimizado)
# ========================================

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
              updatedAt
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

def mapear_campos_pipefy():
    """Mapeia os campos correspondentes entre as pipes."""
    # ADAPTAR ESTES MAPEAMENTOS CONFORME SUAS PIPES
    return {
        # Exemplo: "id_do_campo_origem": "id_do_campo_destino"
        "email": "email",
        "telefone": "phone_number",
        "nome": "name",
        "descricao": "description"
    }

def criar_card_destino(card_node):
    """Cria um card no destino copiando todos os campos."""
    card = card_node["node"]
    titulo_seguro = card["title"].replace('"', '\\"')
    
    # Prepara os campos para copiar
    fields_attributes = []
    mapeamento_campos = mapear_campos_pipefy()
    
    for field in card.get("fields", []):
        field_name = field["name"].lower().replace(" ", "_")
        field_value = field["value"]
        
        # Só copia campos com valor e que existem no mapeamento
        if (field_value not in [None, "", "null", []] and 
            field_name in mapeamento_campos.values()):
            
            fields_attributes.append({
                "field_id": field["field"]["id"],
                "field_value": str(field_value)
            })
    
    # Adiciona campos obrigatórios se necessário (evita rascunhos)
    # ADAPTE ESTES CAMPOS CONFORME SUA PIPE DESTINO
    campos_obrigatorios = [
        # Exemplo: {"field_id": "campo_obrigatorio_id", "field_value": "Valor padrão"}
    ]
    
    fields_attributes.extend(campos_obrigatorios)
    
    # Converte para formato GraphQL
    if fields_attributes:
        fields_str = json.dumps(fields_attributes).replace('"', '')
    else:
        fields_str = "[]"

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
          fields {{
            name
            value
          }}
        }}
        success
      }}
    }}
    """
    
    try:
        res = requests.post(url, json={"query": query_cria}, headers=headers)
        data = res.json()

        if "errors" in data:
            print("❌ Erro ao criar card:", data["errors"])
            # Log detalhado para debugging
            print("Query enviada:", query_cria)
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
    
    ids_copiados = carregar_ids_copiados()
    cards = buscar_cards_novos()
    novos_cards = 0

    for edge in cards:
        card = edge["node"]
        card_id = card["id"]

        if card_id not in ids_copiados:
            print(f"🔄 Processando card: {card['title']}")
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

def main_loop():
    """Loop principal da automação."""
    print("🚀 Iniciando automação Pipefy no Render")
    print(f"📍 Fase Origem: {PHASE_ID_ORIGEM}")
    print(f"📍 Fase Destino: {PHASE_ID_DESTINO}")
    print(f"⏰ Intervalo: {INTERVALO_MINUTOS} minutos")
    
    # Verifica se as variáveis de ambiente estão configuradas
    if not TOKEN:
        print("❌ Erro: Variável de ambiente PIPEFY_TOKEN não configurada")
        return
    
    while True:
        try:
            executar_automacao()
            print(f"⏳ Próxima verificação em {INTERVALO_MINUTOS} minutos...")
            time.sleep(INTERVALO_MINUTOS * 60)
        except KeyboardInterrupt:
            print("🛑 Automação interrompida pelo usuário")
            break
        except Exception as e:
            print(f"💥 Erro inesperado: {e}")
            time.sleep(60)  # Espera 1 minuto antes de continuar

# ========================================
# INICIALIZAÇÃO
# ========================================
if __name__ == "__main__":
    print("🌐 Iniciando servidor health check...")
    print("🤖 Iniciando automação Pipefy...")
    
    # Inicia a automação em thread separada
    automation_thread = threading.Thread(target=main_loop, daemon=True)
    automation_thread.start()
    
    # Mantém o script vivo
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("👋 Encerrando aplicação")
