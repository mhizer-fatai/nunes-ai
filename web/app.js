"use strict";

const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatSend = document.getElementById("chat-send");
const journalLog = document.getElementById("journal-log");
const ablationRun = document.getElementById("ablation-run");
const ablationResult = document.getElementById("ablation-result");

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function toast(container, message) {
  container.prepend(el("div", "toast", message));
}

async function api(path, options) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = data && data.error ? data.error : {};
    throw new Error(err.message || ("request failed: " + res.status));
  }
  return data;
}

/* ---------- status pills ---------- */

async function loadStatus() {
  try {
    const s = await api("/api/status");
    document.getElementById("pill-memory").textContent = "memory: connected";
    document.getElementById("pill-memory").title = s.memory;
    document.getElementById("pill-chain").textContent = "chain: " + s.chain;
  } catch (e) {
    document.getElementById("pill-memory").textContent = "memory: unreachable";
    document.getElementById("pill-chain").textContent = "chain: unknown";
  }
}

/* ---------- chat ---------- */

function addUser(text) {
  chatLog.appendChild(el("div", "msg user", text));
  chatLog.scrollTop = chatLog.scrollHeight;
}

function addTeam(agent, text) {
  const wrap = el("div", "msg team");
  if (agent) wrap.appendChild(el("div", "agent-badge " + agent, agent));
  wrap.appendChild(el("div", "bubble", text));
  chatLog.appendChild(wrap);
  chatLog.scrollTop = chatLog.scrollHeight;
  return wrap;
}

chatForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = "";
  chatSend.disabled = true;
  addUser(text);
  const thinking = addTeam(null, "");
  thinking.querySelector(".bubble").innerHTML =
    '<span class="shimmer">Consulting shared memory…</span>';
  try {
    const data = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    thinking.remove();
    addTeam(data.agent, data.reply);
  } catch (e) {
    thinking.remove();
    addTeam(null, "The team could not answer: " + e.message);
  } finally {
    chatSend.disabled = false;
    chatInput.focus();
  }
  loadJournal();
});

/* ---------- journal ---------- */

function shortAddr(text) {
  return text.replace(/0x[0-9a-fA-F]{40}/g, (m) => m.slice(0, 6) + "…" + m.slice(-4));
}

async function loadJournal() {
  let data;
  try {
    data = await api("/api/journal?limit=40");
  } catch (e) {
    journalLog.innerHTML = "";
    toast(journalLog, "Journal unreachable: " + e.message);
    return;
  }
  journalLog.innerHTML = "";
  if (!data.events || data.events.length === 0) {
    journalLog.appendChild(el("div", "empty",
      "No decisions recorded yet — talk to the team and watch this notebook fill."));
    return;
  }
  for (const ev of data.events) {
    const entry = el("div", "entry " + (ev.kind || ""));
    const meta = el("div", "meta");
    if (ev.kind) meta.appendChild(el("span", "chip " + ev.kind, ev.kind));
    if (ev.actor) meta.appendChild(el("span", null, ev.actor));
    if (ev.ts) {
      const d = new Date(ev.ts);
      meta.appendChild(el("span", null, isNaN(d) ? ev.ts : d.toLocaleString()));
    }
    entry.appendChild(meta);
    const body = el("div", null, shortAddr(ev.text || ""));
    if (ev.txUrl) {
      body.appendChild(document.createTextNode(" "));
      const a = document.createElement("a");
      a.href = ev.txUrl;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = "view tx ↗";
      body.appendChild(a);
    }
    entry.appendChild(body);
    journalLog.appendChild(entry);
  }
}

/* ---------- ablation ---------- */

ablationRun.addEventListener("click", async () => {
  ablationRun.disabled = true;
  ablationResult.innerHTML = '<span class="shimmer">Running with-memory vs without-memory arms…</span>';
  try {
    const r = await api("/api/ablation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trials: 1 }),
    });
    ablationResult.innerHTML = "";
    const big = el("div", "big-number");
    big.innerHTML = "";
    big.appendChild(el("span", "good",
      "With memory: " + r.withBlocked + "/" + r.withTotal + " harmful payments blocked. "));
    big.appendChild(el("span", "bad",
      "Without: " + r.withoutAllowed + "/" + r.withoutTotal + " sail through."));
    ablationResult.appendChild(big);
    const cats = el("div", null, "Blocked by category: " +
      Object.entries(r.byCategory || {}).map(([k, v]) => k + " " + v).join(" · "));
    ablationResult.appendChild(cats);
  } catch (e) {
    ablationResult.innerHTML = "";
    toast(ablationResult, "Deletion test failed: " + e.message);
  } finally {
    ablationRun.disabled = false;
  }
});

/* ---------- boot ---------- */

addTeam("payments",
  "The team is awake. Ask the planner to ban a vendor, the policy agent for a rule, or me to pay an invoice — everything lands in the shared notebook on the right.");
loadStatus();
loadJournal();
setInterval(loadJournal, 15000);
setInterval(loadStatus, 30000);
