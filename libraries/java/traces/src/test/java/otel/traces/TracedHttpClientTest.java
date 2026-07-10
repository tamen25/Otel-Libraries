package otel.traces;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class TracedHttpClientTest {
  @Test
  void tracedClientInjectsTraceparentAndReturnsResponse() throws Exception {
    HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
    AtomicReference<String> traceparent = new AtomicReference<>();
    server.createContext("/t", ex -> {
      traceparent.set(ex.getRequestHeaders().getFirst("traceparent"));
      ex.sendResponseHeaders(200, -1);
      ex.close();
    });
    server.start();
    try {
      Tracer tracer = Tracer.init();
      HttpResponse<Void> resp = tracer.tracedClient().send(
          HttpRequest.newBuilder(URI.create(
              "http://localhost:" + server.getAddress().getPort() + "/t")).GET().build(),
          HttpResponse.BodyHandlers.discarding());
      assertEquals(200, resp.statusCode());
      assertNotNull(traceparent.get(), "W3C traceparent header must be injected");
    } finally {
      server.stop(0);
    }
  }

  @Test
  void wrapRunsHandlerInsideServerSpan() throws Exception {
    HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
    Tracer tracer = Tracer.init();
    AtomicReference<Boolean> handled = new AtomicReference<>(false);
    server.createContext("/w", tracer.wrap("w", ex -> {
      handled.set(true);
      ex.sendResponseHeaders(200, -1);
      ex.close();
    }));
    server.start();
    try {
      HttpResponse<Void> resp = java.net.http.HttpClient.newHttpClient().send(
          HttpRequest.newBuilder(URI.create(
              "http://localhost:" + server.getAddress().getPort() + "/w")).GET().build(),
          HttpResponse.BodyHandlers.discarding());
      assertEquals(200, resp.statusCode());
      assertTrue(handled.get());
    } finally {
      server.stop(0);
    }
  }
}
