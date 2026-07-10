// This file contains the CloudOps tracer for OTel traces.
package com.cloudops.otel.traces;

import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.api.trace.propagation.W3CTraceContextPropagator;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.propagation.ContextPropagators;
import io.opentelemetry.context.propagation.TextMapGetter;
import io.opentelemetry.context.propagation.TextMapSetter;
import io.opentelemetry.exporter.otlp.http.trace.OtlpHttpSpanExporter;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.export.BatchSpanProcessor;
import java.util.HashMap;
import java.util.Map;

public final class CloudOpsTracer {
  private static CloudOpsTracer instance;

  private OpenTelemetrySdk sdk;
  private SdkTracerProvider provider;
  private Tracer tracer;
  private boolean useOtel;

  private static final TextMapSetter<Map<String, String>> SETTER =
      (carrier, key, value) -> {
        if (carrier != null) {
          carrier.put(key, value);
        }
      };

  private static final TextMapGetter<Map<String, String>> GETTER =
      new TextMapGetter<>() {
        @Override
        public Iterable<String> keys(Map<String, String> carrier) {
          return carrier.keySet();
        }

        @Override
        public String get(Map<String, String> carrier, String key) {
          return carrier == null ? null : carrier.get(key);
        }
      };

  private CloudOpsTracer() {
    init();
  }

  // Initializes tracer.
  public static synchronized CloudOpsTracer initialiseTracer() {
    if (instance == null) {
      instance = new CloudOpsTracer();
    }
    return instance;
  }

  // Initializes tracer.
  public static CloudOpsTracer initializeTracer() {
    return initialiseTracer();
  }

  // Initializes the SDK, gating OTLP export on both an endpoint and X_ORG_ID.
  private void init() {
    Resource resource = Resource.getDefault().merge(Resource.create(TracesConfiguration.resourceAttributes()));
    var providerBuilder = SdkTracerProvider.builder().setResource(resource);

    String endpoint = TracesConfiguration.endpoint();
    String orgId = TracesConfiguration.orgId();
    boolean otelRequested = TracesConfiguration.exporters().contains("otel");

    if (otelRequested && endpoint != null && orgId != null) {
      OtlpHttpSpanExporter exporter = OtlpHttpSpanExporter.builder()
          .setEndpoint(endpoint)
          .addHeader("X-OrgId", orgId)
          .build();
      providerBuilder.addSpanProcessor(BatchSpanProcessor.builder(exporter).build());
      this.useOtel = true;
    }

    this.provider = providerBuilder.build();
    this.sdk = OpenTelemetrySdk.builder()
        .setTracerProvider(provider)
        .setPropagators(ContextPropagators.create(W3CTraceContextPropagator.getInstance()))
        .buildAndRegisterGlobal();
    this.tracer = sdk.getTracer("cloudops");
  }

  // Starts a SERVER span, continuing any W3C trace context found in the incoming headers.
  public Span startServerSpan(String name, Map<String, String> incomingHeaders) {
    Context extracted = sdk.getPropagators().getTextMapPropagator()
        .extract(Context.current(), incomingHeaders, GETTER);
    return tracer.spanBuilder(name).setSpanKind(SpanKind.SERVER).setParent(extracted).startSpan();
  }

  // Starts a CLIENT span in the current context.
  public Span startClientSpan(String name) {
    return tracer.spanBuilder(name).setSpanKind(SpanKind.CLIENT).startSpan();
  }

  // Injects the current W3C trace context into a new header map for an outgoing request.
  public Map<String, String> injectHeaders() {
    Map<String, String> carrier = new HashMap<>();
    sdk.getPropagators().getTextMapPropagator().inject(Context.current(), carrier, SETTER);
    return carrier;
  }

  // Returns the tracer for manual spans.
  public Tracer tracer() {
    return tracer;
  }

  // Whether the OTLP exporter is active.
  public boolean isOtelEnabled() {
    return useOtel;
  }

  // Force-flushes pending spans.
  public void exportSpans() {
    if (provider != null) {
      provider.forceFlush();
    }
  }
}
