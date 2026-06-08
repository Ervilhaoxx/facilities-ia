"""
api/chamados.py
Endpoint de chamados — GET lista, POST cria novo.
"""
import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Caminho do arquivo de dados
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

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        chamados = carregar_chamados()
        
        # Filtros via query string
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        status    = params.get("status", [None])[0]
        prioridade = params.get("prioridade", [None])[0]
        categoria = params.get("categoria", [None])[0]
        
        if status:
            chamados = [c for c in chamados if c.get("status") == status]
        if prioridade:
            chamados = [c for c in chamados if c.get("prioridade") == prioridade]
        if categoria:
            chamados = [c for c in chamados if c.get("categoria") == categoria]
        
        self._responder(200, chamados)

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        corpo   = self.rfile.read(tamanho)
        
        try:
            dados = json.loads(corpo)
        except:
            self._responder(400, {"erro": "JSON inválido"})
            return
        
        chamados = carregar_chamados()
        
        novo_id = max((c["id"] for c in chamados), default=0) + 1
        novo = {
            "id":         novo_id,
            "protocolo":  f"FCL-{novo_id:04d}",
            "titulo":     dados.get("titulo", "Sem título"),
            "categoria":  dados.get("categoria", "Manutenção"),
            "prioridade": dados.get("prioridade", "media"),
            "status":     "aberto",
            "solicitante":dados.get("solicitante", "Não informado"),
            "local":      dados.get("local", ""),
            "descricao":  dados.get("descricao", ""),
            "data":       datetime.now().strftime("%Y-%m-%d"),
        }
        
        chamados.append(novo)
        salvar_chamados(chamados)
        
        self._responder(201, novo)

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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
