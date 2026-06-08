"""
api/chat.py
Facilities.IA — busca dados reais do Firebase (Firestore).
"""
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler
from datetime import datetime

import anthropic

# ─── CONFIG ───────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
FIREBASE_PROJECT   = "facilities-logcomex"
FIRESTORE_BASE     = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT}/databases/(default)/documents"
FIREBASE_API_KEY   = "AIzaSyCczKnSawfHiAPuMjY2L80ww_wtBMJJY30"

# ─── FIREBASE ─────────────────────────────────────────────────────────────────
def firestore_get(collection, params=""):
    url = f"{FIRESTORE_BASE}/{collection}?key={FIREBASE_API_KEY}{params}"
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()), None
    except Exception as e:
        return None, str(e)

def parse_value(v):
    """Converte um valor Firestore para Python."""
    if not isinstance(v, dict):
        return v
    if "stringValue"    in v: return v["stringValue"]
    if "integerValue"   in v: return int(v["integerValue"])
    if "doubleValue"    in v: return float(v["doubleValue"])
    if "booleanValue"   in v: return v["booleanValue"]
    if "timestampValue" in v: return v["timestampValue"][:10]
    if "nullValue"      in v: return None
    if "mapValue"       in v:
        return {k: parse_value(val) for k, val in v["mapValue"].get("fields", {}).items()}
    if "arrayValue"     in v:
        return [parse_value(i) for i in v["arrayValue"].get("values", [])]
    return str(v)

def parse_doc(doc):
    """Transforma um documento Firestore em dict limpo."""
    fields = doc.get("fields", {})
    result = {k: parse_value(v) for k, v in fields.items()}
    # Adiciona o ID do documento
    name = doc.get("name", "")
    result["_id"] = name.split("/")[-1] if name else ""
    return result

def buscar_chamados(filtro_status=None, filtro_prioridade=None, filtro_categoria=None):
    data, erro = firestore_get("chamados")
    if erro:
        return None, erro

    docs = data.get("documents", [])
    chamados = [parse_doc(d) for d in docs]

    # Aplica filtros
    if filtro_status and filtro_status != "todos":
        chamados = [c for c in chamados if str(c.get("status","")).lower() == filtro_status.lower()]
    if filtro_prioridade and filtro_prioridade != "todas":
        chamados = [c for c in chamados if str(c.get("prioridade","")).lower() == filtro_prioridade.lower()]
    if filtro_categoria:
        chamados = [c for c in chamados if filtro_categoria.lower() in str(c.get("categoria","")).lower()]

    return chamados, None

def buscar_estoque():
    data, erro = firestore_get("estoque")
    if erro:
        return None, erro
    return [parse_doc(d) for d in data.get("documents", [])], None

def buscar_contratos():
    data, erro = firestore_get("contratos")
    if erro:
        return None, erro
    return [parse_doc(d) for d in data.get("documents", [])], None

# ─── FERRAMENTAS ──────────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "listar_chamados",
        "description": "Lista chamados reais de facilities do Firebase. Use para perguntas sobre chamados abertos, urgentes, por categoria, status, solicitante etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status":     {"type": "string", "enum": ["Aberto","Em andamento","Aguardando aprovação","Concluído","Cancelado","todos"]},
                "prioridade": {"type": "string", "enum": ["Urgente","Alta","Média","Baixa","todas"]},
                "categoria":  {"type": "string", "description": "Ex: Manutenção, Infraestrutura, Limpeza, Suprimentos, Brindes"}
            },
            "required": []
        }
    },
    {
        "name": "resumo_dashboard",
        "description": "Retorna métricas gerais: total de chamados, abertos, urgentes, SLA, por categoria. Use para relatórios e visão geral.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "verificar_estoque",
        "description": "Consulta o estoque de suprimentos e brindes. Use quando perguntarem sobre materiais, estoque, suprimentos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "alerta_baixo": {"type": "boolean", "description": "Se true, retorna só itens com estoque baixo"}
            },
            "required": []
        }
    },
    {
        "name": "verificar_contratos",
        "description": "Consulta contratos de fornecedores e imóveis. Use quando perguntarem sobre contratos, fornecedores, vencimentos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dias_para_vencer": {"type": "integer", "description": "Retorna contratos que vencem nos próximos X dias"}
            },
            "required": []
        }
    }
]

