#!/usr/bin/env python3
import json
import os
import re
import socket
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


CONTROL_HOST = os.environ.get("TOR_CONTROL_HOST", "127.0.0.1")
CONTROL_PORT = int(os.environ.get("TOR_CONTROL_PORT", "19051"))
CONTROL_PASSWORD = os.environ.get("TOR_CONTROL_PASSWORD", "vidalia")
DASHBOARD_HOST = os.environ.get("TOR_DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.environ.get("TOR_DASHBOARD_PORT", "8080"))
TOR_SOCKS_HOST = os.environ.get("TOR_SOCKS_HOST", "127.0.0.1")
TOR_SOCKS_PORT = int(os.environ.get("TOR_SOCKS_PORT", "19050"))
EXIT_CACHE = {"updated": 0, "data": {}}


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
@media (max-width: 900px) {
  main { padding: 16px; }
  header { align-items: flex-start; flex-direction: column; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
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
    <div class="card"><div class="label">Current Exit</div><div class="value" id="exitCountry">-</div><div class="small" id="exitIp"></div></div>
  </div>
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
</main>
<script>
const $ = (id) => document.getElementById(id);
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
  $("count").textContent = `${data.circuits.length} total`;
  $("streamCount").textContent = `${data.streams.length} active`;
  $("updated").textContent = `Updated ${new Date().toLocaleTimeString()}`;

  $("streams").innerHTML = data.streams.map(s => {
    const exitRelay = s.exitRelay || {};
    const exitText = exitRelay.ip ? `${countryLabel(exitRelay.country)} ${exitRelay.ip}` : "-";
    return `
      <tr>
        <td>${esc(s.id)}</td>
        <td class="${s.status === "SUCCEEDED" ? "ok" : "warn"}">${esc(s.status)}</td>
        <td>${esc(s.target || "-")}</td>
        <td>${esc(exitText)}</td>
      </tr>`;
  }).join("") || `<tr><td colspan="4">No active streams yet.</td></tr>`;

  $("circuits").innerHTML = data.circuits.map(c => `
    <tr>
      <td>${esc(c.id)}</td>
      <td class="${c.status === "BUILT" ? "ok" : "warn"}">${esc(c.status)}</td>
      <td>${esc(c.purpose || "-")}</td>
      <td><div class="path">${c.relays.map(r => `
        <div class="relay">
          <strong>${esc(r.nickname || "unknown")}</strong>
          <span>${esc(countryLabel(r.country))} ${esc(r.ip || "")}</span>
          <span>${esc(r.fingerprint ? r.fingerprint.slice(0, 12) : "")}</span>
        </div>`).join("")}</div></td>
    </tr>`).join("") || `<tr><td colspan="4">No circuits yet.</td></tr>`;
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
    await fetch("/api/newnym", { method: "POST" });
    await refresh();
  } finally {
    setTimeout(() => { $("newnym").disabled = false; }, 4000);
  }
});

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
                items[key] = value
            elif rest and rest != "OK":
                lines.append(rest)
            if sep == " ":
                return {"items": items, "lines": lines}


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
        fields = first.split()
        if len(fields) >= 7:
            relay["nickname"] = relay["nickname"] or fields[1]
            relay["ip"] = fields[6]
            relay["country"] = control.command("GETINFO ip-to-country/{}".format(relay["ip"]))["items"].get("ip-to-country/{}".format(relay["ip"]), "??").upper()
    except Exception:
        pass
    cache[fingerprint] = relay
    return relay


def current_exit(control):
    now = time.time()
    if EXIT_CACHE["data"] and now - EXIT_CACHE["updated"] < 20:
        return EXIT_CACHE["data"]
    result = {"ip": "", "country": "??", "isTor": False, "error": ""}
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
            result["country"] = control.command("GETINFO ip-to-country/{}".format(result["ip"]))["items"].get("ip-to-country/{}".format(result["ip"]), "??").upper()
    except Exception as exc:
        result["error"] = str(exc)
    EXIT_CACHE["updated"] = now
    EXIT_CACHE["data"] = result
    return result


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
        return {
            "version": info.get("version", ""),
            "bootstrap": parse_bootstrap(info.get("status/bootstrap-phase", "")),
            "circuits": circuits,
            "streams": streams,
            "currentExit": exit_info,
            "error": exit_info.get("error", ""),
        }
    finally:
        control.close()


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
        self.send_error(404)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self.send_index()
            return
        if self.path == "/api/status":
            try:
                self.send_json(tor_status())
            except Exception as exc:
                self.send_json({"version": "", "bootstrap": {}, "circuits": [], "streams": [], "currentExit": {}, "error": str(exc)}, status=503)
            return
        self.send_error(404)

    def do_POST(self):
        if self.path == "/api/newnym":
            try:
                control = TorControl()
                try:
                    control.command("SIGNAL NEWNYM")
                finally:
                    control.close()
                self.send_json({"ok": True})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=503)
            return
        self.send_error(404)


if __name__ == "__main__":
    server = ThreadingHTTPServer((DASHBOARD_HOST, DASHBOARD_PORT), Handler)
    print("Tor dashboard listening on {}:{}".format(DASHBOARD_HOST, DASHBOARD_PORT), flush=True)
    server.serve_forever()
