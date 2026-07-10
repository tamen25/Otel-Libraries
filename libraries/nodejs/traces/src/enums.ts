// This file contains enums for traces src.
export enum AttributeNames {
  TRIGGER_SERVICE_TYPE = "trigger.service.type",
  TRIGGER_SERVICE_NAME = "trigger.service",
  AZURE_OPERATION = "azure.operation",
  AZURE_REGION = "azure.region",
  AZURE_SERVICE_API = "azure.service.api",
  AZURE_SERVICE_NAME = "azure.service.name",
  AZURE_SERVICE_IDENTIFIER = "azure.service.identifier",
  AZURE_REQUEST_ID = "azure.request.id",
  MESSAGING_SERVICE_TYPE = "azure.messaging.service.type",
}

export enum AzureService {
  FUNCTIONS = "functions",
  SERVICE_BUS_TOPIC = "servicebustopic",
  SERVICE_BUS_QUEUE = "servicebusqueue",
  EVENT_HUBS = "eventhubs",
  EVENT_GRID = "eventgrid",
  COSMOS_DB = "cosmosdb",
  COSMOS_GREMLIN = "cosmosgremlin",
  DATA_EXPLORER = "dataexplorer",
  API_MANAGEMENT = "apimanagement",
  BLOB_STORAGE = "blobstorage",
}
