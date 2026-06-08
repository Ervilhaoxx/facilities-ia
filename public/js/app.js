// ─── ESTADO ─────────────────────────────────────────────────────────────────
let historico = [];
let aguardando = false;

// ─── ELEMENTOS ───────────────────────────────────────────────────────────────
const emptyState    = document.getElementById('empty-state');
const chatContainer = document.getElementById('chat-container');
const messagesEl    = document.getElementById('messages');
const inputEl       = document.getElementById('input');
const sendBtn       = document.getElementById('send-btn');

// ─── NOVA CONVERSA ────────────────────────────────────────────────────────────
function novaConversa() {
  historico = [];
  messagesEl.innerHTML = '';
  chatContainer.style.display = 'none';
  emptyState.style.display = 'flex';
  inputEl.value = '';
  autoResize(inputEl);
}

// ─── ENVIAR MENSAGEM ──────────────────────────────────────────────────────────
async function enviar() {
  const texto = inputEl.value.trim();
  if (!texto || aguardando) return;

  // Esconde empty state, mostra chat
  emptyState.style.display = 'none';
  chatContainer.style.display = 'flex';

  // Adiciona mensagem do usuário
  adicionarMensagem('user', texto);
  historico.push({ role: 'user', content: texto });

  // Limpa input
  inputEl.value = '';
  autoResize(inputEl);

  // Estado de loading
  aguardando = true;
  sendBtn.disabled = true;
  const typingEl = adicionarTyping();

  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: texto,
        history: historico.slice(-20) // últimas 10 trocas
      })
    });

    const dados = await resp.json();

    typingEl.remove();

    if (dados.response) {
      adicionarMensagem('ai', dados.response);
      historico.push({ role: 'assistant', content: dados.response });
    } else if (dados.erro) {
      adicionarMensagem('ai', `Ocorreu um erro: ${dados.erro}`);
    }

  } catch (err) {
    typingEl.remove();
    adicionarMensagem('ai', 'Não consegui me conectar ao servidor. Verifique sua conexão e tente novamente.');
  }

  aguardando = false;
  sendBtn.disabled = false;
  inputEl.focus();
}

// ─── ENVIAR SUGESTÃO ──────────────────────────────────────────────────────────
function enviarSugestao(texto) {
  inputEl.value = texto;
  autoResize(inputEl);
  enviar();
}

// ─── ADICIONAR MENSAGEM ───────────────────────────────────────────────────────
function adicionarMensagem(tipo, texto) {
  const msg = document.createElement('div');
  msg.className = `message ${tipo}`;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = tipo === 'ai' ? 'F' : 'V';

  const content = document.createElement('div');
  content.className = 'message-content';
  content.textContent = texto;

  msg.appendChild(avatar);
  msg.appendChild(content);
  messagesEl.appendChild(msg);

  // Scroll para o final
  messagesEl.scrollTop = messagesEl.scrollHeight;

  return msg;
}

// ─── TYPING INDICATOR ────────────────────────────────────────────────────────
function adicionarTyping() {
  const msg = document.createElement('div');
  msg.className = 'message ai';

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = 'F';

  const content = document.createElement('div');
  content.className = 'message-content';
  content.innerHTML = `
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
  `;

  msg.appendChild(avatar);
  msg.appendChild(content);
  messagesEl.appendChild(msg);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  return msg;
}

// ─── UTILITÁRIOS ─────────────────────────────────────────────────────────────
function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    enviar();
  }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

// Focus no input ao carregar
inputEl.focus();
