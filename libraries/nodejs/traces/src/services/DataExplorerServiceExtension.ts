import { SpanKind } from "@opentelemetry/api";

import { ServiceAttributes, SpanAttributes } from "../interface";

import { RequestMetadata, ServiceExtension } from "./types";

const ATTR_DB_SYSTEM = "db.system";

export class DataExplorerServiceExtension implements ServiceExtension {
  /* eslint-disable class-methods-use-this */
  requestPreSpanHook(serviceName: string, attributes: ServiceAttributes): RequestMetadata {
    const spanKind: SpanKind = SpanKind.CLIENT;
    const spanName = `azure.dataexplorer ${attributes.dataExplorerAttributes?.databaseName?.trim() || "database"}`;

    const spanAttributes: SpanAttributes = {
      [ATTR_DB_SYSTEM]: serviceName,
      "azure.dataexplorer.database.name": attributes.dataExplorerAttributes?.databaseName,
      "azure.dataexplorer.table.name": attributes.dataExplorerAttributes?.tableName,
      "azure.dataexplorer.operation": attributes.dataExplorerAttributes?.operation,
    };

    return {
      spanAttributes,
      spanKind,
      spanName,
    };
  }
  /* eslint-enable class-methods-use-this */
}
