const state = { token: localStorage.getItem("monitor-token"), mode: "login", sessions: [], packets: [], models: [], socket: null, toastTimer: null };
const $ = (selector) => document.querySelector(selector);

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
  if (options.body instanceof URLSearchParams) headers.set("Content-Type", "application/x-www-form-urlencoded");
  else if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers });
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.detail || `Request failed (${response.status})`);
  return body;
}

function notify(message) {
  const toast = $("#toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.remove("show"), 3300);
}

function showError(element, message) { element.textContent = message; }
function escapeText(value) { return value == null ? "—" : String(value); }

function setAuthenticated(userEmail) {
  $("#auth-panel").hidden = true;
  $("#dashboard").hidden = false;
  $("#user-tools").hidden = false;
  $("#user-email").textContent = userEmail;
}

function setAnonymous() {
  state.token = null;
  localStorage.removeItem("monitor-token");
  state.socket?.close();
  state.socket = null;
  $("#auth-panel").hidden = false;
  $("#dashboard").hidden = true;
  $("#user-tools").hidden = true;
}

async function loadDashboard() {
  const [summary, sessions, interfaces, packets, models] = await Promise.all([
    api("/api/dashboard/summary"), api("/api/monitoring/sessions"), api("/api/monitoring/interfaces"),
    api("/api/detections?limit=50"), api("/api/models"),
  ]);
  state.sessions = sessions;
  state.packets = packets;
  state.models = models;
  $("#stat-packets").textContent = summary.total_packets;
  $("#stat-anomalies").textContent = summary.anomalies;
  $("#stat-benign").textContent = summary.benign;
  $("#stat-sessions").textContent = summary.active_sessions;
  $("#session-count").textContent = `${sessions.length} session${sessions.length === 1 ? "" : "s"}`;
  renderInterfaces(interfaces.interfaces);
  renderSessions();
  renderModels();
  renderPackets();
  connectLiveSocket($("#packet-session").value);
}

function renderInterfaces(interfaces) {
  const select = $("#interface");
  const previous = select.value;
  select.replaceChildren(new Option("Select interface", ""));
  for (const name of interfaces) select.add(new Option(name, name));
  if (interfaces.includes(previous)) select.value = previous;
  if (!interfaces.length) select.add(new Option("No interfaces found", ""));
}

function renderSessions() {
  const target = $("#sessions");
  const live = $("#packet-session");
  const selected = live.value;
  target.replaceChildren();
  live.replaceChildren(new Option("Choose session for live updates", ""));
  for (const session of state.sessions) {
    live.add(new Option(`${session.name} (${session.status})`, session.id));
    const row = document.createElement("div");
    row.className = "session-row";
    const info = document.createElement("div");
    const name = document.createElement("div");
    name.className = "session-name";
    name.textContent = session.name;
    const meta = document.createElement("div");
    meta.className = "session-meta";
    meta.textContent = `${session.interface} · ${session.packet_capture_limit_bytes} bytes · ${session.status}`;
    info.append(name, meta);
    const actions = document.createElement("div");
    actions.className = "session-actions";
    const toggle = document.createElement("button");
    toggle.className = `button ${session.status === "running" ? "button-quiet" : "button-primary"}`;
    toggle.type = "button";
    toggle.textContent = session.status === "running" ? "Stop" : "Start";
    toggle.addEventListener("click", () => changeSession(session));
    actions.append(toggle);
    row.append(info, actions);
    target.append(row);
  }
  if (!state.sessions.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "Create a session to get started.";
    target.append(empty);
  }
  live.value = state.sessions.some((session) => session.id === selected)
    ? selected
    : (state.sessions.find((session) => session.status === "running")?.id || "");
}

function renderModels() {
  const target = $("#models");
  target.replaceChildren();
  const active = state.models.find((model) => model.status === "active");
  $("#model-status").textContent = active ? active.version : "No active model";
  for (const model of state.models) {
    const row = document.createElement("div");
    row.className = "model-row";
    const info = document.createElement("div");
    const name = document.createElement("div");
    name.className = "model-name";
    name.textContent = model.version;
    const meta = document.createElement("div");
    meta.className = "model-meta";
    meta.textContent = `${model.trained_on_samples} samples · threshold ${Number(model.threshold ?? 0).toFixed(4)}`;
    info.append(name, meta);
    if (model.status === "active") {
      const status = document.createElement("span");
      status.className = "model-state";
      status.textContent = "Active";
      info.append(status);
    } else if (model.status === "trained") {
      const activate = document.createElement("button");
      activate.className = "button";
      activate.type = "button";
      activate.textContent = "Activate";
      activate.addEventListener("click", () => activateModel(model.id));
      row.append(info, activate);
      target.append(row);
      continue;
    }
    row.append(info);
    target.append(row);
  }
  if (!state.models.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "No model metadata found. Check that the configured .keras model file exists.";
    target.append(empty);
  }
}

function renderPackets() {
  const target = $("#packets");
  target.replaceChildren();
  if (!state.packets.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.className = "empty";
    cell.textContent = "No packets yet. Start a session, then send or forward a packet.";
    row.append(cell);
    target.append(row);
    return;
  }
  for (const packet of state.packets) target.append(packetRow(packet));
}

async function refreshSummary() {
  const summary = await api("/api/dashboard/summary");
  $("#stat-packets").textContent = summary.total_packets;
  $("#stat-anomalies").textContent = summary.anomalies;
  $("#stat-benign").textContent = summary.benign;
  $("#stat-sessions").textContent = summary.active_sessions;
}

function packetRow(packet) {
  const row = document.createElement("tr");
  const time = new Date(packet.checked_at);
  const columns = [
    Number.isNaN(time.getTime()) ? "—" : time.toLocaleTimeString(),
    `${escapeText(packet.src_ip)} → ${escapeText(packet.dst_ip)}`,
    escapeText(packet.protocol),
    `${escapeText(packet.packet_size)} B`,
    `${Number(packet.anomaly_score).toFixed(4)} / ${Number(packet.threshold).toFixed(4)}`,
  ];
  for (const value of columns) {
    const cell = document.createElement("td");
    cell.textContent = value;
    row.append(cell);
  }
  const verdict = document.createElement("td");
  const badge = document.createElement("span");
  badge.className = `verdict ${packet.is_anomalous ? "bad" : "good"}`;
  badge.textContent = packet.is_anomalous ? "Anomaly" : "Benign";
  verdict.append(badge);
  row.append(verdict);
  const label = document.createElement("td");
  const actions = document.createElement("div");
  actions.className = "label-actions";
  for (const value of ["normal", "anomalous", "ignore"]) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = value;
    if (packet.training_label === value) button.classList.add("selected");
    button.addEventListener("click", () => labelPacket(packet.packet_id, value));
    actions.append(button);
  }
  label.append(actions);
  row.append(label);
  return row;
}

