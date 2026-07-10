// Node.js edge service: the entry point of the demo trace chain.
// Requiring the traces package FIRST registers HTTP auto-instrumentation, so the
// inbound request and the outbound call to python are traced and W3C context
// propagates automatically — no manual span code.
require("@cloudops/otel-traces");
const { logger } = require("@cloudops/otel-logs");
const { trace } = require("@opentelemetry/api");
const http = require("http");

const PYTHON_URL = process.env.PYTHON_URL || "http://python-app:8000/order";
const PORT = 8090;

// Calls the downstream python service over the instrumented http module.
function callPython() {
  return new Promise((resolve, reject) => {
    const req = http.get(PYTHON_URL, (res) => {
      let body = "";
      res.on("data", (chunk) => (body += chunk));
      res.on("end", () => resolve({ status: res.statusCode, body }));
    });
    req.on("error", reject);
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    return res.end();
  }

  if (req.url.startsWith("/health")) {
    res.writeHead(200);
    return res.end("ok");
  }

  if (req.url.startsWith("/api/order")) {
    logger.info("order requested at edge", { hop: "node" });
    try {
      const downstream = await callPython();
      const traceId = trace.getActiveSpan()?.spanContext().traceId || "unknown";
      logger.info("edge order complete", { hop: "node", trace_id: traceId, downstream_status: downstream.status });
      await logger.exportLogs();
      res.writeHead(200, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({
        traceId,
        chain: ["node", "python", "java", "dotnet"],
        downstreamStatus: downstream.status,
      }));
    } catch (error) {
      const traceId = trace.getActiveSpan()?.spanContext().traceId || "unknown";
      logger.error("edge order failed", { hop: "node", trace_id: traceId, error: String(error) });
      await logger.exportLogs();
      res.writeHead(502, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ traceId, error: String(error) }));
    }
  }

  res.writeHead(404);
  res.end("not found");
});

server.listen(PORT, () => logger.info("node-edge started", { port: PORT }));
