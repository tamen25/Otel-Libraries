import { useState } from "react";

const BACKEND = import.meta.env.VITE_BACKEND_URL || "http://localhost:8090";
const GRAFANA = import.meta.env.VITE_GRAFANA_URL || "http://localhost:3000";

const CHAIN = ["browser", "node", "python", "java", "dotnet"];
const COLORS = {
  browser: "#8b5cf6",
  node: "#22c55e",
  python: "#3b82f6",
  java: "#f97316",
  dotnet: "#a855f7",
};

function traceUrl(traceId) {
  return `${GRAFANA}/d/traces-logs-correlation/traces-logs-correlation?var-trace_id=${traceId}&from=now-30m&to=now`;
}

export default function App() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  async function sendOrder() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND}/api/order`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setResult(data);
      setHistory((h) => [{ traceId: data.traceId, at: new Date().toLocaleTimeString() }, ...h].slice(0, 8));
    } catch (e) {
      setError(String(e.message || e));
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        <header style={styles.header}>
          <h1 style={styles.h1}>CloudOps · Distributed Tracing</h1>
          <p style={styles.sub}>
            One request fans out across five hops. Each hop propagates W3C trace context automatically,
            so it becomes a single trace in Tempo — with correlated logs in Loki.
          </p>
        </header>

        <section style={styles.flow}>
          {CHAIN.map((svc, i) => (
            <div key={svc} style={styles.flowItem}>
              <div style={{ ...styles.node, borderColor: COLORS[svc], boxShadow: `0 0 0 1px ${COLORS[svc]}33` }}>
                <span style={{ ...styles.dot, background: COLORS[svc] }} />
                {svc}
              </div>
              {i < CHAIN.length - 1 && <span style={styles.arrow}>→</span>}
            </div>
          ))}
        </section>

        <button style={{ ...styles.button, opacity: loading ? 0.6 : 1 }} onClick={sendOrder} disabled={loading}>
          {loading ? "Sending…" : "▶  Send a traced order"}
        </button>

        {error && <div style={styles.error}>⚠ {error}</div>}

        {result && (
          <section style={styles.result}>
            <div style={styles.row}>
              <span style={styles.label}>Trace ID</span>
              <code style={styles.trace}>{result.traceId}</code>
            </div>
            <div style={styles.row}>
              <span style={styles.label}>Downstream</span>
              <span style={styles.badge}>HTTP {result.downstreamStatus}</span>
            </div>
            <a style={styles.primaryLink} href={traceUrl(result.traceId)} target="_blank" rel="noreferrer">
              🔍 Open this trace &amp; its logs in Grafana
            </a>
          </section>
        )}

        {history.length > 0 && (
          <section style={styles.history}>
            <div style={styles.historyHead}>Recent traces</div>
            {history.map((h, i) => (
              <a key={i} style={styles.historyRow} href={traceUrl(h.traceId)} target="_blank" rel="noreferrer">
                <code style={styles.historyTrace}>{h.traceId.slice(0, 24)}…</code>
                <span style={styles.historyTime}>{h.at}</span>
              </a>
            ))}
          </section>
        )}

        <footer style={styles.footer}>
          <a style={styles.footLink} href={`${GRAFANA}/d/service-graph/service-graph`} target="_blank" rel="noreferrer">
            Service graph (flow chart)
          </a>
          <a style={styles.footLink} href={`${GRAFANA}/d/traces-logs-correlation/traces-logs-correlation`} target="_blank" rel="noreferrer">
            Traces &amp; Logs dashboard
          </a>
        </footer>
      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: "100vh", background: "#0b0f1a", color: "#e5e7eb", fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif", display: "flex", justifyContent: "center", padding: "48px 16px" },
  container: { width: "100%", maxWidth: 720 },
  header: { marginBottom: 28 },
  h1: { fontSize: 30, fontWeight: 700, margin: "0 0 8px", letterSpacing: -0.5 },
  sub: { color: "#9ca3af", lineHeight: 1.5, margin: 0, fontSize: 15 },
  flow: { display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6, padding: "20px 0 24px" },
  flowItem: { display: "flex", alignItems: "center", gap: 6 },
  node: { display: "inline-flex", alignItems: "center", gap: 8, padding: "8px 14px", borderRadius: 10, border: "1px solid", background: "#111827", fontSize: 14, fontWeight: 600, textTransform: "capitalize" },
  dot: { width: 8, height: 8, borderRadius: "50%" },
  arrow: { color: "#4b5563", fontSize: 18 },
  button: { width: "100%", padding: "14px 20px", fontSize: 16, fontWeight: 600, color: "#0b0f1a", background: "#22c55e", border: "none", borderRadius: 12, cursor: "pointer" },
  error: { marginTop: 16, padding: "12px 16px", background: "#7f1d1d33", border: "1px solid #ef4444", borderRadius: 10, color: "#fca5a5" },
  result: { marginTop: 24, padding: 20, background: "#111827", border: "1px solid #1f2937", borderRadius: 14 },
  row: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid #1f2937" },
  label: { color: "#9ca3af", fontSize: 13, textTransform: "uppercase", letterSpacing: 0.5 },
  trace: { fontFamily: "ui-monospace, monospace", fontSize: 13, color: "#22c55e", wordBreak: "break-all", textAlign: "right" },
  badge: { padding: "3px 10px", background: "#14532d", color: "#86efac", borderRadius: 999, fontSize: 13, fontWeight: 600 },
  primaryLink: { display: "block", marginTop: 16, textAlign: "center", padding: "12px", background: "#1d4ed8", color: "#fff", borderRadius: 10, textDecoration: "none", fontWeight: 600 },
  history: { marginTop: 24 },
  historyHead: { color: "#9ca3af", fontSize: 13, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 },
  historyRow: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", background: "#0f1522", border: "1px solid #1f2937", borderRadius: 8, marginBottom: 6, textDecoration: "none", color: "#e5e7eb" },
  historyTrace: { fontFamily: "ui-monospace, monospace", fontSize: 12, color: "#60a5fa" },
  historyTime: { color: "#6b7280", fontSize: 12 },
  footer: { display: "flex", gap: 16, marginTop: 32, paddingTop: 20, borderTop: "1px solid #1f2937" },
  footLink: { color: "#9ca3af", fontSize: 14, textDecoration: "none", borderBottom: "1px dotted #4b5563", paddingBottom: 2 },
};
