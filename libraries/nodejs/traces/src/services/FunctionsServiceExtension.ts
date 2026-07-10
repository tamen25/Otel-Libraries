import { SpanKind } from "@opentelemetry/api";

import { ServiceAttributes, SpanAttributes } from "../interface";
import { AttributeNames } from "../enums";

import { RequestMetadata, ServiceExtension } from "./types";

export class FunctionsServiceExtension implements ServiceExtension {
  /* eslint-disable class-methods-use-this */
  requestPreSpanHook(serviceName: string, attributes: ServiceAttributes): RequestMetadata {
    const spanKind: SpanKind = SpanKind.SERVER;
    const functionName = attributes.functionsAttributes?.functionName
      || process.env.WEBSITE_SITE_NAME
      || "function";
    const spanName = `azure.functions ${functionName}`;

    const spanAttributes: SpanAttributes = {
      [AttributeNames.MESSAGING_SERVICE_TYPE]: serviceName,
      "azure.functions.name": attributes.functionsAttributes?.functionName,
      "azure.functions.invocation.id": attributes.functionsAttributes?.invocationId,
      "azure.functions.trigger.type": attributes.functionsAttributes?.triggerType,
    };

    return {
      spanAttributes,
      spanKind,
      spanName,
    };
  }
  /* eslint-enable class-methods-use-this */
}