async function changeSession(session) {
  try {
    const operation = session.status === "running" ? "stop" : "start";
    await api(`/api/monitoring/sessions/${session.id}/${operation}`, { method: "POST" });
    await loadDashboard();
    notify(`Session ${operation === "start" ? "started" : "stopped"}.`);
  } catch (error) { notify(error.message); }
}

async function activateModel(modelId) {
  try {
    await api("/api/models/activate", { method: "POST", body: JSON.stringify({ model_id: modelId }) });
    await loadDashboard();
    notify("Model activated.");
  } catch (error) { notify(error.message); }
}

async function labelPacket(packetId, label) {
  try {
    await api(`/api/packets/${packetId}/label`, { method: "PATCH", body: JSON.stringify({ training_label: label }) });
    state.packets = await api("/api/detections?limit=50");
    renderPackets();
    notify(`Packet labeled ${label}.`);
  } catch (error) { notify(error.message); }
}

async function trainModel() {
  const button = $("#train-model");
  button.disabled = true;
  try {
    const job = await api("/api/models/train", { method: "POST" });
    $("#training-status").textContent = `Training job ${job.job_id} is ${job.status}.`;
    notify("Training queued.");
    pollTraining(job.job_id);
  } catch (error) {
    notify(error.message);
  } finally { button.disabled = false; }
}

