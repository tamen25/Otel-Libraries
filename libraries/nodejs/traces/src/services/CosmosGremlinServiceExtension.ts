import { SpanKind } from "@opentelemetry/api";

import { ServiceAttributes, SpanAttributes } from "../interface";

import { RequestMetadata, ServiceExtension } from "./types";

const ATTR_DB_SYSTEM = "db.system";

export class CosmosGremlinServiceExtension implements ServiceExtension {
  /* eslint-disable class-methods-use-this */
  requestPreSpanHook(serviceName: string, attributes: ServiceAttributes): RequestMetadata {
    const spanKind: SpanKind = SpanKind.CLIENT;
    const spanName = `azure.cosmosgremlin ${attributes.cosmosGremlinAttributes?.databaseName?.trim() || "database"}`;

    const spanAttributes: SpanAttributes = {
      [ATTR_DB_SYSTEM]: serviceName,
      "azure.cosmosgremlin.database.name": attributes.cosmosGremlinAttributes?.databaseName,
      "azure.cosmosgremlin.graph.name": attributes.cosmosGremlinAttributes?.graphName,
      "azure.cosmosgremlin.operation": attributes.cosmosGremlinAttributes?.operation,
    };

    return {
      spanAttributes,
      spanKind,
      spanName,
    };
  }
  /* eslint-enable class-methods-use-this */
}
