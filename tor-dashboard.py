#!/usr/bin/env python3
import json
import mimetypes
import os
import re
import socket
import subprocess
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


CONTROL_HOST = os.environ.get("TOR_CONTROL_HOST", "127.0.0.1")
CONTROL_PORT = int(os.environ.get("TOR_CONTROL_PORT", "19051"))
CONTROL_PASSWORD = os.environ.get("TOR_CONTROL_PASSWORD", "vidalia")
DASHBOARD_HOST = os.environ.get("TOR_DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.environ.get("TOR_DASHBOARD_PORT", "8080"))
TOR_SOCKS_HOST = os.environ.get("TOR_SOCKS_HOST", "127.0.0.1")
TOR_SOCKS_PORT = int(os.environ.get("TOR_SOCKS_PORT", "19050"))
TOR_LOG_FILE = os.environ.get("TOR_LOG_FILE", "/run/tor-notice.log")
STATIC_ROOT = os.environ.get("TOR_DASHBOARD_STATIC_ROOT", "/opt/tor-dashboard/static")
VENDOR_ROOT = os.environ.get("TOR_DASHBOARD_VENDOR_ROOT", "/opt/tor-dashboard/vendor")
EXIT_CACHE = {"updated": 0, "data": {}}
EVENTS = deque(maxlen=300)


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tor Dashboard</title>
<style>
:root {
  color-scheme: dark;
  --bg: #101318;
  --panel: #181d24;
  --panel-2: #202733;
  --text: #eef2f7;
  --muted: #a8b3c2;
  --line: #313a48;
  --ok: #53d18c;
  --warn: #f2c94c;
  --bad: #ff6b6b;
  --accent: #8ec5ff;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
main { max-width: 1180px; margin: 0 auto; padding: 24px; }
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
h1 { font-size: 24px; margin: 0; letter-spacing: 0; }
button {
  background: var(--accent);
  border: 0;
  border-radius: 6px;
  color: #07111d;
  cursor: pointer;
  font-weight: 700;
  min-height: 36px;
  padding: 0 14px;
}
button:disabled { cursor: wait; opacity: .65; }
.grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.field { display: grid; gap: 5px; margin-top: 10px; }
input, select, textarea {
  background: #0f1319;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--text);
  font: inherit;
  min-height: 36px;
  padding: 8px 10px;
  width: 100%;
}
textarea { min-height: 120px; resize: vertical; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.chip {
  background: var(--panel-2);
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--text);
  cursor: pointer;
  min-height: 30px;
  padding: 0 10px;
}
.chip.active { background: var(--accent); color: #07111d; }
.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
}
.label { color: var(--muted); font-size: 12px; text-transform: uppercase; }
.value { font-size: 22px; font-weight: 700; margin-top: 4px; overflow-wrap: anywhere; }
.small { color: var(--muted); font-size: 13px; margin-top: 2px; overflow-wrap: anywhere; }
.ok { color: var(--ok); }
.warn { color: var(--warn); }
.bad { color: var(--bad); }
section { margin-top: 18px; }
.section-title { align-items: center; display: flex; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
h2 { font-size: 16px; margin: 0; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid var(--line); padding: 10px 8px; text-align: left; vertical-align: top; }
th { color: var(--muted); font-size: 12px; font-weight: 600; text-transform: uppercase; }
tr:last-child td { border-bottom: 0; }
.path { display: flex; flex-wrap: wrap; gap: 8px; }
.relay {
  background: var(--panel-2);
  border: 1px solid var(--line);
  border-radius: 6px;
  min-width: 180px;
  padding: 8px;
}
.relay strong { display: block; overflow-wrap: anywhere; }
.relay span { color: var(--muted); display: block; font-size: 12px; overflow-wrap: anywhere; }
.notice {
  background: #241c1c;
  border: 1px solid #5f3838;
  border-radius: 8px;
  color: #ffd6d6;
  margin-top: 14px;
  padding: 12px;
}
.log {
  background: #0b0e13;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: #d7dee9;
  max-height: 260px;
  overflow: auto;
  padding: 10px;
  white-space: pre-wrap;
}
.health { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.health-item { background: var(--panel-2); border: 1px solid var(--line); border-radius: 6px; padding: 8px; }
@media (max-width: 900px) {
  main { padding: 16px; }
  header { align-items: flex-start; flex-direction: column; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .two { grid-template-columns: 1fr; }
  .health { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  table, thead, tbody, th, td, tr { display: block; }
  thead { display: none; }
  td { padding: 8px 0; }
}
@media (max-width: 520px) {
  .grid { grid-template-columns: 1fr; }
  .health { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Tor Dashboard</h1>
      <div class="small" id="updated">Loading...</div>
    </div>
    <button id="newnym" type="button">New Identity</button>
  </header>
  <div id="error"></div>
  <div class="grid">
    <div class="card"><div class="label">Bootstrap</div><div class="value" id="bootstrap">-</div><div class="small" id="bootstrapText"></div></div>
    <div class="card"><div class="label">Tor Version</div><div class="value" id="version">-</div></div>
    <div class="card"><div class="label">Built Circuits</div><div class="value" id="built">-</div></div>
    <div class="card"><div class="label">Exit Countries</div><div class="value" id="countries">-</div></div>
    <div class="card"><div class="label">Current Exit</div><div class="value" id="exitCountry">-</div><div class="small" id="exitIp"></div><div class="small" id="exitMeta"></div></div>
  </div>
  <section class="two">
    <div class="card">
      <div class="section-title"><h2>Exit Country</h2><div class="small" id="exitPolicyState"></div></div>
      <div class="chips" id="countryChips"></div>
      <div class="actions">
        <button id="applyCountries" type="button">Apply</button>
        <button id="clearCountries" type="button">Clear</button>
      </div>
    </div>
    <div class="card">
      <div class="section-title"><h2>Identity</h2><div class="small" id="identityState"></div></div>
      <div class="field">
        <label class="label" for="autoNewnym">Auto New Identity</label>
        <select id="autoNewnym">
          <option value="0">Off</option>
          <option value="300">Every 5 minutes</option>
          <option value="600">Every 10 minutes</option>
          <option value="1800">Every 30 minutes</option>
        </select>
      </div>
      <div class="actions">
        <button id="clearDirty" type="button">Close Dirty Circuits</button>
      </div>
    </div>
  </section>
  <section class="card">
    <div class="section-title"><h2>Health Checks</h2><div class="small" id="healthUpdated"></div></div>
    <div class="health" id="health"></div>
  </section>
  <section class="two">
    <div class="card">
      <div class="section-title"><h2>DNS Leak Check</h2><div class="small" id="dnsLeakState"></div></div>
      <div class="small" id="dnsLeakText">Not run yet.</div>
      <div class="actions"><button id="runDnsLeak" type="button">Run Check</button></div>
    </div>
    <div class="card">
      <div class="section-title"><h2>WebRTC Leak Check</h2><div class="small" id="webrtcState"></div></div>
      <div class="small" id="webrtcText">Not run yet.</div>
      <div class="actions"><button id="runWebrtc" type="button">Run Local Check</button></div>
    </div>
  </section>
  <section class="card">
    <div class="section-title"><h2>Bridges</h2><div class="small" id="bridgeState"></div></div>
    <div class="field">
      <label class="label" for="bridges">Bridge lines</label>
      <textarea id="bridges" spellcheck="false" placeholder="obfs4 1.2.3.4:443 FINGERPRINT cert=... iat-mode=0"></textarea>
    </div>
    <div class="actions">
      <button id="enableBridges" type="button">Enable Bridges</button>
      <button id="disableBridges" type="button">Disable Bridges</button>
    </div>
  </section>
  <section class="card">
    <div class="section-title"><h2>Active Connections</h2><div class="small" id="streamCount"></div></div>
    <table>
      <thead><tr><th>ID</th><th>Status</th><th>Target</th><th>Exit</th></tr></thead>
      <tbody id="streams"></tbody>
    </table>
  </section>
  <section class="card">
    <div class="section-title"><h2>Circuits</h2><div class="small" id="count"></div></div>
    <table>
      <thead><tr><th>ID</th><th>Status</th><th>Purpose</th><th>Route</th></tr></thead>
      <tbody id="circuits"></tbody>
    </table>
  </section>
  <section class="card">
    <div class="section-title"><h2>Logs</h2><div class="small" id="logCount"></div></div>
    <div class="log" id="logs">No dashboard events yet.</div>
  </section>
</main>
<script>
const $ = (id) => document.getElementById(id);
const commonCountries = ["DE", "NL", "US", "GB", "FR", "SE", "CH", "CA", "TR"];
const selectedCountries = new Set();
let countriesDirty = false;
let autoTimer = null;
let lastNewnym = Number(localStorage.getItem("lastNewnym") || "0");
const regionNames = typeof Intl !== "undefined" && Intl.DisplayNames
  ? new Intl.DisplayNames(["en"], { type: "region" })
  : null;

function flag(cc) {
  if (!cc || cc.length !== 2 || cc === "??") return "??";
  const upper = cc.toUpperCase();
  return [...upper].map(c => String.fromCodePoint(127397 + c.charCodeAt(0))).join("");
}

function countryLabel(cc) {
  if (!cc || cc === "??") return "Unknown";
  const upper = cc.toUpperCase();
  let name = upper;
  try { if (regionNames) name = regionNames.of(upper) || upper; } catch (_) {}
  return `${flag(upper)} ${name} (${upper})`;
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"]/g, s => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[s]));
}

function setError(message) {
  $("error").innerHTML = message ? `<div class="notice">${esc(message)}</div>` : "";
}

function postJson(url, body = {}) {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async res => {
    const payload = await res.json().catch(() => ({}));
    if (!res.ok || payload.ok === false) throw new Error(payload.error || res.statusText);
    return payload;
  });
}

function renderCountryChips() {
  $("countryChips").innerHTML = commonCountries.map(cc => `
    <button class="chip ${selectedCountries.has(cc) ? "active" : ""}" type="button" data-country="${cc}">
      ${flag(cc)} ${cc}
    </button>`).join("");
  document.querySelectorAll("[data-country]").forEach(button => {
    button.addEventListener("click", () => {
      const cc = button.dataset.country;
      selectedCountries.has(cc) ? selectedCountries.delete(cc) : selectedCountries.add(cc);
      countriesDirty = true;
      renderCountryChips();
    });
  });
}

function renderHealth(items) {
  $("health").innerHTML = (items || []).map(item => `
    <div class="health-item">
      <div class="label">${esc(item.name)}</div>
      <div class="${item.ok ? "ok" : "bad"}">${item.ok ? "OK" : "FAIL"}</div>
      <div class="small">${esc(item.detail || "")}</div>
    </div>`).join("");
  $("healthUpdated").textContent = items ? `${items.length} checks` : "";
}

function renderSettings(settings) {
  if (!settings) return;
  const exitNodes = settings.exitNodes || "";
  $("exitPolicyState").textContent = exitNodes ? `ExitNodes ${exitNodes} StrictNodes ${settings.strictNodes || "0"}` : "Any exit country";
  if (!countriesDirty) {
    selectedCountries.clear();
    for (const cc of exitNodes.match(/[A-Za-z]{2}/g) || []) selectedCountries.add(cc.toUpperCase());
    renderCountryChips();
  }
  $("bridgeState").textContent = settings.useBridges === "1" ? "Enabled" : "Disabled";
  if (!$("bridges").matches(":focus")) $("bridges").value = (settings.bridges || []).join("\n");
}

function renderLogs(events) {
  $("logCount").textContent = `${(events || []).length} events`;
  $("logs").textContent = (events || []).map(e => `${e.time} ${e.message}`).join("\n") || "No dashboard events yet.";
}

function render(data) {
  setError(data.error || "");
  data.circuits = data.circuits || [];
  data.streams = data.streams || [];
  $("bootstrap").textContent = `${data.bootstrap.progress ?? 0}%`;
  $("bootstrap").className = `value ${(data.bootstrap.progress ?? 0) >= 100 ? "ok" : "warn"}`;
  $("bootstrapText").textContent = data.bootstrap.summary || data.bootstrap.tag || "";
  $("version").textContent = data.version || "-";
  $("built").textContent = data.circuits.filter(c => c.status === "BUILT").length;
  const exits = [...new Set(data.circuits.map(c => c.relays[c.relays.length - 1]).filter(Boolean).map(r => r.country).filter(Boolean))];
  $("countries").textContent = exits.length ? exits.map(cc => flag(cc)).join(" ") : "-";
  const exit = data.currentExit || {};
  $("exitCountry").textContent = exit.country ? flag(exit.country) : "-";
  $("exitIp").textContent = exit.ip ? `${countryLabel(exit.country)} ${exit.ip}${exit.isTor ? " Tor" : ""}` : "No exit check yet";
  $("exitMeta").textContent = [exit.city, exit.region, exit.isp, exit.source || exit.error].filter(Boolean).join(" | ");
  $("count").textContent = `${data.circuits.length} total`;
  $("streamCount").textContent = `${data.streams.length} active`;
  $("updated").textContent = `Updated ${new Date().toLocaleTimeString()}`;
  $("identityState").textContent = lastNewnym ? `Last changed ${new Date(lastNewnym).toLocaleTimeString()}` : "Manual";
  renderHealth(data.health);
  renderSettings(data.settings);
  renderLogs(data.events);

  $("streams").innerHTML = data.streams.map(s => {
    const exitRelay = s.exitRelay || {};
    const exitText = exitRelay.ip ? `${countryLabel(exitRelay.country)} ${exitRelay.ip}` : "-";
    return `
      <tr>
        <td>${esc(s.id)} / circuit ${esc(s.circuitId || "-")}</td>
        <td class="${s.status === "SUCCEEDED" ? "ok" : "warn"}">${esc(s.status)}</td>
        <td>${esc(s.target || "-")}</td>
        <td>${esc(exitText)}</td>
      </tr>`;
  }).join("") || `<tr><td colspan="4">No active streams yet.</td></tr>`;

  $("circuits").innerHTML = data.circuits.map(c => `
    <tr>
      <td>${esc(c.id)}</td>
      <td class="${c.status === "BUILT" ? "ok" : "warn"}">${esc(c.status)}</td>
      <td>${esc(c.purpose || "-")}<div class="small">${esc(c.flags || "")}</div><button type="button" data-close-circuit="${esc(c.id)}">Close</button></td>
      <td><div class="path">${c.relays.map(r => `
        <div class="relay">
          <strong>${esc(r.nickname || "unknown")}</strong>
          <span>${esc(countryLabel(r.country))} ${esc(r.ip || "")}</span>
          <span>${esc([r.flags, r.bandwidth ? "bw " + r.bandwidth : ""].filter(Boolean).join(" | "))}</span>
          <span>${esc(r.fingerprint ? r.fingerprint.slice(0, 12) : "")}</span>
        </div>`).join("")}</div></td>
    </tr>`).join("") || `<tr><td colspan="4">No circuits yet.</td></tr>`;

  document.querySelectorAll("[data-close-circuit]").forEach(button => {
    button.addEventListener("click", async () => {
      await postJson("/api/close-circuit", { id: button.dataset.closeCircuit });
      await refresh();
    });
  });
}

async function refresh() {
  try {
    const res = await fetch("/api/status", { cache: "no-store" });
    render(await res.json());
  } catch (err) {
    setError(String(err));
  }
}

$("newnym").addEventListener("click", async () => {
  $("newnym").disabled = true;
  try {
    await postJson("/api/newnym");
    lastNewnym = Date.now();
    localStorage.setItem("lastNewnym", String(lastNewnym));
    await refresh();
  } finally {
    setTimeout(() => { $("newnym").disabled = false; }, 4000);
  }
});

$("applyCountries").addEventListener("click", async () => {
  await postJson("/api/exit-policy", { countries: [...selectedCountries], strict: true });
  countriesDirty = false;
  await postJson("/api/newnym");
  await refresh();
});

$("clearCountries").addEventListener("click", async () => {
  selectedCountries.clear();
  await postJson("/api/exit-policy", { countries: [], strict: false });
  countriesDirty = false;
  await postJson("/api/newnym");
  renderCountryChips();
  await refresh();
});

$("clearDirty").addEventListener("click", async () => {
  await postJson("/api/close-dirty-circuits");
  await refresh();
});

$("enableBridges").addEventListener("click", async () => {
  const bridges = $("bridges").value.split(/\n+/).map(line => line.trim()).filter(Boolean);
  await postJson("/api/bridges", { enabled: true, bridges });
  await refresh();
});

$("disableBridges").addEventListener("click", async () => {
  await postJson("/api/bridges", { enabled: false, bridges: [] });
  await refresh();
});

$("runDnsLeak").addEventListener("click", async () => {
  $("dnsLeakState").textContent = "Running";
  try {
    const result = await postJson("/api/dns-leak");
    $("dnsLeakState").textContent = result.ok ? "OK" : "Check failed";
    $("dnsLeakText").textContent = result.detail || JSON.stringify(result);
  } catch (err) {
    $("dnsLeakState").textContent = "Failed";
    $("dnsLeakText").textContent = String(err);
  }
});

$("runWebrtc").addEventListener("click", async () => {
  $("webrtcState").textContent = "Running";
  if (!window.RTCPeerConnection) {
    $("webrtcState").textContent = "Disabled";
    $("webrtcText").textContent = "RTCPeerConnection is unavailable, which is the preferred state for Tor browsing.";
    return;
  }
  const candidates = new Set();
  const pc = new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }] });
  pc.createDataChannel("leak-test");
  pc.onicecandidate = event => {
    if (!event.candidate) return;
    const matches = event.candidate.candidate.match(/([0-9]{1,3}(?:\.[0-9]{1,3}){3})/g) || [];
    matches.forEach(ip => candidates.add(ip));
  };
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  setTimeout(() => {
    pc.close();
    const ips = [...candidates];
    $("webrtcState").textContent = ips.length ? "Candidates found" : "No candidates";
    $("webrtcText").textContent = ips.length ? ips.join(", ") : "No WebRTC IP candidates were exposed.";
  }, 3000);
});

$("autoNewnym").value = localStorage.getItem("autoNewnym") || "0";
$("autoNewnym").addEventListener("change", () => {
  localStorage.setItem("autoNewnym", $("autoNewnym").value);
  setupAutoNewnym();
});

function setupAutoNewnym() {
  if (autoTimer) clearInterval(autoTimer);
  const seconds = Number($("autoNewnym").value || "0");
  if (!seconds) return;
  autoTimer = setInterval(async () => {
    await postJson("/api/newnym");
    lastNewnym = Date.now();
    localStorage.setItem("lastNewnym", String(lastNewnym));
    await refresh();
  }, seconds * 1000);
}

renderCountryChips();
setupAutoNewnym();
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""


class TorControl:
    def __init__(self):
        self.sock = socket.create_connection((CONTROL_HOST, CONTROL_PORT), timeout=5)
        self.file = self.sock.makefile("rwb", buffering=0)
        self.command('AUTHENTICATE "{}"'.format(CONTROL_PASSWORD.replace("\\", "\\\\").replace('"', '\\"')))

    def close(self):
        try:
            self.command("QUIT")
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass

    def command(self, command):
        self.file.write((command + "\r\n").encode("utf-8"))
        return self._read_response()

    def _read_response(self):
        items = {}
        lines = []
        while True:
            raw = self.file.readline()
            if not raw:
                raise RuntimeError("Tor control connection closed")
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if len(line) < 4 or not line[:3].isdigit():
                lines.append(line)
                continue
            code = line[:3]
            sep = line[3]
            rest = line[4:]
            if code not in ("250", "251"):
                raise RuntimeError(rest or line)
            if sep == "+":
                block = []
                while True:
                    block_line = self.file.readline().decode("utf-8", "replace").rstrip("\r\n")
                    if block_line == ".":
                        break
                    block.append(block_line[1:] if block_line.startswith("..") else block_line)
                key = rest[:-1] if rest.endswith("=") else rest.split("=", 1)[0]
                items[key] = "\n".join(block)
            elif rest and "=" in rest:
                key, value = rest.split("=", 1)
                if key in items and items[key]:
                    items[key] = "{}\n{}".format(items[key], value)
                else:
                    items[key] = value
            elif rest and rest != "OK":
                lines.append(rest)
            if sep == " ":
                return {"items": items, "lines": lines}


def record_event(message):
    EVENTS.append({"time": time.strftime("%H:%M:%S"), "message": message})


def dashboard_logs():
    lines = []
    try:
        with open(TOR_LOG_FILE, "r", encoding="utf-8", errors="replace") as handle:
            lines.extend(handle.readlines()[-200:])
    except Exception:
        pass
    event_lines = ["{} dashboard: {}\n".format(event["time"], event["message"]) for event in EVENTS]
    combined = lines + event_lines
    return [{"time": "", "message": line.rstrip("\n")} for line in combined[-250:]]


def classified_logs():
    items = []
    for item in dashboard_logs():
        message = item["message"]
        lower = message.lower()
        level = "info"
        category = "general"
        if "warn" in lower or "failed" in lower or "error" in lower:
            level = "warn"
        if "bootstrapped" in lower:
            category = "bootstrap"
        elif "bridge" in lower:
            category = "bridge"
        elif "circuit" in lower:
            category = "circuit"
        elif "control" in lower:
            category = "control"
        elif "dashboard:" in lower:
            category = "dashboard"
        items.append({"time": item["time"], "message": message, "level": level, "category": category})
    return items


def control_quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def control_getconf(control, *keys):
    response = control.command("GETCONF " + " ".join(keys))["items"]
    return {key: response.get(key, "") for key in keys}


def socket_check(host, port, timeout=2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "{}:{}".format(host, port)
    except Exception as exc:
        return False, str(exc)


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tor Dashboard</title>
<style>
:root {
  color-scheme: dark;
  --bg: #101318;
  --panel: #181d24;
  --panel-2: #202733;
  --text: #eef2f7;
  --muted: #a8b3c2;
  --line: #313a48;
  --ok: #53d18c;
  --warn: #f2c94c;
  --bad: #ff6b6b;
  --accent: #8ec5ff;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
button {
  background: var(--accent);
  border: 0;
  border-radius: 6px;
  color: #07111d;
  cursor: pointer;
  font-weight: 700;
  min-height: 36px;
  padding: 0 14px;
}
button.secondary {
  background: var(--panel-2);
  border: 1px solid var(--line);
  color: var(--text);
}
button:disabled { cursor: wait; opacity: .65; }
input, select, textarea {
  background: #0f1319;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--text);
  font: inherit;
  min-height: 36px;
  padding: 8px 10px;
  width: 100%;
}
textarea { min-height: 120px; resize: vertical; }
main { max-width: 1240px; margin: 0 auto; padding: 24px; }
header { align-items: center; display: flex; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
h1 { font-size: 24px; margin: 0; letter-spacing: 0; }
h2 { font-size: 16px; margin: 0; }
section { margin-top: 18px; }
.grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
.label { color: var(--muted); font-size: 12px; text-transform: uppercase; }
.value { font-size: 22px; font-weight: 700; margin-top: 4px; overflow-wrap: anywhere; }
.small { color: var(--muted); font-size: 13px; margin-top: 2px; overflow-wrap: anywhere; }
.ok { color: var(--ok); }
.warn { color: var(--warn); }
.bad { color: var(--bad); }
.section-title { align-items: center; display: flex; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.field { display: grid; gap: 5px; margin-top: 10px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.chip { background: var(--panel-2); border: 1px solid var(--line); border-radius: 999px; color: var(--text); cursor: pointer; min-height: 30px; padding: 0 10px; }
.chip.active { background: var(--accent); color: #07111d; }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.tab { background: var(--panel-2); color: var(--text); }
.tab.active { background: var(--accent); color: #07111d; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid var(--line); padding: 10px 8px; text-align: left; vertical-align: top; }
th { color: var(--muted); font-size: 12px; font-weight: 600; text-transform: uppercase; }
tr:last-child td { border-bottom: 0; }
.path { display: flex; flex-wrap: wrap; gap: 8px; }
.relay { background: var(--panel-2); border: 1px solid var(--line); border-radius: 6px; min-width: 180px; padding: 8px; }
.relay strong { display: block; overflow-wrap: anywhere; }
.relay span { color: var(--muted); display: block; font-size: 12px; overflow-wrap: anywhere; }
.notice { background: #241c1c; border: 1px solid #5f3838; border-radius: 8px; color: #ffd6d6; margin-top: 14px; padding: 12px; }
.log { background: #0b0e13; border: 1px solid var(--line); border-radius: 6px; color: #d7dee9; max-height: 320px; overflow: auto; padding: 10px; white-space: pre-wrap; }
.health { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.health-item { background: var(--panel-2); border: 1px solid var(--line); border-radius: 6px; padding: 8px; }
.toolbar { align-items: center; display: flex; flex-wrap: wrap; gap: 8px; }
.steps { display: grid; gap: 10px; }
.step { background: var(--panel-2); border: 1px solid var(--line); border-radius: 8px; padding: 10px; }
.step.active { border-color: var(--accent); }
.circuit-line { align-items: stretch; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.hop-title { color: var(--muted); font-size: 12px; text-transform: uppercase; }
.split { display: grid; grid-template-columns: 2fr 1fr; gap: 12px; }
@media (max-width: 900px) {
  main { padding: 16px; }
  header { align-items: flex-start; flex-direction: column; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .two, .health, .split, .circuit-line { grid-template-columns: 1fr; }
  table, thead, tbody, th, td, tr { display: block; }
  thead { display: none; }
  td { padding: 8px 0; }
}
@media (max-width: 520px) {
  .grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div id="root"></div>
<script src="/vendor/react.production.min.js"></script>
<script src="/vendor/react-dom.production.min.js"></script>
<script src="/static/app.js"></script>
</body>
</html>
"""


def parse_bootstrap(value):
    result = {"progress": 0, "tag": "", "summary": ""}
    if not value:
        return result
    for key, attr in (("PROGRESS", "progress"), ("TAG", "tag"), ("SUMMARY", "summary")):
        match = re.search(r'{}=("[^"]*"|\S+)'.format(key), value)
        if not match:
            continue
        parsed = match.group(1).strip('"')
        result[attr] = int(parsed) if attr == "progress" and parsed.isdigit() else parsed
    return result


def parse_kv(tokens):
    values = {}
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            values[key] = value.strip('"')
    return values


def relay_identity(part):
    part = part.strip()
    if not part:
        return "", ""
    if part.startswith("$"):
        part = part[1:]
    if "~" in part:
        fingerprint, nickname = part.split("~", 1)
    else:
        fingerprint, nickname = part, ""
    return fingerprint, nickname


def relay_details(control, fingerprint, nickname, cache):
    if fingerprint in cache:
        cached = dict(cache[fingerprint])
        if nickname and not cached.get("nickname"):
            cached["nickname"] = nickname
        return cached
    relay = {"fingerprint": fingerprint, "nickname": nickname, "ip": "", "country": "??"}
    try:
        ns = control.command("GETINFO ns/id/{}".format(fingerprint))["items"].get("ns/id/{}".format(fingerprint), "")
        first = next((line for line in ns.splitlines() if line.startswith("r ")), "")
        flags = next((line[2:] for line in ns.splitlines() if line.startswith("s ")), "")
        bandwidth_line = next((line for line in ns.splitlines() if line.startswith("w ")), "")
        fields = first.split()
        if len(fields) >= 7:
            relay["nickname"] = relay["nickname"] or fields[1]
            relay["ip"] = fields[6]
            relay["country"] = control.command("GETINFO ip-to-country/{}".format(relay["ip"]))["items"].get("ip-to-country/{}".format(relay["ip"]), "??").upper()
            relay["flags"] = flags
            bandwidth = re.search(r"Bandwidth=(\d+)", bandwidth_line)
            relay["bandwidth"] = bandwidth.group(1) if bandwidth else ""
    except Exception:
        pass
    cache[fingerprint] = relay
    return relay


def current_exit(control):
    now = time.time()
    if EXIT_CACHE["data"] and now - EXIT_CACHE["updated"] < 20:
        return EXIT_CACHE["data"]
    result = {
        "ip": "",
        "country": "??",
        "countryName": "",
        "region": "",
        "city": "",
        "isp": "",
        "asn": "",
        "isTor": False,
        "source": "",
        "error": "",
    }
    try:
        completed = subprocess.run(
            [
                "curl",
                "-fsS",
                "--max-time",
                "12",
                "--socks5-hostname",
                "{}:{}".format(TOR_SOCKS_HOST, TOR_SOCKS_PORT),
                "https://check.torproject.org/api/ip",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        result["ip"] = payload.get("IP", "")
        result["isTor"] = bool(payload.get("IsTor", False))
        if result["ip"]:
            geo_completed = subprocess.run(
                [
                    "curl",
                    "-fsS",
                    "--max-time",
                    "12",
                    "--socks5-hostname",
                    "{}:{}".format(TOR_SOCKS_HOST, TOR_SOCKS_PORT),
                    "https://ipwho.is/{}".format(result["ip"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            geo_payload = json.loads(geo_completed.stdout)
            if geo_payload.get("success", True):
                connection = geo_payload.get("connection") or {}
                result["country"] = (geo_payload.get("country_code") or "??").upper()
                result["countryName"] = geo_payload.get("country") or ""
                result["region"] = geo_payload.get("region") or ""
                result["city"] = geo_payload.get("city") or ""
                result["isp"] = connection.get("isp") or connection.get("org") or ""
                result["asn"] = str(connection.get("asn") or "")
                result["source"] = "ipwho.is"
            else:
                raise RuntimeError(geo_payload.get("message") or "ipwho.is lookup failed")
    except Exception as exc:
        result["error"] = str(exc)
        if result["ip"]:
            try:
                result["country"] = control.command("GETINFO ip-to-country/{}".format(result["ip"]))["items"].get("ip-to-country/{}".format(result["ip"]), "??").upper()
                result["source"] = "Tor GeoIP fallback"
            except Exception:
                pass
    EXIT_CACHE["updated"] = now if result["ip"] else now - 15
    EXIT_CACHE["data"] = result
    return result


def health_checks(control, info, exit_info):
    control_ok, control_detail = socket_check(CONTROL_HOST, CONTROL_PORT)
    socks_ok, socks_detail = socket_check(TOR_SOCKS_HOST, TOR_SOCKS_PORT)
    privoxy_ok, privoxy_detail = socket_check("127.0.0.1", 8118)
    bootstrap = parse_bootstrap(info.get("status/bootstrap-phase", ""))
    return [
        {"name": "Tor Bootstrap", "ok": bootstrap.get("progress", 0) >= 100, "detail": "{}% {}".format(bootstrap.get("progress", 0), bootstrap.get("summary", ""))},
        {"name": "ControlPort", "ok": control_ok, "detail": control_detail},
        {"name": "SOCKS", "ok": socks_ok, "detail": socks_detail},
        {"name": "Privoxy", "ok": privoxy_ok, "detail": privoxy_detail},
        {"name": "Public Exit", "ok": bool(exit_info.get("ip")), "detail": "{} {}".format(exit_info.get("ip", ""), exit_info.get("source", ""))},
        {"name": "Tor Check", "ok": bool(exit_info.get("isTor")), "detail": "IsTor={}".format(str(bool(exit_info.get("isTor"))).lower())},
    ]


def tor_settings(control):
    values = control_getconf(control, "ExitNodes", "ExcludeExitNodes", "StrictNodes", "UseBridges", "Bridge")
    bridges = values.get("Bridge", "")
    if isinstance(bridges, str):
        bridges = [line for line in bridges.splitlines() if line]
    return {
        "exitNodes": values.get("ExitNodes", ""),
        "excludeExitNodes": values.get("ExcludeExitNodes", ""),
        "strictNodes": values.get("StrictNodes", "0"),
        "useBridges": values.get("UseBridges", "0"),
        "bridges": bridges,
    }


def risk_summary(settings, exit_info):
    risks = []
    risks.append({"name": "Dashboard Binding", "level": "ok", "detail": "ruh.sh publishes dashboard on 127.0.0.1 by default"})
    risks.append({"name": "Control Password", "level": "warn" if CONTROL_PASSWORD == "vidalia" else "ok", "detail": "default password" if CONTROL_PASSWORD == "vidalia" else "custom password"})
    risks.append({"name": "Tor Exit", "level": "ok" if exit_info.get("isTor") else "warn", "detail": "IsTor={}".format(str(bool(exit_info.get("isTor"))).lower())})
    risks.append({"name": "Exit Policy", "level": "warn" if settings.get("strictNodes") == "1" else "ok", "detail": settings.get("exitNodes") or "any country"})
    risks.append({"name": "Bridges", "level": "ok" if settings.get("useBridges") == "1" else "info", "detail": "enabled" if settings.get("useBridges") == "1" else "disabled"})
    return risks


def apply_profile(control, profile):
    if profile == "default":
        control.command("RESETCONF ExitNodes ExcludeExitNodes StrictNodes UseBridges Bridge")
    elif profile == "stable":
        control.command("RESETCONF ExitNodes ExcludeExitNodes StrictNodes")
    else:
        raise ValueError("Unknown profile")
    record_event("Profile applied: {}".format(profile))


def tor_status():
    control = TorControl()
    cache = {}
    try:
        info = control.command("GETINFO version status/bootstrap-phase circuit-status stream-status")["items"]
        circuits = []
        for line in info.get("circuit-status", "").splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            circ_id, status = parts[:2]
            path = parts[2] if len(parts) >= 3 and "=" not in parts[2] else ""
            attrs = parse_kv(parts[3:] if path else parts[2:])
            relays = []
            for hop in path.split(","):
                fingerprint, nickname = relay_identity(hop)
                if fingerprint:
                    relays.append(relay_details(control, fingerprint, nickname, cache))
            circuits.append({
                "id": circ_id,
                "status": status,
                "purpose": attrs.get("PURPOSE", ""),
                "created": attrs.get("TIME_CREATED", ""),
                "relays": relays,
            })
        circuit_by_id = {circuit["id"]: circuit for circuit in circuits}
        streams = []
        for line in info.get("stream-status", "").splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            stream_id, status, circuit_id, target = parts[:4]
            circuit = circuit_by_id.get(circuit_id, {})
            relays = circuit.get("relays", [])
            streams.append({
                "id": stream_id,
                "status": status,
                "circuitId": circuit_id,
                "target": target,
                "exitRelay": relays[-1] if relays else {},
            })
        exit_info = current_exit(control)
        settings = tor_settings(control)
        return {
            "version": info.get("version", ""),
            "bootstrap": parse_bootstrap(info.get("status/bootstrap-phase", "")),
            "circuits": circuits,
            "streams": streams,
            "currentExit": exit_info,
            "health": health_checks(control, info, exit_info),
            "settings": settings,
            "events": classified_logs(),
            "risks": risk_summary(settings, exit_info),
            "error": "",
        }
    finally:
        control.close()


def timed_curl(name, args):
    start = time.time()
    try:
        completed = subprocess.run(args, check=True, capture_output=True, text=True, timeout=20)
        elapsed = int((time.time() - start) * 1000)
        return {"name": name, "ok": True, "ms": elapsed, "detail": completed.stdout[:500]}
    except Exception as exc:
        elapsed = int((time.time() - start) * 1000)
        return {"name": name, "ok": False, "ms": elapsed, "detail": str(exc)}


def run_proxy_tests():
    tests = [
        timed_curl("SOCKS Tor check", ["curl", "-fsS", "--max-time", "15", "--socks5-hostname", "{}:{}".format(TOR_SOCKS_HOST, TOR_SOCKS_PORT), "https://check.torproject.org/api/ip"]),
        timed_curl("HTTP Privoxy Tor check", ["curl", "-fsS", "--max-time", "15", "--proxy", "http://127.0.0.1:8118", "https://check.torproject.org/api/ip"]),
        timed_curl("SOCKS remote DNS", ["curl", "-fsS", "--max-time", "15", "--socks5-hostname", "{}:{}".format(TOR_SOCKS_HOST, TOR_SOCKS_PORT), "https://example.com/"]),
        timed_curl("GeoIP lookup", ["curl", "-fsS", "--max-time", "15", "--socks5-hostname", "{}:{}".format(TOR_SOCKS_HOST, TOR_SOCKS_PORT), "https://ipwho.is/"]),
    ]
    record_event("Proxy test center ran {} checks".format(len(tests)))
    return {"ok": all(test["ok"] for test in tests), "tests": tests}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_static(self, root, prefix, head_only=False):
        relative = self.path[len(prefix):].split("?", 1)[0].lstrip("/")
        if not relative or ".." in relative.split("/"):
            self.send_error(404)
            return
        path = os.path.abspath(os.path.join(root, relative))
        root_abs = os.path.abspath(root)
        if not path.startswith(root_abs + os.sep):
            self.send_error(404)
            return
        try:
            with open(path, "rb") as handle:
                body = handle.read()
        except OSError:
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if path.endswith(".js"):
            content_type = "application/javascript; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if prefix == "/static/" else "public, max-age=31536000, immutable")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def send_index(self, head_only=False):
        body = INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_HEAD(self):
        if self.path == "/" or self.path.startswith("/?"):
            self.send_index(head_only=True)
            return
        if self.path.startswith("/static/"):
            self.send_static(STATIC_ROOT, "/static/", head_only=True)
            return
        if self.path.startswith("/vendor/"):
            self.send_static(VENDOR_ROOT, "/vendor/", head_only=True)
            return
        self.send_error(404)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self.send_index()
            return
        if self.path.startswith("/static/"):
            self.send_static(STATIC_ROOT, "/static/")
            return
        if self.path.startswith("/vendor/"):
            self.send_static(VENDOR_ROOT, "/vendor/")
            return
        if self.path == "/api/status":
            try:
                self.send_json(tor_status())
            except Exception as exc:
                self.send_json({"version": "", "bootstrap": {}, "circuits": [], "streams": [], "currentExit": {}, "error": str(exc)}, status=503)
            return
        if self.path == "/api/proxy-tests":
            try:
                self.send_json(run_proxy_tests())
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "tests": []}, status=503)
            return
        self.send_error(404)

    def do_POST(self):
        if self.path == "/api/newnym":
            try:
                control = TorControl()
                try:
                    control.command("SIGNAL NEWNYM")
                    EXIT_CACHE["updated"] = 0
                    record_event("SIGNAL NEWNYM sent")
                finally:
                    control.close()
                self.send_json({"ok": True})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=503)
            return
        if self.path == "/api/exit-policy":
            try:
                body = self.read_json()
                countries = []
                for item in body.get("countries", []):
                    cc = str(item).strip().lower()
                    if re.fullmatch(r"[a-z]{2}", cc):
                        countries.append("{" + cc + "}")
                excluded = []
                for item in body.get("excluded", []):
                    cc = str(item).strip().lower()
                    if re.fullmatch(r"[a-z]{2}", cc):
                        excluded.append("{" + cc + "}")
                control = TorControl()
                try:
                    if countries or excluded:
                        args = ["StrictNodes={}".format("1" if body.get("strict", True) else "0")]
                        args.append("ExitNodes={}".format(control_quote(",".join(countries))) if countries else "ExitNodes")
                        args.append("ExcludeExitNodes={}".format(control_quote(",".join(excluded))) if excluded else "ExcludeExitNodes")
                        control.command("SETCONF {}".format(" ".join(args)))
                        record_event("Exit policy set preferred={} excluded={}".format(",".join(countries) or "-", ",".join(excluded) or "-"))
                    else:
                        control.command("RESETCONF ExitNodes ExcludeExitNodes StrictNodes")
                        record_event("Exit policy cleared")
                    EXIT_CACHE["updated"] = 0
                finally:
                    control.close()
                self.send_json({"ok": True})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=503)
            return
        if self.path == "/api/profile":
            try:
                body = self.read_json()
                control = TorControl()
                try:
                    apply_profile(control, str(body.get("profile", "")))
                    control.command("SIGNAL NEWNYM")
                    EXIT_CACHE["updated"] = 0
                finally:
                    control.close()
                self.send_json({"ok": True})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=503)
            return
        if self.path == "/api/close-circuit":
            try:
                body = self.read_json()
                circuit_id = str(body.get("id", "")).strip()
                if not circuit_id.isdigit():
                    raise ValueError("Invalid circuit id")
                control = TorControl()
                try:
                    control.command("CLOSECIRCUIT {} IfUnused".format(circuit_id))
                    record_event("Circuit {} close requested".format(circuit_id))
                finally:
                    control.close()
                self.send_json({"ok": True})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=503)
            return
        if self.path == "/api/close-dirty-circuits":
            try:
                control = TorControl()
                closed = 0
                try:
                    info = control.command("GETINFO circuit-status")["items"].get("circuit-status", "")
                    for line in info.splitlines():
                        parts = line.split()
                        if len(parts) >= 2 and parts[0].isdigit() and parts[1] == "BUILT":
                            control.command("CLOSECIRCUIT {} IfUnused".format(parts[0]))
                            closed += 1
                    control.command("SIGNAL NEWNYM")
                    EXIT_CACHE["updated"] = 0
                    record_event("Requested close for {} built circuits and sent NEWNYM".format(closed))
                finally:
                    control.close()
                self.send_json({"ok": True, "closed": closed})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=503)
            return
        if self.path == "/api/bridges":
            try:
                body = self.read_json()
                enabled = bool(body.get("enabled"))
                bridge_lines = [str(line).strip() for line in body.get("bridges", []) if str(line).strip()]
                control = TorControl()
                try:
                    if enabled:
                        if not bridge_lines:
                            raise ValueError("At least one bridge line is required")
                        if len(bridge_lines) > 20:
                            raise ValueError("Too many bridge lines")
                        bridge_args = " ".join("Bridge={}".format(control_quote(line)) for line in bridge_lines)
                        control.command("SETCONF UseBridges=1 {}".format(bridge_args))
                        record_event("Enabled {} bridge line(s)".format(len(bridge_lines)))
                    else:
                        control.command("RESETCONF UseBridges Bridge")
                        record_event("Bridges disabled")
                    control.command("SIGNAL NEWNYM")
                    EXIT_CACHE["updated"] = 0
                finally:
                    control.close()
                self.send_json({"ok": True})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=503)
            return
        if self.path == "/api/dns-leak":
            try:
                control = TorControl()
                try:
                    exit_info = current_exit(control)
                finally:
                    control.close()
                ok = bool(exit_info.get("ip") and exit_info.get("isTor"))
                detail = "SOCKS hostname request exits as {} {} via {}; local DNS is not used for this check.".format(
                    exit_info.get("ip", ""),
                    exit_info.get("country", ""),
                    exit_info.get("source") or exit_info.get("error", ""),
                )
                record_event("DNS leak check {}".format("passed" if ok else "failed"))
                self.send_json({"ok": ok, "detail": detail, "exit": exit_info})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=503)
            return
        self.send_error(404)


if __name__ == "__main__":
    server = ThreadingHTTPServer((DASHBOARD_HOST, DASHBOARD_PORT), Handler)
    print("Tor dashboard listening on {}:{}".format(DASHBOARD_HOST, DASHBOARD_PORT), flush=True)
    server.serve_forever()
