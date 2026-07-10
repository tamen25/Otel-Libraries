# Build stage: restore from a local NuGet source containing the Otel nupkgs.
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
# The local NuGet source is the mounted artifacts folder.
COPY artifacts /local-nuget
COPY apps/dotnet/nuget.config .
COPY apps/dotnet/DotnetApp.csproj .
RUN dotnet restore
COPY apps/dotnet/Program.cs .
RUN dotnet publish -c Release -o /out

FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /out .
EXPOSE 8081
CMD ["dotnet", "DotnetApp.dll"]
