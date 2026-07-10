package otel.traces;

import io.opentelemetry.api.trace.Span;
import io.opentelemetry.context.Scope;
import java.io.IOException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

// Traced wrapper over java.net.http.HttpClient: each send() runs in a CLIENT
// span named "<METHOD> <path>" with W3C tracecontext headers injected, so the
// downstream service continues the same trace.
public final class TracedHttpClient {
  private final Tracer tracer;
  private final HttpClient delegate;

  TracedHttpClient(Tracer tracer, HttpClient delegate) {
    this.tracer = tracer;
    this.delegate = delegate;
  }

  public <T> HttpResponse<T> send(HttpRequest request, HttpResponse.BodyHandler<T> handler)
      throws IOException, InterruptedException {
    Span span = tracer.startClientSpan(request.method() + " " + request.uri().getPath());
    try (Scope scope = span.makeCurrent()) {
      HttpRequest.Builder builder = HttpRequest.newBuilder(request, (k, v) -> true);
      tracer.injectHeaders().forEach(builder::header);
      return delegate.send(builder.build(), handler);
    } catch (IOException | InterruptedException e) {
      span.recordException(e);
      throw e;
    } finally {
      span.end();
    }
  }
}
