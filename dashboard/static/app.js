(function () {
  const h = React.createElement;
  const countries = ["DE", "NL", "US", "GB", "FR", "SE", "CH", "CA", "TR", "PL", "CZ", "AT", "BG"];
  const profiles = [
    ["default", "Default"],
    ["stable", "Stable browsing"],
  ];
  const names = typeof Intl !== "undefined" && Intl.DisplayNames ? new Intl.DisplayNames(["en"], { type: "region" }) : null;

  function flag(cc) {
    if (!cc || cc.length !== 2 || cc === "??") return "??";
    return [...cc.toUpperCase()].map((c) => String.fromCodePoint(127397 + c.charCodeAt(0))).join("");
  }
  function country(cc) {
    if (!cc || cc === "??") return "Unknown";
    const upper = cc.toUpperCase();
    let name = upper;
    try { if (names) name = names.of(upper) || upper; } catch (_) {}
    return `${flag(upper)} ${name} (${upper})`;
  }
  async function postJson(url, body = {}) {
    const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok || payload.ok === false) throw new Error(payload.error || res.statusText);
    return payload;
  }
  function extractCountries(value) {
    return new Set((value || "").match(/[A-Za-z]{2}/g)?.map((cc) => cc.toUpperCase()) || []);
  }
  function Card({ label, value, detail, tone }) {
    return h("div", { className: "card" },
      h("div", { className: "label" }, label),
      h("div", { className: `value ${tone || ""}` }, value),
      detail ? h("div", { className: "small" }, detail) : null);
  }
  function Section({ title, meta, children }) {
    return h("section", { className: "card" },
      h("div", { className: "section-title" }, h("h2", null, title), meta ? h("div", { className: "small" }, meta) : null),
      children);
  }
  function Button({ children, secondary, disabled, onClick }) {
    return h("button", { type: "button", className: secondary ? "secondary" : "", disabled, onClick }, children);
  }
  function ChipGroup({ selected, onToggle }) {
    return h("div", { className: "chips" }, countries.map((cc) =>
      h("button", {
        key: cc,
        type: "button",
        className: `chip ${selected.has(cc) ? "active" : ""}`,
        onClick: () => onToggle(cc),
      }, `${flag(cc)} ${cc}`)));
  }
  function RelayHop({ relay, index }) {
    const labels = ["Guard", "Middle", "Exit"];
    return h("div", { className: "step active" },
      h("div", { className: "hop-title" }, labels[index] || `Hop ${index + 1}`),
      h("strong", null, relay?.nickname || "unknown"),
      h("div", { className: "small" }, relay?.ip ? `${country(relay.country)} ${relay.ip}` : country(relay?.country)),
      h("div", { className: "small" }, [relay?.flags, relay?.bandwidth ? `bw ${relay.bandwidth}` : ""].filter(Boolean).join(" | ")),
      h("div", { className: "small" }, relay?.fingerprint ? relay.fingerprint.slice(0, 20) : ""));
  }
  function CircuitVisualizer({ circuits, streams, closeCircuit }) {
    const activeIds = new Set((streams || []).map((s) => s.circuitId));
    const built = (circuits || []).filter((c) => c.status === "BUILT").slice(0, 8);
    if (!built.length) return h("div", { className: "small" }, "No built circuits yet.");
    return h("div", { className: "steps" }, built.map((c) =>
      h("div", { className: "step", key: c.id },
        h("div", { className: "section-title" },
          h("h2", null, `Circuit ${c.id}${activeIds.has(c.id) ? " | active" : ""}`),
          h("div", { className: "actions" }, h(Button, { secondary: true, onClick: () => closeCircuit(c.id) }, "Close"))),
        h("div", { className: "small" }, `${c.status} | ${c.purpose || "-"} | ${c.created || ""}`),
        h("div", { className: "circuit-line" }, (c.relays || []).map((relay, index) => h(RelayHop, { relay, index, key: relay.fingerprint || index }))),
      )));
  }
  function Health({ items }) {
    return h("div", { className: "health" }, (items || []).map((item) =>
      h("div", { className: "health-item", key: item.name },
        h("div", { className: "label" }, item.name),
        h("div", { className: item.ok ? "ok" : "bad" }, item.ok ? "OK" : "FAIL"),
        h("div", { className: "small" }, item.detail || ""))));
  }

  function App() {
    const [data, setData] = React.useState({ bootstrap: {}, circuits: [], streams: [], currentExit: {}, settings: {}, health: [], events: [], risks: [] });
    const [tab, setTab] = React.useState("overview");
    const [error, setError] = React.useState("");
    const [busy, setBusy] = React.useState("");
    const [preferred, setPreferred] = React.useState(new Set());
    const [excluded, setExcluded] = React.useState(new Set());
    const [strict, setStrict] = React.useState(true);
    const [policyDirty, setPolicyDirty] = React.useState(false);
    const [bridges, setBridges] = React.useState("");
    const [bridgeStep, setBridgeStep] = React.useState("mode");
    const [autoNewnym, setAutoNewnym] = React.useState(localStorage.getItem("autoNewnym") || "0");
    const [lastNewnym, setLastNewnym] = React.useState(Number(localStorage.getItem("lastNewnym") || "0"));
    const [tests, setTests] = React.useState([]);
    const [dnsLeak, setDnsLeak] = React.useState({ state: "Not run", detail: "Not run yet." });
    const [webrtcLeak, setWebrtcLeak] = React.useState({ state: "Not run", detail: "Not run yet." });
    const [logFilter, setLogFilter] = React.useState("all");

    const refresh = React.useCallback(async () => {
      try {
        const res = await fetch("/api/status", { cache: "no-store" });
        const payload = await res.json();
        payload.circuits ||= [];
        payload.streams ||= [];
        payload.settings ||= {};
        payload.currentExit ||= {};
        setData(payload);
        setError(payload.error || "");
        if (!policyDirty) {
          setPreferred(extractCountries(payload.settings.exitNodes));
          setExcluded(extractCountries(payload.settings.excludeExitNodes));
          setStrict((payload.settings.strictNodes || "0") === "1");
        }
        if (document.activeElement?.id !== "bridges") setBridges((payload.settings.bridges || []).join("\n"));
      } catch (err) {
        setError(String(err));
      }
    }, [policyDirty]);

    React.useEffect(() => {
      refresh();
      const timer = setInterval(refresh, 5000);
      return () => clearInterval(timer);
    }, [refresh]);
    React.useEffect(() => {
      localStorage.setItem("autoNewnym", autoNewnym);
      const seconds = Number(autoNewnym);
      if (!seconds) return undefined;
      const timer = setInterval(async () => {
        await postJson("/api/newnym");
        const now = Date.now();
        setLastNewnym(now);
        localStorage.setItem("lastNewnym", String(now));
        refresh();
      }, seconds * 1000);
      return () => clearInterval(timer);
    }, [autoNewnym, refresh]);

    async function action(name, fn) {
      setBusy(name);
      setError("");
      try { await fn(); } catch (err) { setError(String(err)); } finally { setBusy(""); }
    }
    function toggle(setter, source, cc) {
      const next = new Set(source);
      next.has(cc) ? next.delete(cc) : next.add(cc);
      setter(next);
      setPolicyDirty(true);
    }

    const bootstrap = data.bootstrap || {};
    const exit = data.currentExit || {};
    const built = data.circuits.filter((c) => c.status === "BUILT").length;
    const exitCountries = [...new Set(data.circuits.map((c) => c.relays?.[c.relays.length - 1]).filter(Boolean).map((r) => r.country).filter(Boolean))];
    const logs = (data.events || []).filter((event) => logFilter === "all" || event.category === logFilter || event.level === logFilter);
    const tabs = [["overview", "Overview"], ["policy", "Policy"], ["bridges", "Bridges"], ["tests", "Tests"], ["traffic", "Traffic"], ["events", "Events"]];

    return h("main", null,
      h("header", null,
        h("div", null, h("h1", null, "Tor Management Console"), h("div", { className: "small" }, `Updated ${new Date().toLocaleTimeString()}`)),
        h("div", { className: "toolbar" },
          h(Button, { secondary: true, onClick: refresh }, "Refresh"),
          h(Button, { disabled: busy === "newnym", onClick: () => action("newnym", async () => {
            await postJson("/api/newnym");
            const now = Date.now();
            setLastNewnym(now);
            localStorage.setItem("lastNewnym", String(now));
            await refresh();
          }) }, "New Identity"))),
      error ? h("div", { className: "notice" }, error) : null,
      h("div", { className: "tabs" }, tabs.map(([id, label]) => h("button", { key: id, type: "button", className: `tab ${tab === id ? "active" : ""}`, onClick: () => setTab(id) }, label))),

      tab === "overview" && h(React.Fragment, null,
        h("div", { className: "grid" },
          h(Card, { label: "Bootstrap", value: `${bootstrap.progress ?? 0}%`, detail: bootstrap.summary || bootstrap.tag || "", tone: (bootstrap.progress ?? 0) >= 100 ? "ok" : "warn" }),
          h(Card, { label: "Current Exit", value: exit.country ? flag(exit.country) : "-", detail: exit.ip ? `${country(exit.country)} ${exit.ip} ${exit.isTor ? "Tor" : ""}` : (exit.error || "No exit") }),
          h(Card, { label: "Circuits", value: String(built), detail: `${data.circuits.length} total` }),
          h(Card, { label: "Streams", value: String(data.streams.length), detail: "active mappings" }),
          h(Card, { label: "Exit Countries", value: exitCountries.length ? exitCountries.map(flag).join(" ") : "-", detail: data.settings.exitNodes || "any" })),
        h("section", { className: "split" },
          h(Section, { title: "Circuit Visualizer", meta: "Guard -> Middle -> Exit" },
            h(CircuitVisualizer, { circuits: data.circuits, streams: data.streams, closeCircuit: (id) => action(`close-${id}`, async () => { await postJson("/api/close-circuit", { id }); await refresh(); }) })),
          h("div", null,
            h(Section, { title: "Risk Cards", meta: `${(data.risks || []).length} checks` },
              h("div", { className: "steps" }, (data.risks || []).map((risk) => h("div", { className: "health-item", key: risk.name }, h("div", { className: "label" }, risk.name), h("div", { className: risk.level === "ok" ? "ok" : risk.level === "warn" ? "warn" : "small" }, risk.level.toUpperCase()), h("div", { className: "small" }, risk.detail))))),
            h(Section, { title: "Health", meta: `${(data.health || []).length} checks` }, h(Health, { items: data.health })))),
      ),

      tab === "policy" && h(React.Fragment, null,
        h("section", { className: "two" },
          h(Section, { title: "Preferred Exit Countries", meta: preferred.size ? [...preferred].join(", ") : "any" }, h(ChipGroup, { selected: preferred, onToggle: (cc) => toggle(setPreferred, preferred, cc) })),
          h(Section, { title: "Excluded Exit Countries", meta: excluded.size ? [...excluded].join(", ") : "none" }, h(ChipGroup, { selected: excluded, onToggle: (cc) => toggle(setExcluded, excluded, cc) }))),
        h(Section, { title: "Pending Policy", meta: policyDirty ? "Unsaved changes" : "Synced" },
          h("div", { className: "field" }, h("label", { className: "label" }, "Strict mode"), h("select", { value: strict ? "1" : "0", onChange: (e) => { setStrict(e.target.value === "1"); setPolicyDirty(true); } }, h("option", { value: "1" }, "StrictNodes on"), h("option", { value: "0" }, "Soft preference"))),
          h("div", { className: "small" }, `Will set ExitNodes=${[...preferred].join(",") || "-"} ExcludeExitNodes=${[...excluded].join(",") || "-"} StrictNodes=${strict ? "1" : "0"}`),
          h("div", { className: "actions" },
            h(Button, { onClick: () => action("policy", async () => { await postJson("/api/exit-policy", { countries: [...preferred], excluded: [...excluded], strict }); setPolicyDirty(false); await postJson("/api/newnym"); await refresh(); }) }, "Apply and Rotate"),
            h(Button, { secondary: true, onClick: () => action("clearPolicy", async () => { setPreferred(new Set()); setExcluded(new Set()); await postJson("/api/exit-policy", { countries: [], excluded: [], strict: false }); setPolicyDirty(false); await refresh(); }) }, "Clear Policy"))),
        h(Section, { title: "Profiles", meta: "runtime presets" },
          h("div", { className: "actions" }, profiles.map(([id, label]) => h(Button, { key: id, secondary: true, onClick: () => action(`profile-${id}`, async () => { await postJson("/api/profile", { profile: id }); await refresh(); }) }, label))),
          h("div", { className: "small" }, "Profiles are runtime changes. Permanent defaults still belong in torrc."))),

      tab === "bridges" && h(React.Fragment, null,
        h("div", { className: "steps" },
          ["mode", "paste", "apply"].map((step) => h("button", { key: step, type: "button", className: `chip ${bridgeStep === step ? "active" : ""}`, onClick: () => setBridgeStep(step) }, step))),
        h(Section, { title: "Bridge Wizard", meta: data.settings.useBridges === "1" ? "enabled" : "disabled" },
          bridgeStep === "mode" && h("div", { className: "small" }, "Use bridges when your network blocks direct Tor connections. Snowflake is already installed as a client transport; paste obfs4 bridge lines when you have them."),
          bridgeStep === "paste" && h("div", { className: "field" }, h("label", { className: "label", htmlFor: "bridges" }, "Bridge lines"), h("textarea", { id: "bridges", spellCheck: false, value: bridges, onChange: (e) => setBridges(e.target.value), placeholder: "obfs4 1.2.3.4:443 FINGERPRINT cert=... iat-mode=0" })),
          bridgeStep === "apply" && h("div", null, h("div", { className: "small" }, `${bridges.split(/\n+/).filter(Boolean).length} bridge line(s) ready`), h("div", { className: "actions" }, h(Button, { onClick: () => action("enableBridges", async () => { await postJson("/api/bridges", { enabled: true, bridges: bridges.split(/\n+/).map((line) => line.trim()).filter(Boolean) }); await refresh(); }) }, "Enable Bridges"), h(Button, { secondary: true, onClick: () => action("disableBridges", async () => { await postJson("/api/bridges", { enabled: false, bridges: [] }); await refresh(); }) }, "Disable Bridges"))))),

      tab === "tests" && h(React.Fragment, null,
        h("section", { className: "two" },
          h(Section, { title: "Proxy Test Center", meta: tests.length ? `${tests.length} checks` : "not run" },
            h("div", { className: "actions" }, h(Button, { onClick: () => action("proxyTests", async () => { const result = await fetch("/api/proxy-tests", { cache: "no-store" }).then((r) => r.json()); setTests(result.tests || []); }) }, "Run Proxy Tests")),
            h("div", { className: "steps" }, tests.map((test) => h("div", { className: "health-item", key: test.name }, h("div", { className: "label" }, test.name), h("div", { className: test.ok ? "ok" : "bad" }, `${test.ok ? "OK" : "FAIL"} ${test.ms}ms`), h("div", { className: "small" }, test.detail))))),
          h(Section, { title: "Identity Automation", meta: lastNewnym ? `last ${new Date(lastNewnym).toLocaleTimeString()}` : "manual" },
            h("div", { className: "field" }, h("label", { className: "label" }, "Auto New Identity"), h("select", { value: autoNewnym, onChange: (e) => setAutoNewnym(e.target.value) }, h("option", { value: "0" }, "Off"), h("option", { value: "300" }, "Every 5 minutes"), h("option", { value: "600" }, "Every 10 minutes"), h("option", { value: "1800" }, "Every 30 minutes"))),
            h("div", { className: "actions" }, h(Button, { secondary: true, onClick: () => action("dirty", async () => { await postJson("/api/close-dirty-circuits"); await refresh(); }) }, "Close Dirty Circuits")))),
        h("section", { className: "two" },
          h(Section, { title: "DNS Leak Check", meta: dnsLeak.state }, h("div", { className: "small" }, dnsLeak.detail), h("div", { className: "actions" }, h(Button, { onClick: () => action("dns", async () => { setDnsLeak({ state: "Running", detail: "Checking..." }); const result = await postJson("/api/dns-leak"); setDnsLeak({ state: result.ok ? "OK" : "Check failed", detail: result.detail || JSON.stringify(result) }); }) }, "Run Check"))),
          h(Section, { title: "WebRTC Leak Check", meta: webrtcLeak.state }, h("div", { className: "small" }, webrtcLeak.detail), h("div", { className: "actions" }, h(Button, { onClick: async () => { setWebrtcLeak({ state: "Running", detail: "Checking browser candidates..." }); if (!window.RTCPeerConnection) { setWebrtcLeak({ state: "Disabled", detail: "RTCPeerConnection is unavailable." }); return; } const ips = new Set(); const pc = new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }] }); pc.createDataChannel("leak-test"); pc.onicecandidate = (e) => (e.candidate?.candidate.match(/([0-9]{1,3}(?:\.[0-9]{1,3}){3})/g) || []).forEach((ip) => ips.add(ip)); await pc.setLocalDescription(await pc.createOffer()); setTimeout(() => { pc.close(); setWebrtcLeak({ state: ips.size ? "Candidates found" : "No candidates", detail: ips.size ? [...ips].join(", ") : "No WebRTC IP candidates were exposed." }); }, 3000); } }, "Run Local Check"))))),

      tab === "traffic" && h(React.Fragment, null,
        h(Section, { title: "Circuit Visualizer", meta: `${data.circuits.length} circuits` }, h(CircuitVisualizer, { circuits: data.circuits, streams: data.streams, closeCircuit: (id) => action(`close-${id}`, async () => { await postJson("/api/close-circuit", { id }); await refresh(); }) })),
        h(Section, { title: "Active Streams", meta: `${data.streams.length} active` }, h("table", null, h("thead", null, h("tr", null, h("th", null, "ID"), h("th", null, "Status"), h("th", null, "Target"), h("th", null, "Exit"))), h("tbody", null, data.streams.length ? data.streams.map((s) => h("tr", { key: s.id }, h("td", null, `${s.id} / circuit ${s.circuitId || "-"}`), h("td", { className: s.status === "SUCCEEDED" ? "ok" : "warn" }, s.status), h("td", null, s.target || "-"), h("td", null, s.exitRelay?.ip ? `${country(s.exitRelay.country)} ${s.exitRelay.ip}` : "-"))) : h("tr", null, h("td", { colSpan: 4 }, "No active streams yet.")))))),

      tab === "events" && h(React.Fragment, null,
        h(Section, { title: "Event Center", meta: `${logs.length} visible` },
          h("div", { className: "actions" }, ["all", "warn", "bootstrap", "bridge", "circuit", "control", "dashboard"].map((filter) => h(Button, { key: filter, secondary: logFilter !== filter, onClick: () => setLogFilter(filter) }, filter))),
          h("div", { className: "log" }, logs.map((event) => `[${event.level || "info"}] ${event.category || "general"} ${event.message}`).join("\n") || "No events yet."))),
    );
  }
  ReactDOM.createRoot(document.getElementById("root")).render(h(App));
})();
