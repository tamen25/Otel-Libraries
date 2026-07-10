// This file contains the service extension registry for traces services.
import { Span } from "@opentelemetry/api";

import { ServiceAttributes } from "../interface";
import { AzureService } from "../enums";

import { ServiceExtension, RequestMetadata, propagationAttributes } from "./types";
import { ServiceBusTopicServiceExtension } from "./ServiceBusTopicServiceExtension";
import { ServiceBusQueueServiceExtension } from "./ServiceBusQueueServiceExtension";
import { CosmosDbServiceExtension } from "./CosmosDbServiceExtension";
import { FunctionsServiceExtension } from "./FunctionsServiceExtension";
import { EventHubsServiceExtension } from "./EventHubsServiceExtension";
import { CosmosGremlinServiceExtension } from "./CosmosGremlinServiceExtension";
import { DataExplorerServiceExtension } from "./DataExplorerServiceExtension";
import { EventGridServiceExtension } from "./EventGridServiceExtension";
import { BlobStorageServiceExtension } from "./BlobStorageServiceExtension";
import { ApiManagementServiceExtension } from "./ApiManagementServiceExtension";

export class ServicesExtensions implements ServiceExtension {
  services: Map<string, ServiceExtension> = new Map();

  private validPropagationServices = new Set<AzureService>([
    AzureService.SERVICE_BUS_TOPIC,
    AzureService.SERVICE_BUS_QUEUE,
    AzureService.EVENT_GRID,
  ]);

  constructor() {
    this.services.set(AzureService.SERVICE_BUS_QUEUE, new ServiceBusQueueServiceExtension());
    this.services.set(AzureService.SERVICE_BUS_TOPIC, new ServiceBusTopicServiceExtension());
    this.services.set(AzureService.COSMOS_DB, new CosmosDbServiceExtension());
    this.services.set(AzureService.FUNCTIONS, new FunctionsServiceExtension());
    this.services.set(AzureService.EVENT_HUBS, new EventHubsServiceExtension());
    this.services.set(AzureService.COSMOS_GREMLIN, new CosmosGremlinServiceExtension());
    this.services.set(AzureService.DATA_EXPLORER, new DataExplorerServiceExtension());
    this.services.set(AzureService.EVENT_GRID, new EventGridServiceExtension());
    this.services.set(AzureService.BLOB_STORAGE, new BlobStorageServiceExtension());
    this.services.set(AzureService.API_MANAGEMENT, new ApiManagementServiceExtension());
  }

  requestPreSpanHook(serviceName: AzureService, attributes: ServiceAttributes): RequestMetadata {
    const serviceExtension = this.services.get(serviceName);
    if (!serviceExtension) return {};

    return serviceExtension.requestPreSpanHook(serviceName, attributes);
  }

  requestPropagationAttributes(span: Span, serviceName?: AzureService): propagationAttributes {
    if (serviceName && !this.validPropagationServices.has(serviceName)) {
      return undefined;
    }

    const serviceExtension = serviceName ? this.services.get(serviceName) : undefined;

    return serviceExtension?.requestPropagationAttributes?.(span);
  }

  retrievePropagationAttributes(event: any, serviceName?: AzureService): any {
    if (serviceName && !this.validPropagationServices.has(serviceName)) {
      return undefined;
    }

    const serviceExtension = serviceName ? this.services.get(serviceName) : undefined;

    return serviceExtension?.retrievePropagationAttributes?.(event);
  }
}
