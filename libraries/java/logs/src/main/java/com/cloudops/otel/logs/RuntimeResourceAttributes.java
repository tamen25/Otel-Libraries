// This file contains runtime resource attributes logic for OTel logs.
package com.cloudops.otel.logs;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

public final class RuntimeResourceAttributes {
  private static final String ATTR_SERVICE_NAME = "service.name";
  private static final String ATTR_CLOUD_PLATFORM = "cloud.platform";
  private static final String ATTR_CLOUD_PROVIDER = "cloud.provider";
  private static final String ATTR_CONTAINER_ID = "container.id";
  private static final String ATTR_CONTAINER_NAME = "container.name";
  private static final String ATTR_FAAS_NAME = "faas.name";
  private static final String ATTR_K8S_CLUSTER_NAME = "k8s.cluster.name";
  private static final String ATTR_K8S_NAMESPACE_NAME = "k8s.namespace.name";
  private static final String ATTR_K8S_NODE_NAME = "k8s.node.name";
  private static final String ATTR_K8S_POD_NAME = "k8s.pod.name";

  // Handles runtime resource attributes.
  private RuntimeResourceAttributes() {}

  // Creates the requested work.
  public static Map<String, String> create() {
    Map<String, String> attributes = new LinkedHashMap<>(parseResourceAttributes(env("OTEL_RESOURCE_ATTRIBUTES")));
    attributes.put(
        ATTR_SERVICE_NAME,
        firstEnv("OTEL_SERVICE_NAME", attributes.get(ATTR_SERVICE_NAME), "WEBSITE_SITE_NAME", "unknown_service"));
    attributes.put("pe-lib-log-ver", "1.16.2");

    addRuntimeAttributes(attributes);
    return Collections.unmodifiableMap(attributes);
  }

  // Adds runtime attributes.
  private static void addRuntimeAttributes(Map<String, String> attributes) {
    if (hasValue(firstEnv("FUNCTIONS_EXTENSION_VERSION", "FUNCTIONS_WORKER_RUNTIME"))) {
      attributes.put(ATTR_CLOUD_PROVIDER, "azure");
      attributes.put(ATTR_CLOUD_PLATFORM, "azure_functions");
      String siteName = env("WEBSITE_SITE_NAME");
      if (hasValue(siteName)) {
        attributes.put(ATTR_FAAS_NAME, siteName);
      }
      return;
    }

    if (hasValue(env("CONTAINER_APP_NAME"))) {
      attributes.put(ATTR_CLOUD_PROVIDER, "azure");
      attributes.put(ATTR_CLOUD_PLATFORM, "azure_container_apps");
    }

    if (hasValue(env("WEBSITE_SITE_NAME"))) {
      attributes.put(ATTR_CLOUD_PROVIDER, "azure");
      attributes.put(ATTR_CLOUD_PLATFORM, "azure_app_service");
    }

    boolean runningOnKubernetes = hasValue(env("KUBERNETES_SERVICE_HOST"));
    String k8sClusterName = firstEnv("K8S_CLUSTER_NAME", "AKS_CLUSTER_NAME");
    String k8sNamespaceName = firstEnv("K8S_NAMESPACE_NAME", "POD_NAMESPACE");
    String k8sNodeName = firstEnv("K8S_NODE_NAME", "NODE_NAME");
    String k8sPodName = firstEnv("K8S_POD_NAME", "POD_NAME");
    if (!hasValue(k8sPodName) && runningOnKubernetes) {
      k8sPodName = env("HOSTNAME");
    }

    if (runningOnKubernetes || hasValue(k8sClusterName) || hasValue(k8sNamespaceName) || hasValue(k8sPodName)) {
      attributes.put(ATTR_CLOUD_PROVIDER, "azure");
      attributes.put(ATTR_CLOUD_PLATFORM, "azure_aks");
    }

    putIfPresent(attributes, ATTR_K8S_CLUSTER_NAME, k8sClusterName);
    putIfPresent(attributes, ATTR_K8S_NAMESPACE_NAME, k8sNamespaceName);
    putIfPresent(attributes, ATTR_K8S_NODE_NAME, k8sNodeName);
    putIfPresent(attributes, ATTR_K8S_POD_NAME, k8sPodName);
    putIfPresent(attributes, ATTR_CONTAINER_ID, env("CONTAINER_ID"));
    putIfPresent(attributes, ATTR_CONTAINER_NAME, firstEnv("CONTAINER_NAME", "CONTAINER_APP_NAME"));
  }

  // Parses resource attributes.
  private static Map<String, String> parseResourceAttributes(String raw) {
    Map<String, String> attributes = new LinkedHashMap<>();
    if (!hasValue(raw)) return attributes;

    for (String item : raw.split(",")) {
      int separatorIndex = item.indexOf('=');
      if (separatorIndex <= 0) continue;

      String key = item.substring(0, separatorIndex).trim();
      String value = item.substring(separatorIndex + 1).trim();
      if (hasValue(key) && hasValue(value)) {
        attributes.put(key, value);
      }
    }

    return attributes;
  }

  // Handles put if present.
  private static void putIfPresent(Map<String, String> attributes, String key, String value) {
    if (hasValue(value)) attributes.put(key, value);
  }

  // Finds first env.
  private static String firstEnv(String... names) {
    for (String name : names) {
      String value = env(name);
      if (hasValue(value)) return value;
    }

    return "";
  }

  // Finds first env.
  private static String firstEnv(String firstName, String literalValue, String secondName, String fallback) {
    String first = env(firstName);
    if (hasValue(first)) return first;
    if (hasValue(literalValue)) return literalValue;
    String second = env(secondName);
    return hasValue(second) ? second : fallback;
  }

  // Handles env.
  private static String env(String name) {
    return System.getenv(name);
  }

  // Handles has value.
  private static boolean hasValue(String value) {
    return value != null && !value.isBlank();
  }
}
