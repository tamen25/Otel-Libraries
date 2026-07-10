import { SpanKind } from "@opentelemetry/api";

import { ServiceAttributes, SpanAttributes } from "../interface";

import { RequestMetadata, ServiceExtension } from "./types";

// The DB semantic-convention constant is experimental in @opentelemetry/semantic-conventions
// and not exported from the stable entrypoint used across these libraries, so the attribute
// key is inlined to keep parity with the other exporters/instrumentations.
const ATTR_DB_SYSTEM = "db.system";

export class CosmosDbServiceExtension implements ServiceExtension {
  /* eslint-disable class-methods-use-this */
  requestPreSpanHook(serviceName: string, attributes: ServiceAttributes): RequestMetadata {
    const spanKind: SpanKind = SpanKind.CLIENT;
    const spanName = `azure.cosmosdb ${attributes.cosmosDbAttributes?.containerName?.trim() || "container"} ${
      attributes.cosmosDbAttributes?.operation
    }`;

    const spanAttributes: SpanAttributes = {
      [ATTR_DB_SYSTEM]: serviceName,
      "azure.cosmosdb.container.name": attributes.cosmosDbAttributes?.containerName,
      "azure.cosmosdb.operation": attributes.cosmosDbAttributes?.operation,
      "azure.cosmosdb.partition.key": attributes.cosmosDbAttributes?.key,
    };

    return {
      spanAttributes,
      spanKind,
      spanName,
    };
  }
  /* eslint-enable class-methods-use-this */
}