async function pollTraining(jobId) {
  const status = $("#training-status");
  const poll = async () => {
    try {
      const job = await api(`/api/models/jobs/${jobId}`);
      status.textContent = `Training ${job.status}. Samples: ${job.samples_used}.${job.error_message ? ` ${job.error_message}` : ""}`;
      if (["completed", "failed"].includes(job.status)) {
        await loadDashboard();
        return;
      }
      setTimeout(poll, 1800);
    } catch (error) { status.textContent = error.message; }
  };
  setTimeout(poll, 1200);
}

function connectLiveSocket(sessionId) {
  state.socket?.close();
  state.socket = null;
  const indicator = document.querySelector(".live-indicator");
  indicator?.classList.remove("connected");
  if (!sessionId || !state.token) return;
  const scheme = location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${scheme}//${location.host}/ws/monitoring/${encodeURIComponent(sessionId)}`);
  state.socket = socket;
  socket.onopen = () => {
    socket.send(JSON.stringify({ token: state.token }));
    indicator?.classList.add("connected");
  };
  socket.onclose = () => indicator?.classList.remove("connected");
  socket.onmessage = (message) => {
    try {
      const event = JSON.parse(message.data);
      if (event.event !== "packet") return;
      state.packets = [event, ...state.packets.filter((packet) => packet.packet_id !== event.packet_id)].slice(0, 50);
      renderPackets();
      refreshSummary().catch((error) => notify(error.message));
    } catch { notify("Received an invalid live event."); }
  };
}

$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorTarget = $("#auth-error");
  errorTarget.textContent = "";
  const email = $("#email").value.trim().toLowerCase();
  const password = $("#password").value;
  try {
    if (state.mode === "register") {
      await api("/api/auth/register", { method: "POST", body: JSON.stringify({ email, password }) });
    }
    const form = new URLSearchParams({ username: email, password });
    const response = await api("/api/auth/login", { method: "POST", body: form });
    state.token = response.access_token;
    localStorage.setItem("monitor-token", state.token);
    setAuthenticated(email);
    await loadDashboard();
  } catch (error) {
    showError(errorTarget, error.message);
  }
});

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
  state.mode = tab.dataset.mode;
  document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item === tab));
  const registering = state.mode === "register";
  $("#auth-title").textContent = registering ? "Create your account" : "Welcome back";
  $("#auth-description").textContent = registering ? "Register a local account for this monitor." : "Sign in to continue to your monitor.";
  $("#auth-submit").textContent = registering ? "Create account" : "Sign in";
  $("#password").autocomplete = registering ? "new-password" : "current-password";
  $("#auth-error").textContent = "";
}));

$("#session-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/monitoring/sessions", {
      method: "POST",
      body: JSON.stringify({
        name: $("#session-name").value.trim(),
        interface: $("#interface").value,
        packet_capture_limit_bytes: Number($("#capture-bytes").value),
      }),
    });
    $("#session-name").value = "";
    await loadDashboard();
    notify("Monitoring session created.");
  } catch (error) { notify(error.message); }
});

$("#train-model").addEventListener("click", trainModel);
$("#refresh").addEventListener("click", () => loadDashboard().catch((error) => notify(error.message)));
$("#logout").addEventListener("click", setAnonymous);
$("#packet-session").addEventListener("change", (event) => connectLiveSocket(event.target.value));

if (state.token) {
  api("/api/auth/me").then((user) => {
    setAuthenticated(user.email);
    return loadDashboard();
  }).catch(setAnonymous);
}
