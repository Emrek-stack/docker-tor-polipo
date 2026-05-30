(function () {
  const h = React.createElement;
  const commonCountries = ["DE", "NL", "US", "GB", "FR", "SE", "CH", "CA", "TR"];
  const regionNames = typeof Intl !== "undefined" && Intl.DisplayNames
    ? new Intl.DisplayNames(["en"], { type: "region" })
    : null;

  function flag(cc) {
    if (!cc || cc.length !== 2 || cc === "??") return "??";
    return [...cc.toUpperCase()].map((c) => String.fromCodePoint(127397 + c.charCodeAt(0))).join("");
  }

  function countryLabel(cc) {
    if (!cc || cc === "??") return "Unknown";
    const upper = cc.toUpperCase();
    let name = upper;
    try {
      if (regionNames) name = regionNames.of(upper) || upper;
    } catch (_) {}
    return `${flag(upper)} ${name} (${upper})`;
  }

  async function postJson(url, body = {}) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) throw new Error(payload.error || response.statusText);
    return payload;
  }

  function Card({ label, value, detail, className }) {
    return h("div", { className: "card" },
      h("div", { className: "label" }, label),
      h("div", { className: `value ${className || ""}` }, value),
      detail ? h("div", { className: "small" }, detail) : null,
    );
  }

  function Section({ title, meta, children }) {
    return h("section", { className: "card" },
      h("div", { className: "section-title" },
        h("h2", null, title),
        meta ? h("div", { className: "small" }, meta) : null,
      ),
      children,
    );
  }

  function Health({ items }) {
    return h("div", { className: "health" }, (items || []).map((item) =>
      h("div", { className: "health-item", key: item.name },
        h("div", { className: "label" }, item.name),
        h("div", { className: item.ok ? "ok" : "bad" }, item.ok ? "OK" : "FAIL"),
        h("div", { className: "small" }, item.detail || ""),
      ),
    ));
  }

  function Relay({ relay }) {
    return h("div", { className: "relay" },
      h("strong", null, relay.nickname || "unknown"),
      h("span", null, `${countryLabel(relay.country)} ${relay.ip || ""}`),
      h("span", null, [relay.flags, relay.bandwidth ? `bw ${relay.bandwidth}` : ""].filter(Boolean).join(" | ")),
      h("span", null, relay.fingerprint ? relay.fingerprint.slice(0, 16) : ""),
    );
  }

  function App() {
    const [data, setData] = React.useState({ bootstrap: {}, circuits: [], streams: [], currentExit: {}, health: [], settings: {}, events: [] });
    const [error, setError] = React.useState("");
    const [activeTab, setActiveTab] = React.useState("overview");
    const [selectedCountries, setSelectedCountries] = React.useState(new Set());
    const [countriesDirty, setCountriesDirty] = React.useState(false);
    const [bridges, setBridges] = React.useState("");
    const [bridgesFocused, setBridgesFocused] = React.useState(false);
    const [autoNewnym, setAutoNewnym] = React.useState(localStorage.getItem("autoNewnym") || "0");
    const [lastNewnym, setLastNewnym] = React.useState(Number(localStorage.getItem("lastNewnym") || "0"));
    const [dnsLeak, setDnsLeak] = React.useState({ state: "Not run", detail: "Not run yet." });
    const [webrtcLeak, setWebrtcLeak] = React.useState({ state: "Not run", detail: "Not run yet." });
    const [busy, setBusy] = React.useState("");

    const refresh = React.useCallback(async () => {
      try {
        const response = await fetch("/api/status", { cache: "no-store" });
        const payload = await response.json();
        payload.circuits = payload.circuits || [];
        payload.streams = payload.streams || [];
        payload.currentExit = payload.currentExit || {};
        payload.settings = payload.settings || {};
        setData(payload);
        setError(payload.error || "");
        if (!countriesDirty) {
          const next = new Set();
          for (const cc of (payload.settings.exitNodes || "").match(/[A-Za-z]{2}/g) || []) next.add(cc.toUpperCase());
          setSelectedCountries(next);
        }
        if (!bridgesFocused) setBridges((payload.settings.bridges || []).join("\n"));
      } catch (err) {
        setError(String(err));
      }
    }, [bridgesFocused, countriesDirty]);

    React.useEffect(() => {
      refresh();
      const timer = setInterval(refresh, 5000);
      return () => clearInterval(timer);
    }, [refresh]);

    React.useEffect(() => {
      localStorage.setItem("autoNewnym", autoNewnym);
      const seconds = Number(autoNewnym || "0");
      if (!seconds) return undefined;
      const timer = setInterval(async () => {
        await postJson("/api/newnym");
        const now = Date.now();
        setLastNewnym(now);
        localStorage.setItem("lastNewnym", String(now));
        await refresh();
      }, seconds * 1000);
      return () => clearInterval(timer);
    }, [autoNewnym, refresh]);

    async function action(name, fn) {
      setBusy(name);
      setError("");
      try {
        await fn();
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy("");
      }
    }

    const bootstrap = data.bootstrap || {};
    const exit = data.currentExit || {};
    const builtCircuits = data.circuits.filter((c) => c.status === "BUILT").length;
    const exitCountries = [...new Set(data.circuits.map((c) => c.relays[c.relays.length - 1]).filter(Boolean).map((r) => r.country).filter(Boolean))];
    const tabs = [
      ["overview", "Overview"],
      ["controls", "Controls"],
      ["traffic", "Traffic"],
      ["logs", "Logs"],
    ];

    return h("main", null,
      h("header", null,
        h("div", null,
          h("h1", null, "Tor Dashboard"),
          h("div", { className: "small" }, `Updated ${new Date().toLocaleTimeString()}`),
        ),
        h("div", { className: "toolbar" },
          h("button", { className: "secondary", type: "button", onClick: refresh }, "Refresh"),
          h("button", {
            type: "button",
            disabled: busy === "newnym",
            onClick: () => action("newnym", async () => {
              await postJson("/api/newnym");
              const now = Date.now();
              setLastNewnym(now);
              localStorage.setItem("lastNewnym", String(now));
              await refresh();
            }),
          }, "New Identity"),
        ),
      ),
      error ? h("div", { className: "notice" }, error) : null,
      h("div", { className: "tabs" }, tabs.map(([id, label]) =>
        h("button", { key: id, className: `tab ${activeTab === id ? "active" : ""}`, type: "button", onClick: () => setActiveTab(id) }, label),
      )),
      activeTab === "overview" ? h(React.Fragment, null,
        h("div", { className: "grid" },
          h(Card, { label: "Bootstrap", value: `${bootstrap.progress ?? 0}%`, detail: bootstrap.summary || bootstrap.tag || "", className: (bootstrap.progress ?? 0) >= 100 ? "ok" : "warn" }),
          h(Card, { label: "Tor Version", value: data.version || "-" }),
          h(Card, { label: "Built Circuits", value: String(builtCircuits) }),
          h(Card, { label: "Exit Countries", value: exitCountries.length ? exitCountries.map(flag).join(" ") : "-" }),
          h(Card, {
            label: "Current Exit",
            value: exit.country ? flag(exit.country) : "-",
            detail: exit.ip ? `${countryLabel(exit.country)} ${exit.ip}${exit.isTor ? " Tor" : ""} ${[exit.city, exit.region, exit.isp, exit.source].filter(Boolean).join(" | ")}` : (exit.error || "No exit check yet"),
          }),
        ),
        h(Section, { title: "Health Checks", meta: `${(data.health || []).length} checks` }, h(Health, { items: data.health })),
        h("section", { className: "two" },
          h(Section, { title: "DNS Leak Check", meta: dnsLeak.state },
            h("div", { className: "small" }, dnsLeak.detail),
            h("div", { className: "actions" }, h("button", { type: "button", onClick: () => action("dns", async () => {
              setDnsLeak({ state: "Running", detail: "Checking..." });
              const result = await postJson("/api/dns-leak");
              setDnsLeak({ state: result.ok ? "OK" : "Check failed", detail: result.detail || JSON.stringify(result) });
            }) }, "Run Check")),
          ),
          h(Section, { title: "WebRTC Leak Check", meta: webrtcLeak.state },
            h("div", { className: "small" }, webrtcLeak.detail),
            h("div", { className: "actions" }, h("button", { type: "button", onClick: async () => {
              setWebrtcLeak({ state: "Running", detail: "Checking browser candidates..." });
              if (!window.RTCPeerConnection) {
                setWebrtcLeak({ state: "Disabled", detail: "RTCPeerConnection is unavailable, which is the preferred state for Tor browsing." });
                return;
              }
              const candidates = new Set();
              const pc = new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }] });
              pc.createDataChannel("leak-test");
              pc.onicecandidate = (event) => {
                if (!event.candidate) return;
                const matches = event.candidate.candidate.match(/([0-9]{1,3}(?:\.[0-9]{1,3}){3})/g) || [];
                matches.forEach((ip) => candidates.add(ip));
              };
              await pc.setLocalDescription(await pc.createOffer());
              setTimeout(() => {
                pc.close();
                const ips = [...candidates];
                setWebrtcLeak({ state: ips.length ? "Candidates found" : "No candidates", detail: ips.length ? ips.join(", ") : "No WebRTC IP candidates were exposed." });
              }, 3000);
            } }, "Run Local Check")),
          ),
        ),
      ) : null,
      activeTab === "controls" ? h(React.Fragment, null,
        h("section", { className: "two" },
          h(Section, { title: "Exit Country", meta: data.settings.exitNodes ? `ExitNodes ${data.settings.exitNodes}` : "Any exit country" },
            h("div", { className: "chips" }, commonCountries.map((cc) =>
              h("button", {
                key: cc,
                className: `chip ${selectedCountries.has(cc) ? "active" : ""}`,
                type: "button",
                onClick: () => {
                  const next = new Set(selectedCountries);
                  next.has(cc) ? next.delete(cc) : next.add(cc);
                  setCountriesDirty(true);
                  setSelectedCountries(next);
                },
              }, `${flag(cc)} ${cc}`),
            )),
            h("div", { className: "actions" },
              h("button", { type: "button", onClick: () => action("applyCountries", async () => {
                await postJson("/api/exit-policy", { countries: [...selectedCountries], strict: true });
                setCountriesDirty(false);
                await postJson("/api/newnym");
                await refresh();
              }) }, "Apply"),
              h("button", { className: "secondary", type: "button", onClick: () => action("clearCountries", async () => {
                setSelectedCountries(new Set());
                await postJson("/api/exit-policy", { countries: [], strict: false });
                setCountriesDirty(false);
                await postJson("/api/newnym");
                await refresh();
              }) }, "Clear"),
            ),
          ),
          h(Section, { title: "Identity", meta: lastNewnym ? `Last changed ${new Date(lastNewnym).toLocaleTimeString()}` : "Manual" },
            h("div", { className: "field" },
              h("label", { className: "label", htmlFor: "auto-newnym" }, "Auto New Identity"),
              h("select", { id: "auto-newnym", value: autoNewnym, onChange: (event) => setAutoNewnym(event.target.value) },
                h("option", { value: "0" }, "Off"),
                h("option", { value: "300" }, "Every 5 minutes"),
                h("option", { value: "600" }, "Every 10 minutes"),
                h("option", { value: "1800" }, "Every 30 minutes"),
              ),
            ),
            h("div", { className: "actions" },
              h("button", { type: "button", onClick: () => action("dirty", async () => { await postJson("/api/close-dirty-circuits"); await refresh(); }) }, "Close Dirty Circuits"),
            ),
          ),
        ),
        h(Section, { title: "Bridges", meta: data.settings.useBridges === "1" ? "Enabled" : "Disabled" },
          h("div", { className: "field" },
            h("label", { className: "label", htmlFor: "bridges" }, "Bridge lines"),
            h("textarea", {
              id: "bridges",
              spellCheck: false,
              value: bridges,
              onFocus: () => setBridgesFocused(true),
              onBlur: () => setBridgesFocused(false),
              onChange: (event) => setBridges(event.target.value),
              placeholder: "obfs4 1.2.3.4:443 FINGERPRINT cert=... iat-mode=0",
            }),
          ),
          h("div", { className: "actions" },
            h("button", { type: "button", onClick: () => action("enableBridges", async () => {
              await postJson("/api/bridges", { enabled: true, bridges: bridges.split(/\n+/).map((line) => line.trim()).filter(Boolean) });
              await refresh();
            }) }, "Enable Bridges"),
            h("button", { className: "secondary", type: "button", onClick: () => action("disableBridges", async () => { await postJson("/api/bridges", { enabled: false, bridges: [] }); await refresh(); }) }, "Disable Bridges"),
          ),
        ),
      ) : null,
      activeTab === "traffic" ? h(React.Fragment, null,
        h(Section, { title: "Active Connections", meta: `${data.streams.length} active` },
          h("table", null,
            h("thead", null, h("tr", null, h("th", null, "ID"), h("th", null, "Status"), h("th", null, "Target"), h("th", null, "Exit"))),
            h("tbody", null, data.streams.length ? data.streams.map((s) => {
              const exitRelay = s.exitRelay || {};
              return h("tr", { key: s.id },
                h("td", null, `${s.id} / circuit ${s.circuitId || "-"}`),
                h("td", { className: s.status === "SUCCEEDED" ? "ok" : "warn" }, s.status),
                h("td", null, s.target || "-"),
                h("td", null, exitRelay.ip ? `${countryLabel(exitRelay.country)} ${exitRelay.ip}` : "-"),
              );
            }) : h("tr", null, h("td", { colSpan: 4 }, "No active streams yet."))),
          ),
        ),
        h(Section, { title: "Circuits", meta: `${data.circuits.length} total` },
          h("table", null,
            h("thead", null, h("tr", null, h("th", null, "ID"), h("th", null, "Status"), h("th", null, "Purpose"), h("th", null, "Route"))),
            h("tbody", null, data.circuits.length ? data.circuits.map((c) =>
              h("tr", { key: c.id },
                h("td", null, c.id),
                h("td", { className: c.status === "BUILT" ? "ok" : "warn" }, c.status),
                h("td", null,
                  c.purpose || "-",
                  h("div", { className: "small" }, c.flags || ""),
                  h("button", { className: "secondary", type: "button", onClick: () => action(`close-${c.id}`, async () => { await postJson("/api/close-circuit", { id: c.id }); await refresh(); }) }, "Close"),
                ),
                h("td", null, h("div", { className: "path" }, (c.relays || []).map((relay) => h(Relay, { relay, key: relay.fingerprint || relay.nickname })))),
              ),
            ) : h("tr", null, h("td", { colSpan: 4 }, "No circuits yet."))),
          ),
        ),
      ) : null,
      activeTab === "logs" ? h(Section, { title: "Logs", meta: `${(data.events || []).length} events` },
        h("div", { className: "log" }, (data.events || []).map((event) => `${event.time || ""} ${event.message}`).join("\n") || "No dashboard events yet."),
      ) : null,
    );
  }

  ReactDOM.createRoot(document.getElementById("root")).render(h(App));
})();
