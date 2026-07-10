import { SpanKind } from "@opentelemetry/api";

import { ServiceAttributes, SpanAttributes } from "../interface";
import { AttributeNames } from "../enums";

import { RequestMetadata, ServiceExtension } from "./types";

export class EventGridServiceExtension implements ServiceExtension {
  /* eslint-disable class-methods-use-this */
  requestPreSpanHook(serviceName: string, attributes: ServiceAttributes): RequestMetadata {
    const spanKind: SpanKind = SpanKind.PRODUCER;
    const spanName = `azure.eventgrid ${attributes.eventGridAttributes?.topicName?.trim() || "topic"}`;

    const spanAttributes: SpanAttributes = {
      [AttributeNames.MESSAGING_SERVICE_TYPE]: serviceName,
      "azure.eventgrid.topic.name": attributes.eventGridAttributes?.topicName,
      "azure.eventgrid.source": attributes.eventGridAttributes?.source,
      "azure.eventgrid.event.type": attributes.eventGridAttributes?.eventType,
      "azure.eventgrid.operation": attributes.eventGridAttributes?.operation,
    };

    return {
      spanAttributes,
      spanKind,
      spanName,
    };
  }
  /* eslint-enable class-methods-use-this */
}
