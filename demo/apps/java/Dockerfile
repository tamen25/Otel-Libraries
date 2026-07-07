# Build stage: install the local CloudOps logs library from source, then build the app.
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
# Copy and install the CloudOps logs library into the local Maven repo.
COPY libraries/java/logs /libs/logs
RUN mvn -q -f /libs/logs/pom.xml install -DskipTests
# Build the demo app.
COPY demo/apps/java/pom.xml .
COPY demo/apps/java/src ./src
RUN mvn -q package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /build/target/java-app.jar app.jar
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
