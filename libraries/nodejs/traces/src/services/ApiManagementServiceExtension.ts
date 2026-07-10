import { SpanKind } from "@opentelemetry/api";

import { ServiceAttributes, SpanAttributes } from "../interface";
import { AttributeNames } from "../enums";

import { RequestMetadata, ServiceExtension } from "./types";

export class ApiManagementServiceExtension implements ServiceExtension {
  /* eslint-disable class-methods-use-this */
  requestPreSpanHook(serviceName: string, attributes: ServiceAttributes): RequestMetadata {
    const spanKind: SpanKind = SpanKind.SERVER;
    const spanName = `azure.apim ${attributes.apiManagementAttributes?.apiName?.trim() || "api"} ${
      attributes.apiManagementAttributes?.operation ?? ""
    }`.trim();

    const spanAttributes: SpanAttributes = {
      [AttributeNames.MESSAGING_SERVICE_TYPE]: serviceName,
      "azure.apim.api.name": attributes.apiManagementAttributes?.apiName,
      "azure.apim.method": attributes.apiManagementAttributes?.httpMethod,
      "azure.apim.resource.path": attributes.apiManagementAttributes?.path,
      "azure.apim.operation": attributes.apiManagementAttributes?.operation,
    };

    return {
      spanAttributes,
      spanKind,
      spanName,
    };
  }
  /* eslint-enable class-methods-use-this */
}
