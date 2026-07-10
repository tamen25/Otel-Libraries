import api, { SpanKind, Span, propagation } from "@opentelemetry/api";

import { ServiceAttributes, SpanAttributes } from "../interface";
import { AttributeNames } from "../enums";

import { RequestMetadata, ServiceExtension } from "./types";

export class ServiceBusTopicServiceExtension implements ServiceExtension {
  /* eslint-disable class-methods-use-this */
  requestPreSpanHook(serviceName: string, attributes: ServiceAttributes): RequestMetadata {
    const spanKind: SpanKind = SpanKind.PRODUCER;
    const spanName = `azure.servicebus.topic ${attributes.serviceBusTopicAttributes?.topicName?.trim() || "topic"}`;

    const spanAttributes: SpanAttributes = {
      [AttributeNames.MESSAGING_SERVICE_TYPE]: serviceName,
      "azure.servicebus.topic.name": attributes.serviceBusTopicAttributes?.topicName,
      "azure.servicebus.namespace": attributes.serviceBusTopicAttributes?.namespace,
      "azure.servicebus.messaging.destination": attributes.serviceBusTopicAttributes?.messageDestination,
      "azure.servicebus.messaging.operation": "send",
    };

    return {
      spanAttributes,
      spanKind,
      spanName,
    };
  }
  /* eslint-enable class-methods-use-this */

  // Injects W3C trace context into Service Bus message applicationProperties.
  /* eslint-disable class-methods-use-this */
  requestPropagationAttributes(span: Span): any {
    const applicationProperties: any = {};
    propagation.inject(api.trace.setSpan(api.context.active(), span), applicationProperties);
    return applicationProperties;
  }
  /* eslint-enable class-methods-use-this */

  // Extracts W3C trace context from a received Service Bus message's applicationProperties.
  /* eslint-disable class-methods-use-this */
  retrievePropagationAttributes(event: any): any {
    const contextAttributes: any = {};
    const properties = event?.applicationProperties || event?.Records?.[0]?.applicationProperties || {};
    if (properties.traceparent) contextAttributes.traceparent = properties.traceparent;
    if (properties.tracestate) contextAttributes.tracestate = properties.tracestate;
    return contextAttributes;
  }
  /* eslint-enable class-methods-use-this */
}
