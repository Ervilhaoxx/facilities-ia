"""
api/chat.py
Endpoint principal do Facilities.IA.
Busca chamados reais do Pipefy via GraphQL.
"""
import json
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from datetime import datetime

import anthropic

# ─── CONFIG ───────────────────────────────────────────────────────────────────
PIPEFY_TOKEN  = os.environ.get("PIPEFY_TOKEN", "")
PIPEFY_PIPE_ID = "304316750"
PIPEFY_API    = "https://api.pipefy.com/graphql"

# ─── PIPEFY ───────────────────────────────────────────────────────────────────
def buscar_cards_pipefy(filtro_status=None):
    """Busca cards do pipe de facilities no Pipefy via GraphQL."""
    query = """
    query($pipeId: ID!) {
      pipe(id: $pipeId) {
        name
        phases {
          name
          cards_count
          cards {
            edges {
              node {
                id
                title
                createdAt
                due_date
                assignees { name }
                fields {
                  name
                  value
                }
                current_phase { name }
                labels { name color }
              }
            }
          }
        }
      }
    }
    """
    payload = json.dumps({
        "query": query,
        "variables": {"pipeId": PIPEFY_PIPE_ID}
    }).encode("utf-8")

    req = urllib.request.Request(
        PIPEFY_API,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {PIPEFY_TOKEN}"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return None, str(e)

    if "errors" in data:
        return None, str(data["errors"])

    pipe = data.get("data", {}).get("pipe", {})
    phases = pipe.get("phases", [])

    chamados = []
    for phase in phases:
        phase_name = phase.get("name", "")
        for edge in phase.get("cards", {}).get("edges", []):
            card = edge.get("node", {})
            
            # Extrai campos do card
            fields = {f["name"]: f["value"] for f in card.get("fields", []) if f.get("value")}
            
            # Mapeia status pela fase
            status = mapear_status(phase_name)
            
            # Pega prioridade dos labels ou campos
            prioridade = "media"
            for label in card.get("labels", []):
                label_name = label.get("name", "").lower()
                if "urgente" in label_name:
                    prioridade = "urgente"
                elif "alta" in label_name:
                    prioridade = "alta"
                elif "baixa" in label_name:
                    prioridade = "baixa"
            
            chamado = {
                "id":          card.get("id"),
                "protocolo":   f"FCL-{card.get('id', '?')}",
                "titulo":      card.get("title", "Sem título"),
                "status":      status,
                "fase":        phase_name,
                "prioridade":  fields.get("Prioridade", prioridade).lower() if fields.get("Prioridade") else prioridade,
                "categoria":   fields.get("Categoria", fields.get("Tipo", "Geral")),
                "solicitante": fields.get("Solicitante", fields.get("Nome", "Não informado")),
                "local":       fields.get("Local", fields.get("Andar", "")),
                "descricao":   fields.get("Descrição", fields.get("Descricao", "")),
                "data":        card.get("createdAt", "")[:10] if card.get("createdAt") else "",
                "responsavel": ", ".join(a["name"] for a in card.get("assignees", [])),
            }
            chamados.append(chamado)

    # Filtra por status se pedido
    if filtro_status and filtro_status != "todos":
        chamados = [c for c in chamados if c["status"] == filtro_status]

    return chamados, None


def mapear_status(fase_name):
    """Mapeia nome da fase do Pipefy para status padronizado."""
    fase = fase_name.lower()
    if any(x in fase for x in ["início", "inicio", "aberto", "novo", "solicitaç", "entrada"]):
        return "aberto"
    elif any(x in fase for x in ["andamento", "execução", "execucao", "em curso", "aprovação gestor"]):
        return "em_andamento"
    elif any(x in fase for x in ["concluído", "concluido", "feito", "done", "finalizado", "resolvido"]):
        return "concluido"
    elif any(x in fase for x in ["cancelado", "cancelado", "recusado"]):
        return "cancelado"
    else:
        return "aberto"


# ─── FERRAMENTAS ──────────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "listar_chamados",
        "description": "Lista chamados reais de facilities do Pipefy. Use para responder perguntas sobre chamados abertos, urgentes, por categoria, status etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status":     {"type": "string", "enum": ["aberto", "em_andamento", "concluido", "cancelado", "todos"]},
                "prioridade": {"type": "string", "enum": ["urgente", "alta", "media", "baixa", "todas"]},
                "categoria":  {"type": "string", "description": "Ex: Manutenção, Infraestrutura, Limpeza, Suprimentos"}
            },
            "required": []
        }
    },
    {
        "name": "resumo_dashboard",
        "description": "Retorna métricas gerais do Pipefy: total de chamados, por fase, urgentes. Use para perguntas sobre status geral ou relatório.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

# ─── EXECUÇÃO DAS FERRAMENTAS ─────────────────────────────────────────────────
def executar_ferramenta(nome: str, params: dict) -> str:

    if nome == "listar_chamados":
        filtro = params.get("status", "todos")
        chamados, erro = buscar_cards_pipefy(filtro)

        if erro:
            return f"Erro ao buscar dados do Pipefy: {erro}"
        if not chamados:
            return "Nenhum chamado encontrado com esses filtros."

        # Aplica filtro de prioridade
        if params.get("prioridade") and params["prioridade"] != "todas":
            chamados = [c for c in chamados if c.get("prioridade") == params["prioridade"]]

        # Aplica filtro de categoria
        if params.get("categoria"):
            chamados = [c for c in chamados if params["categoria"].lower() in c.get("categoria", "").lower()]

        linhas = f"{len(chamados)} chamado(s) encontrado(s):\n\n"
        for c in chamados[:15]:
            linhas += (
                f"• {c['protocolo']} — {c['titulo']}\n"
                f"  Fase: {c['fase']} | Prioridade: {c['prioridade']} | Categoria: {c['categoria']}\n"
                f"  Solicitante: {c['solicitante']} | Local: {c.get('local','?')} | Data: {c['data']}\n\n"
            )
        return linhas

    elif nome == "resumo_dashboard":
        chamados, erro = buscar_cards_pipefy()

        if erro:
            return f"Erro ao buscar dados do Pipefy: {erro}"

        total      = len(chamados)
        abertos    = len([c for c in chamados if c["status"] == "aberto"])
        andamento  = len([c for c in chamados if c["status"] == "em_andamento"])
        concluidos = len([c for c in chamados if c["status"] == "concluido"])
        urgentes   = len([c for c in chamados if c["prioridade"] == "urgente"])
        sla        = round(concluidos / total * 100, 1) if total > 0 else 0

        return (
            f"Dashboard Facilities — Pipefy\n\n"
            f"Total de chamados: {total}\n"
            f"Abertos: {abertos} | Em andamento: {andamento} | Concluídos: {concluidos}\n"
            f"Urgentes: {urgentes}\n"
            f"SLA (conclusão): {sla}%"
        )

    return "Ferramenta não reconhecida."


# ─── AGENTE ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Você é o Facilities.IA, assistente de inteligência artificial especializado em gestão de facilities da Logcomex.

Você tem acesso aos chamados reais do Pipefy da Logcomex em tempo real.

Responda sempre em português brasileiro. Seja direto, use os dados reais e sempre ofereça um próximo passo ou insight útil."""

def rodar_agente(mensagem: str, historico: list) -> str:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    mensagens = historico + [{"role": "user", "content": mensagem}]

    while True:
        resposta = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=mensagens
        )

        if resposta.stop_reason == "end_turn":
            return "".join(b.text for b in resposta.content if hasattr(b, "text"))

        if resposta.stop_reason == "tool_use":
            mensagens.append({"role": "assistant", "content": resposta.content})
            resultados = []
            for bloco in resposta.content:
                if bloco.type == "tool_use":
                    resultado = executar_ferramenta(bloco.name, bloco.input)
                    resultados.append({
                        "type": "tool_result",
                        "tool_use_id": bloco.id,
                        "content": resultado
                    })
            mensagens.append({"role": "user", "content": resultados})


# ─── HANDLER HTTP ─────────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        corpo   = json.loads(self.rfile.read(tamanho))
        mensagem  = corpo.get("message", "")
        historico = corpo.get("history", [])

        if not mensagem:
            self._responder(400, {"erro": "Mensagem vazia"})
            return

        try:
            resposta = rodar_agente(mensagem, historico)
            self._responder(200, {"response": resposta})
        except Exception as e:
            self._responder(500, {"erro": str(e)})

    def do_OPTIONS(self):
        self.send_response(200)
        self._headers_cors()
        self.end_headers()

    def _responder(self, codigo, dados):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self._headers_cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(corpo))
        self.end_headers()
        self.wfile.write(corpo)

    def _headers_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