# ─── EXECUÇÃO DAS FERRAMENTAS ─────────────────────────────────────────────────
def executar_ferramenta(nome: str, params: dict) -> str:

    if nome == "listar_chamados":
        chamados, erro = buscar_chamados(
            params.get("status"),
            params.get("prioridade"),
            params.get("categoria")
        )
        if erro: return f"Erro ao buscar chamados: {erro}"
        if not chamados: return "Nenhum chamado encontrado com esses filtros."

        linhas = f"{len(chamados)} chamado(s) encontrado(s):\n\n"
        for c in chamados[:15]:
            linhas += (
                f"• {c.get('protocolo', c.get('_id','?'))} — {c.get('titulo', c.get('descricao','Sem título'))}\n"
                f"  Status: {c.get('status','?')} | Prioridade: {c.get('prioridade','?')} | Categoria: {c.get('categoria','?')}\n"
                f"  Solicitante: {c.get('solicitante', c.get('nome','?'))} | Centro de custo: {c.get('centroCusto', c.get('centro_custo','?'))}\n"
                f"  Data: {c.get('data', c.get('createdAt','?'))}\n\n"
            )
        return linhas

    elif nome == "resumo_dashboard":
        chamados, erro = buscar_chamados()
        if erro: return f"Erro ao buscar dados: {erro}"

        total      = len(chamados)
        abertos    = len([c for c in chamados if "aberto" in str(c.get("status","")).lower()])
        andamento  = len([c for c in chamados if "andamento" in str(c.get("status","")).lower()])
        concluidos = len([c for c in chamados if "conclu" in str(c.get("status","")).lower()])
        urgentes   = len([c for c in chamados if "urgente" in str(c.get("prioridade","")).lower()])
        sla        = round(concluidos / total * 100, 1) if total > 0 else 0

        # Conta por categoria
        categorias = {}
        for c in chamados:
            cat = c.get("categoria", "Sem categoria")
            categorias[cat] = categorias.get(cat, 0) + 1
        top_cats = sorted(categorias.items(), key=lambda x: x[1], reverse=True)[:5]
        cats_txt = "\n".join(f"  - {k}: {v}" for k, v in top_cats)

        return (
            f"Dashboard Facilities — Logcomex\n\n"
            f"Total de chamados: {total}\n"
            f"Abertos: {abertos} | Em andamento: {andamento} | Concluídos: {concluidos}\n"
            f"Urgentes: {urgentes}\n"
            f"SLA (conclusão): {sla}%\n\n"
            f"Top categorias:\n{cats_txt}"
        )

    elif nome == "verificar_estoque":
        itens, erro = buscar_estoque()
        if erro: return f"Erro ao buscar estoque: {erro}"
        if not itens: return "Nenhum item no estoque."

        if params.get("alerta_baixo"):
            itens = [i for i in itens if int(i.get("quantidade", 99)) <= int(i.get("minimo", i.get("estoqueMinimo", 0)))]

        if not itens: return "Estoque OK — nenhum item abaixo do mínimo."

        linhas = f"{len(itens)} item(ns):\n\n"
        for i in itens[:15]:
            qtd = i.get("quantidade", "?")
            minimo = i.get("minimo", i.get("estoqueMinimo", "?"))
            alerta = " ⚠️ BAIXO" if str(qtd) <= str(minimo) else ""
            linhas += f"• {i.get('nome', i.get('item','?'))}: {qtd} unidades (mín: {minimo}){alerta}\n"
        return linhas

    elif nome == "verificar_contratos":
        contratos, erro = buscar_contratos()
        if erro: return f"Erro ao buscar contratos: {erro}"
        if not contratos: return "Nenhum contrato encontrado."

        if params.get("dias_para_vencer"):
            hoje = datetime.now()
            filtrados = []
            for c in contratos:
                venc = c.get("dataVencimento") or c.get("vencimento") or c.get("data_vencimento")
                if venc:
                    try:
                        dv = datetime.strptime(str(venc)[:10], "%Y-%m-%d")
                        diff = (dv - hoje).days
                        if 0 <= diff <= params["dias_para_vencer"]:
                            c["_dias_restantes"] = diff
                            filtrados.append(c)
                    except: pass
            contratos = filtrados

        if not contratos: return "Nenhum contrato encontrado com esse filtro."

        linhas = f"{len(contratos)} contrato(s):\n\n"
        for c in contratos[:10]:
            dias = f" — vence em {c.get('_dias_restantes')} dias ⚠️" if c.get("_dias_restantes") is not None else ""
            linhas += (
                f"• {c.get('fornecedor', c.get('nome','?'))}{dias}\n"
                f"  Valor: R$ {c.get('valor','?')} | Vencimento: {c.get('dataVencimento', c.get('vencimento','?'))}\n\n"
            )
        return linhas

    return "Ferramenta não reconhecida."

# ─── AGENTE ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Você é o Facilities.IA, assistente de inteligência artificial especializado em gestão de facilities da Logcomex.

Você tem acesso aos dados reais do sistema de facilities da Logcomex em tempo real — chamados, estoque, contratos.

Responda sempre em português brasileiro. Seja direto, apresente dados reais com destaque para urgências, e sempre sugira um próximo passo útil."""

def rodar_agente(mensagem: str, historico: list) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
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
                    resultados.append({"type": "tool_result", "tool_use_id": bloco.id, "content": resultado})
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
