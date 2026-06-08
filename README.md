# Facilities.IA 🏢

> Inteligência Artificial para gestão de facilities — Logcomex

## Stack
- **Frontend**: HTML + CSS + JS puro (sem framework)
- **Backend**: Python (Vercel Serverless Functions)
- **IA**: Claude API (Anthropic) com tool use
- **Banco**: JSON local → migrar para Supabase/Postgres depois

## Estrutura

```
facilities-ia/
├── api/                  ← Serverless functions (Python)
│   ├── chat.py           ← Endpoint principal do agente IA
│   ├── chamados.py       ← CRUD de chamados
│   └── dashboard.py      ← Resumo e métricas
├── public/               ← Frontend estático
│   ├── index.html        ← Interface do chat
│   ├── css/style.css
│   └── js/app.js
├── data/                 ← Dados iniciais (JSON)
│   └── chamados.json
├── vercel.json           ← Config do Vercel
└── requirements.txt      ← Dependências Python
```

## Setup local

```bash
npm i -g vercel
vercel dev
```

## Deploy

```bash
vercel --prod
```

## Variáveis de ambiente (Vercel)

```
ANTHROPIC_API_KEY=sk-ant-...
```
