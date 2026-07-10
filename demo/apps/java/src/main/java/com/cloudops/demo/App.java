// Java middle service: logs then calls the .NET service.
package com.cloudops.demo;

import com.cloudops.otel.logs.CloudOpsLogger;
import com.cloudops.otel.traces.CloudOpsTracer;
import com.sun.net.httpserver.HttpServer;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.context.Scope;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.HashMap;
import java.util.Map;

public final class App {
  private static final CloudOpsLogger LOG = CloudOpsLogger.initializeLogger();
  private static final CloudOpsTracer TRACER = CloudOpsTracer.initializeTracer();
  private static final String DOTNET_URL =
      System.getenv().getOrDefault("DOTNET_URL", "http://dotnet-app:8081/finalize");
  private static final HttpClient CLIENT = HttpClient.newHttpClient();
  private static final java.util.concurrent.atomic.AtomicLong COUNT =
      new java.util.concurrent.atomic.AtomicLong();

  public static void main(String[] args) throws IOException {
    HttpServer server = HttpServer.create(new InetSocketAddress(8080), 0);
    server.createContext("/health", ex -> respond(ex, 200, "ok"));
    server.createContext("/process", App::process);
    server.setExecutor(null);
    server.start();
    LOG.info("java-app started", "port", 8080);
  }

  private static void process(com.sun.net.httpserver.HttpExchange ex) throws IOException {
    // Continue the caller's trace from the incoming request headers (W3C tracecontext).
    Map<String, String> incoming = new HashMap<>();
    ex.getRequestHeaders().forEach((key, values) -> {
      if (values != null && !values.isEmpty()) {
        incoming.put(key.toLowerCase(), values.get(0));
      }
    });
    Span span = TRACER.startServerSpan("process", incoming);

    try (Scope scope = span.makeCurrent()) {
      String query = ex.getRequestURI().getQuery();
      String orderId = query != null && query.startsWith("order_id=") ? query.substring(9) : "unknown";
      LOG.debug("validating order", "order_id", orderId, "hop", "java");
      LOG.info("processing order", "order_id", orderId, "hop", "java");
      if (COUNT.incrementAndGet() % 5 == 0) {
        LOG.warn("downstream latency high (simulated)", "order_id", orderId, "count", COUNT.get());
      }
      // Wrap the outbound call in a CLIENT span so java-app -> dotnet-app forms a
      // service-graph edge, and inject the context within it for propagation.
      Span clientSpan = TRACER.startClientSpan("GET /finalize");
      try (Scope clientScope = clientSpan.makeCurrent()) {
        HttpRequest.Builder builder = HttpRequest.newBuilder()
            .uri(URI.create(DOTNET_URL + "?order_id=" + orderId)).GET();
        TRACER.injectHeaders().forEach(builder::header);
        HttpResponse<String> resp = CLIENT.send(builder.build(), HttpResponse.BodyHandlers.ofString());
        LOG.info("dotnet responded", "order_id", orderId, "status", resp.statusCode());
        respond(ex, 200, "processed");
      } catch (Exception e) {
        clientSpan.recordException(e);
        span.recordException(e);
        LOG.error("dotnet call failed", "order_id", orderId, "error", e.getMessage());
        respond(ex, 502, "downstream error");
      } finally {
        clientSpan.end();
        LOG.exportLogs();
      }
    } finally {
      span.end();
      TRACER.exportSpans();
    }
  }

  private static void respond(com.sun.net.httpserver.HttpExchange ex, int code, String body)
      throws IOException {
    byte[] bytes = body.getBytes();
    ex.sendResponseHeaders(code, bytes.length);
    try (OutputStream os = ex.getResponseBody()) {
      os.write(bytes);
    }
  }
}
