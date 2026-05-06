/* =====================================================
   Local ADK — app.js
   ===================================================== */
'use strict';

// ── State ──────────────────────────────────────────────
const state = {
  agents: [],
  selectedAgent: null,
  sessionId: null,
  msgCount: 0,
  tokenEst: 0,
  streaming: false,
};

// ── Helpers ────────────────────────────────────────────
const $ = id => document.getElementById(id);
const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

/** Very small markdown → HTML converter */
function md(text) {
  return text
    .replace(/```([\s\S]*?)```/g, (_,c) => `<pre><code>${esc(c.trim())}</code></pre>`)
    .replace(/`([^`]+)`/g, (_,c) => `<code>${esc(c)}</code>`)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^#{1,3} (.+)$/gm, '<strong>$1</strong>')
    .replace(/^\* (.+)$/gm, '• $1')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

function initials(name) {
  return name.split(/\s+/).map(w => w[0]).join('').toUpperCase().slice(0,2);
}

function genSessionId() {
  return 'ses-' + Math.random().toString(36).slice(2,9);
}

function estimateTokens(text) {
  return Math.ceil(text.split(/\s+/).length * 1.3);
}

// ── Background Canvas ──────────────────────────────────
function initCanvas() {
  const canvas = $('bgCanvas');
  const ctx = canvas.getContext('2d');
  let W, H, particles = [];

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  function Particle() {
    this.x = Math.random() * W;
    this.y = Math.random() * H;
    this.vx = (Math.random() - 0.5) * 0.3;
    this.vy = (Math.random() - 0.5) * 0.3;
    this.r  = Math.random() * 1.5 + 0.3;
    this.alpha = Math.random() * 0.6 + 0.2;
  }

  function init() {
    resize();
    particles = Array.from({length: 80}, () => new Particle());
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    particles.forEach(p => {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0) p.x = W; if (p.x > W) p.x = 0;
      if (p.y < 0) p.y = H; if (p.y > H) p.y = 0;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(6,182,212,${p.alpha})`;
      ctx.fill();
    });
    // Draw connecting lines
    for (let i = 0; i < particles.length; i++) {
      for (let j = i+1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const d  = Math.sqrt(dx*dx + dy*dy);
        if (d < 100) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(6,182,212,${0.12 * (1 - d/100)})`;
          ctx.lineWidth = 0.6;
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(draw);
  }

  window.addEventListener('resize', resize);
  init();
  draw();
}

// ── Health check ───────────────────────────────────────
async function checkHealth() {
  try {
    const r = await fetch('/api/health');
    const d = await r.json();
    const pill = $('lmStatus');
    pill.className = 'status-pill ' + (d.lm_studio === 'online' ? 'online' : 'offline');
    pill.querySelector('.label').textContent = d.lm_studio === 'online' ? 'LM Studio Online' : 'LM Studio Offline';
    $('modelBadge').textContent = d.model || '—';
    $('cfgBaseUrl').textContent = d.base_url || '—';
    $('cfgModel').textContent   = d.model    || '—';
  } catch {
    $('lmStatus').className = 'status-pill offline';
    $('lmStatus').querySelector('.label').textContent = 'Server Error';
  }
}

// ── Load agents ────────────────────────────────────────
async function loadAgents() {
  try {
    const r = await fetch('/api/agents');
    const d = await r.json();
    state.agents = d.agents;
    renderSidebar();
    renderOrchCanvas();
    if (state.agents.length) selectAgent(state.agents[0]);
  } catch(e) {
    console.error('Failed to load agents', e);
  }
}

function renderSidebar() {
  const list = $('agentList');
  list.innerHTML = '';
  state.agents.forEach(a => {
    const card = document.createElement('div');
    card.className = 'agent-card';
    card.dataset.id = a.id;
    card.innerHTML = `
      <div class="agent-avatar" style="background:${a.color}22;color:${a.color}">${initials(a.name)}</div>
      <div class="agent-info">
        <strong>${esc(a.name)}</strong>
        <small>${esc(a.role)}</small>
      </div>
      <span class="agent-status-dot s-${a.status}"></span>`;
    card.addEventListener('click', () => selectAgent(a));
    list.appendChild(card);
  });
}

function renderOrchCanvas() {
  const canvas = $('orchCanvas');
  canvas.innerHTML = '';
  state.agents.forEach(a => {
    const node = document.createElement('div');
    node.className = 'orch-node';
    node.innerHTML = `
      <div class="orch-node-icon" style="background:${a.color}22;color:${a.color}">${initials(a.name)}</div>
      <strong>${esc(a.name)}</strong>
      <small>${esc(a.role)}</small>`;
    canvas.appendChild(node);
  });
}

function selectAgent(agent) {
  state.selectedAgent = agent;
  // Update sidebar highlight
  document.querySelectorAll('.agent-card').forEach(c => {
    c.classList.toggle('selected', c.dataset.id === agent.id);
  });
  // Update chat header
  $('agentDot').style.background = agent.color;
  $('agentDot').style.boxShadow  = `0 0 6px ${agent.color}`;
  $('agentName').textContent = agent.name;
  $('agentRole').textContent = agent.role;
  // Clear chat
  clearMessages();
}

// ── Session ────────────────────────────────────────────
function newSession() {
  state.sessionId = genSessionId();
  state.msgCount  = 0;
  state.tokenEst  = 0;
  updateSessionInfo();
  clearMessages();
}

function updateSessionInfo() {
  $('siSession').textContent = state.sessionId ? state.sessionId.slice(0,10) + '…' : '—';
  $('siMsgs').textContent    = state.msgCount;
  $('siTokens').textContent  = state.tokenEst;
}

// ── Messages ───────────────────────────────────────────
function clearMessages() {
  const msgs = $('messages');
  msgs.innerHTML = `
    <div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
      </svg>
      <p>No messages yet. Start a conversation.</p>
    </div>`;
}

function appendMessage(role, text) {
  const msgs = $('messages');
  // Remove empty state if present
  const empty = msgs.querySelector('.empty-state');
  if (empty) empty.remove();

  const div = document.createElement('div');
  div.className = `msg ${role}`;

  const avatarLetter = role === 'user' ? 'U' : initials(state.selectedAgent?.name || 'AI');
  div.innerHTML = `
    <div class="msg-avatar">${avatarLetter}</div>
    <div class="msg-bubble">${role === 'agent' ? '<p>' + md(text) + '</p>' : esc(text)}</div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div.querySelector('.msg-bubble');
}

function appendThinking() {
  const msgs = $('messages');
  const empty = msgs.querySelector('.empty-state');
  if (empty) empty.remove();

  const div = document.createElement('div');
  div.className = 'msg agent';
  div.id = 'thinkingMsg';
  div.innerHTML = `
    <div class="msg-avatar">${initials(state.selectedAgent?.name || 'AI')}</div>
    <div class="msg-bubble"><div class="thinking"><span></span><span></span><span></span></div></div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function removeThinking() {
  const t = $('thinkingMsg');
  if (t) t.remove();
}

// ── Send ───────────────────────────────────────────────
async function sendMessage() {
  const input = $('userInput');
  const text  = input.value.trim();
  if (!text || state.streaming) return;
  if (!state.selectedAgent) { alert('Please select an agent.'); return; }

  input.value = '';
  input.style.height = 'auto';

  // Ensure session
  if (!state.sessionId) state.sessionId = genSessionId();

  // Render user message
  appendMessage('user', text);
  state.msgCount++;
  state.tokenEst += estimateTokens(text);
  updateSessionInfo();

  // Thinking indicator
  appendThinking();
  state.streaming = true;
  $('sendBtn').disabled = true;

  try {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        agent_id: state.selectedAgent.id,
        session_id: state.sessionId,
        user_id: 'local-user',
      }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let bubble = null;
    let full = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        let evt;
        try { evt = JSON.parse(line.slice(6)); } catch { continue; }

        if (evt.type === 'session') {
          state.sessionId = evt.session_id;
          updateSessionInfo();
        } else if (evt.type === 'chunk') {
          if (!bubble) {
            removeThinking();
            // Create agent bubble
            const msgs = $('messages');
            const div = document.createElement('div');
            div.className = 'msg agent';
            div.innerHTML = `<div class="msg-avatar">${initials(state.selectedAgent?.name||'AI')}</div><div class="msg-bubble"><p></p></div>`;
            msgs.appendChild(div);
            bubble = div.querySelector('p');
            msgs.scrollTop = msgs.scrollHeight;
          }
          full += evt.text;
          bubble.innerHTML = md(full);
          $('messages').scrollTop = $('messages').scrollHeight;
        } else if (evt.type === 'done') {
          removeThinking();
          state.msgCount++;
          state.tokenEst += estimateTokens(full);
          updateSessionInfo();
        } else if (evt.type === 'error') {
          removeThinking();
          appendMessage('agent', `⚠️ Error: ${evt.text}`);
        }
      }
    }
  } catch(e) {
    removeThinking();
    appendMessage('agent', `⚠️ Connection error: ${e.message}`);
  } finally {
    state.streaming = false;
    $('sendBtn').disabled = false;
    input.focus();
  }
}

// ── Tab switching ──────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      btn.classList.add('active');
      $('view-' + btn.dataset.tab).classList.add('active');
    });
  });
}

// ── Auto-resize textarea ───────────────────────────────
function initTextarea() {
  const ta = $('userInput');
  ta.addEventListener('input', () => {
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 140) + 'px';
  });
  ta.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  $('sendBtn').addEventListener('click', sendMessage);
}

// ══════════════════════════════════════════════════════════
// DEEP RESEARCH TAB
// ══════════════════════════════════════════════════════════

const researchState = {
  running: false,
  reportText: '',
  sessionId: null,
};

const STAGE_COLORS = {
  PlannerAgent:     '#6366f1',
  ExecutorAgent:    '#22c55e',
  SynthesizerAgent: '#f59e0b',
};

function resetPipeline() {
  ['PlannerAgent', 'ExecutorAgent', 'SynthesizerAgent'].forEach(s => {
    const el = $('stage-' + s);
    const st = $('status-' + s);
    if (el) { el.classList.remove('stage-active', 'stage-done', 'stage-error'); }
    if (st) { st.textContent = 'idle'; st.className = 'stage-status'; }
  });
  $('activityLog').innerHTML = '';
}

function setStageActive(stage) {
  const el = $('stage-' + stage);
  const st = $('status-' + stage);
  if (!el) return;
  el.classList.remove('stage-done', 'stage-error');
  el.classList.add('stage-active');
  if (st) { st.textContent = 'running…'; st.className = 'stage-status running'; }
}

function setStageComplete(stage) {
  const el = $('stage-' + stage);
  const st = $('status-' + stage);
  if (!el) return;
  el.classList.remove('stage-active', 'stage-error');
  el.classList.add('stage-done');
  if (st) { st.textContent = 'done ✓'; st.className = 'stage-status done'; }
}

function logActivity(type, msg, stage) {
  const log = $('activityLog');
  const idle = log.querySelector('.log-idle');
  if (idle) idle.remove();

  const div = document.createElement('div');
  div.className = 'log-entry log-' + type;
  const color = stage ? (STAGE_COLORS[stage] || '#94a3b8') : '#94a3b8';
  const icon = type === 'stage'   ? '▶'
             : type === 'tool'    ? '⚙'
             : type === 'done'    ? '✓'
             : type === 'error'   ? '✗'
             : '·';
  div.innerHTML = `<span class="log-icon" style="color:${color}">${icon}</span><span>${esc(msg)}</span>`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function initResearch() {
  const btn = $('researchBtn');
  const ta  = $('researchInput');
  const out = $('reportOutput');
  const copyBtn  = $('btnCopyReport');
  const clearBtn = $('btnClearReport');

  btn.addEventListener('click', runResearch);
  ta.addEventListener('keydown', e => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      runResearch();
    }
  });

  copyBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(researchState.reportText).then(() => {
      copyBtn.textContent = 'Copied!';
      setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
    });
  });

  clearBtn.addEventListener('click', () => {
    researchState.reportText = '';
    researchState.sessionId  = null;
    out.innerHTML = `<div class="report-empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" width="48" height="48">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
      </svg>
      <p>Your deep research report will appear here.</p>
    </div>`;
    copyBtn.style.display  = 'none';
    clearBtn.style.display = 'none';
    resetPipeline();
  });
}

async function runResearch() {
  if (researchState.running) return;
  const ta   = $('researchInput');
  const query = ta.value.trim();
  if (!query) { ta.focus(); return; }

  researchState.running    = true;
  researchState.reportText = '';
  $('researchBtn').disabled = true;
  $('researchBtn').textContent = 'Researching…';

  resetPipeline();

  const out = $('reportOutput');
  out.innerHTML = '';
  $('btnCopyReport').style.display  = 'none';
  $('btnClearReport').style.display = 'none';

  logActivity('info', `Starting deep research: "${query.slice(0, 80)}"`, null);

  try {
    const res = await fetch('/api/research/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        session_id: researchState.sessionId,
        user_id: 'local-user',
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let reportEl  = null;   // <p> inside report-output where we stream text
    let reportBuf = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });

      for (const line of chunk.split('\n')) {
        if (!line.startsWith('data: ')) continue;
        let evt;
        try { evt = JSON.parse(line.slice(6)); } catch { continue; }

        switch (evt.type) {
          case 'session':
            researchState.sessionId = evt.session_id;
            break;

          case 'pipeline_start':
            logActivity('info', 'Pipeline initialised — stages: ' + evt.stages.join(' → '), null);
            break;

          case 'stage_start':
            setStageActive(evt.stage);
            logActivity('stage', `[${evt.stage}] started`, evt.stage);
            break;

          case 'stage_complete':
            setStageComplete(evt.stage);
            logActivity('done', `[${evt.stage}] complete`, evt.stage);
            break;

          case 'tool_call':
            logActivity('tool', `[${evt.stage}] ${evt.tool}("${evt.arg}")`, evt.stage);
            break;

          case 'report_start':
            // Create the report container
            reportEl = document.createElement('div');
            reportEl.className = 'report-content';
            out.innerHTML = '';
            out.appendChild(reportEl);
            break;

          case 'chunk':
            if (!reportEl) {
              reportEl = document.createElement('div');
              reportEl.className = 'report-content';
              out.innerHTML = '';
              out.appendChild(reportEl);
            }
            reportBuf += evt.text;
            researchState.reportText = reportBuf;
            reportEl.innerHTML = md(reportBuf);
            out.scrollTop = out.scrollHeight;
            break;

          case 'done':
            logActivity('done', 'Research complete! Stages: ' + (evt.stages_completed || []).join(', '), null);
            $('btnCopyReport').style.display  = 'inline-flex';
            $('btnClearReport').style.display = 'inline-flex';
            break;

          case 'error':
            logActivity('error', 'Error: ' + evt.text, null);
            if (!reportEl) {
              out.innerHTML = `<div class="report-error">&#x26A0;&#xFE0F; ${esc(evt.text)}</div>`;
            }
            break;
        }
      }
    }
  } catch(e) {
    logActivity('error', 'Connection error: ' + e.message, null);
    out.innerHTML = `<div class="report-error">&#x26A0;&#xFE0F; Connection error: ${esc(e.message)}</div>`;
  } finally {
    researchState.running = false;
    $('researchBtn').disabled = false;
    $('researchBtn').textContent = 'Research';
  }
}

// ── Boot ───────────────────────────────────────────────
async function boot() {
  initCanvas();
  initTabs();
  initTextarea();
  initResearch();

  newSession();
  $('btnNewSession').addEventListener('click', newSession);

  await checkHealth();
  await loadAgents();

  // Poll health every 15 s
  setInterval(checkHealth, 15000);
}

document.addEventListener('DOMContentLoaded', boot);

