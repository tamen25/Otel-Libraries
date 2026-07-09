// Java middle service: logs then calls the .NET service.
package com.cloudops.demo;

import com.cloudops.otel.logs.CloudOpsLogger;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public final class App {
  private static final CloudOpsLogger LOG = CloudOpsLogger.initializeLogger();
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
    String query = ex.getRequestURI().getQuery();
    String orderId = query != null && query.startsWith("order_id=") ? query.substring(9) : "unknown";
    LOG.debug("validating order", "order_id", orderId, "hop", "java");
    LOG.info("processing order", "order_id", orderId, "hop", "java");
    if (COUNT.incrementAndGet() % 5 == 0) {
      LOG.warn("downstream latency high (simulated)", "order_id", orderId, "count", COUNT.get());
    }
    try {
      HttpRequest req = HttpRequest.newBuilder()
          .uri(URI.create(DOTNET_URL + "?order_id=" + orderId)).GET().build();
      HttpResponse<String> resp = CLIENT.send(req, HttpResponse.BodyHandlers.ofString());
      LOG.info("dotnet responded", "order_id", orderId, "status", resp.statusCode());
      respond(ex, 200, "processed");
    } catch (Exception e) {
      LOG.error("dotnet call failed", "order_id", orderId, "error", e.getMessage());
      respond(ex, 502, "downstream error");
    } finally {
      LOG.exportLogs();
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
