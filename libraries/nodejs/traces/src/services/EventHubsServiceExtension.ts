import { SpanKind } from "@opentelemetry/api";

import { ServiceAttributes, SpanAttributes } from "../interface";
import { AttributeNames } from "../enums";

import { RequestMetadata, ServiceExtension } from "./types";

export class EventHubsServiceExtension implements ServiceExtension {
  /* eslint-disable class-methods-use-this */
  requestPreSpanHook(serviceName: string, attributes: ServiceAttributes): RequestMetadata {
    const spanKind: SpanKind = SpanKind.PRODUCER;
    const spanName = `azure.eventhubs ${attributes.eventHubsAttributes?.eventHubName?.trim() || "eventhub"}`;

    const spanAttributes: SpanAttributes = {
      [AttributeNames.MESSAGING_SERVICE_TYPE]: serviceName,
      "azure.eventhubs.name": attributes.eventHubsAttributes?.eventHubName,
      "azure.eventhubs.partition.key": attributes.eventHubsAttributes?.partitionKey,
      "azure.eventhubs.consumer.group": attributes.eventHubsAttributes?.consumerGroup,
      "azure.eventhubs.operation": attributes.eventHubsAttributes?.operation,
    };

    return {
      spanAttributes,
      spanKind,
      spanName,
    };
  }
  /* eslint-enable class-methods-use-this */
}
