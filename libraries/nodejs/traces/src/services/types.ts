// This file contains service extension types for traces services.
import { SpanKind, Span } from "@opentelemetry/api";

import { ServiceAttributes, SpanAttributes } from "../interface";
import { AzureService } from "../enums";

export interface RequestMetadata {
  spanAttributes?: SpanAttributes;
  spanKind?: SpanKind;
  spanName?: string;
}

export type propagationAttributes = any;

export interface ServiceExtension {
  requestPreSpanHook: (serviceName: AzureService, attributes: ServiceAttributes) => RequestMetadata;

  requestPropagationAttributes?: (span: Span, serviceName?: AzureService) => propagationAttributes;

  retrievePropagationAttributes?: (event: any, serviceName?: AzureService) => any;
}
