// This file contains interfaces for traces src.
import { Context, SpanKind } from "@opentelemetry/api";

/**
 * Properties for startBasicSpan
 */
export interface spanProps {
  /**
   * The SpanKind of a span
   * @default {@link SpanKind.INTERNAL}
   */
  spanKind?: SpanKind;
  /**
   * The new span will be a root span
   * @default true
   */
  root?: boolean;
  /**
   * Set the current span as active context
   * @default false
   */
  setActiveContext?: boolean;
  /**
   * Pass the parent of the span
   * default is set active acontext
   */
  parent?: Context;
}

export type SpanAttributes =
  | {
      [key: string]: number | string | undefined;
    }
  | string
  | undefined;

// Interface for Service Bus topic attributes
export interface ServiceBusTopicAttributes {
  topicName: string; // Name of the topic
  namespace?: string; // The Service Bus namespace
  messageDestination?: string; // Destination of the message
}

// Interface for Service Bus queue attributes
export interface ServiceBusQueueAttributes {
  queueName: string; // Name of the queue
  namespace?: string; // The Service Bus namespace
  messageConsumer?: string;
  operation?: string; // Type of operation
}

// Interface for Event Hubs attributes
export interface EventHubsAttributes {
  eventHubName: string; // The name of the Event Hub
  partitionKey?: string; // The partition key for the event
  operation?: string; // Type of operation
  consumerGroup?: string; // The consumer group
}

// Interface for Cosmos DB attributes
export interface CosmosDbAttributes {
  containerName: string; // The name of the Cosmos DB container
  key?: string; // The partition key of the item
  operation?: string; // Cosmos DB operation
}

// Interface for Event Grid attributes
export interface EventGridAttributes {
  topicName: string; // The name of the Event Grid topic
  eventType?: string; // The type of the event
  source?: string; // The source of the event
  operation?: string; // The name of the operation
}

// Interface for Azure Functions attributes
export interface FunctionsAttributes {
  functionName: string; // The name of the function
  invocationId?: string; // The invocation id
  triggerType?: string; // The trigger type (http, timer, queue, ...)
}

// Interface for Cosmos DB Gremlin attributes
export interface CosmosGremlinAttributes {
  databaseName: string; // The name of the database
  graphName?: string; // The name of the graph
  operation?: string; // Operation performed
}

// Interface for Azure Data Explorer attributes
export interface DataExplorerAttributes {
  databaseName: string; // The name of the database
  tableName?: string; // The name of the table
  operation?: string; // The name of the operation
}

// Interface for API Management attributes
export interface ApiManagementAttributes {
  apiName: string; // Name of the API
  operation?: string; // The operation name
  httpMethod?: string; // The HTTP method (e.g., GET, POST)
  path?: string; // The path of the API endpoint
}

// Interface for Blob Storage attributes
export interface BlobStorageAttributes {
  containerName: string; // Name of the container
  blobName?: string; // Name of the blob
  operation?: string; // Operation performed
}

export type ServiceAttributes = {
  functionsAttributes?: FunctionsAttributes;
  serviceBusTopicAttributes?: ServiceBusTopicAttributes;
  serviceBusQueueAttributes?: ServiceBusQueueAttributes;
  eventHubsAttributes?: EventHubsAttributes;
  cosmosDbAttributes?: CosmosDbAttributes;
  eventGridAttributes?: EventGridAttributes;
  cosmosGremlinAttributes?: CosmosGremlinAttributes;
  dataExplorerAttributes?: DataExplorerAttributes;
  apiManagementAttributes?: ApiManagementAttributes;
  blobStorageAttributes?: BlobStorageAttributes;
};
