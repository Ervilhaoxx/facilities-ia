"""
api/chat.py
Endpoint principal do Facilities.IA.
Recebe uma mensagem, roda o agente com tool use, retorna a resposta.
"""
import json
import os
from http.server import BaseHTTPRequestHandler
from datetime import datetime

import anthropic

# ─── DADOS ────────────────────────────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "chamados.json")

def carregar_chamados():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def salvar_chamados(chamados):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(chamados, f, ensure_ascii=False, indent=2)

# ─── FERRAMENTAS ──────────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "listar_chamados",
        "description": "Lista chamados de facilities com filtros opcionais. Use para responder perguntas sobre chamados abertos, urgentes, por categoria etc.",
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
        "name": "criar_chamado",
        "description": "Cria um novo chamado de facilities. Use quando o usuário pedir para abrir ou registrar um chamado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo":     {"type": "string"},
                "categoria":  {"type": "string"},
                "prioridade": {"type": "string", "enum": ["baixa", "media", "alta", "urgente"]},
                "solicitante":{"type": "string"},
                "local":      {"type": "string"},
                "descricao":  {"type": "string"}
            },
            "required": ["titulo", "categoria", "prioridade", "solicitante"]
        }
    },
    {
        "name": "resumo_dashboard",
        "description": "Retorna métricas gerais: total de chamados, abertos, urgentes, SLA. Use para perguntas sobre status geral ou relatório.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

# ─── EXECUÇÃO DAS FERRAMENTAS ─────────────────────────────────────────────────
def executar_ferramenta(nome: str, params: dict) -> str:
    chamados = carregar_chamados()

    if nome == "listar_chamados":
        resultado = chamados
        if params.get("status") and params["status"] != "todos":
            resultado = [c for c in resultado if c.get("status") == params["status"]]
        if params.get("prioridade") and params["prioridade"] != "todas":
            resultado = [c for c in resultado if c.get("prioridade") == params["prioridade"]]
        if params.get("categoria"):
            resultado = [c for c in resultado if c.get("categoria", "").lower() == params["categoria"].lower()]

        if not resultado:
            return "Nenhum chamado encontrado com esses filtros."

        linhas = f"{len(resultado)} chamado(s) encontrado(s):\n\n"
        for c in resultado[:10]:
            linhas += (
                f"• {c['protocolo']} — {c['titulo']}\n"
                f"  Status: {c['status']} | Prioridade: {c['prioridade']} | "
                f"Categoria: {c['categoria']} | Local: {c.get('local','?')}\n"
                f"  Solicitante: {c['solicitante']} | Data: {c['data']}\n\n"
            )
        return linhas

    elif nome == "criar_chamado":
        novo_id = max((c["id"] for c in chamados), default=0) + 1
        novo = {
            "id":          novo_id,
            "protocolo":   f"FCL-{novo_id:04d}",
            "titulo":      params.get("titulo"),
            "categoria":   params.get("categoria", "Manutenção"),
            "prioridade":  params.get("prioridade", "media"),
            "status":      "aberto",
            "solicitante": params.get("solicitante", "Não informado"),
            "local":       params.get("local", ""),
            "descricao":   params.get("descricao", ""),
            "data":        datetime.now().strftime("%Y-%m-%d"),
        }
        chamados.append(novo)
        salvar_chamados(chamados)
        return f"Chamado criado! Protocolo: {novo['protocolo']} | Status: aberto | Prioridade: {novo['prioridade']}"

    elif nome == "resumo_dashboard":
        total      = len(chamados)
        abertos    = len([c for c in chamados if c.get("status") == "aberto"])
        andamento  = len([c for c in chamados if c.get("status") == "em_andamento"])
        concluidos = len([c for c in chamados if c.get("status") == "concluido"])
        urgentes   = len([c for c in chamados if c.get("prioridade") == "urgente"])
        sla        = round(concluidos / total * 100, 1) if total > 0 else 0
        return (
            f"Total: {total} chamados\n"
            f"Abertos: {abertos} | Em andamento: {andamento} | Concluídos: {concluidos}\n"
            f"Urgentes: {urgentes}\n"
            f"SLA (conclusão): {sla}%"
        )

    return "Ferramenta não reconhecida."

# ─── AGENTE ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Você é o Facilities.IA, assistente de inteligência artificial especializado em gestão de facilities da Logcomex.

Você pode consultar e criar chamados, ver o dashboard e ajudar gestores e colaboradores com tudo relacionado ao ambiente de trabalho.

Responda sempre em português brasileiro. Seja direto, use dados reais e sempre ofereça um próximo passo ou insight útil."""

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
