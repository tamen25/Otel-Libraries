// This file contains SSM parameters logic for OTel logs.
package com.cloudops.otel.logs;

import java.util.Objects;

public final class SsmParameters {
  public BackendConfig otel;

  // Checks whether empty.
  public boolean isEmpty() {
    return otel == null || otel.logs == null || (!hasValue(otel.logs.url) && !hasValue(otel.logs.apiKey));
  }

  // Handles has value.
  private static boolean hasValue(String value) {
    return value != null && !value.isBlank();
  }

  // Handles backend.
  public BackendConfig backend(String name) {
    if (Objects.equals(name, "otel")) return otel;
    return null;
  }
}
