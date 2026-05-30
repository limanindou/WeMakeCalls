#Call Service Dockerfile
#Build the Spring Boot application using a multi-stage Docker build
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn clean package -DskipTests

# Use a lightweight OpenJDK image for the runtime
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=build /app/target/call-service-0.0.1-SNAPSHOT.jar call-service.jar
EXPOSE 5000
ENTRYPOINT ["java", "-Dspring.data.mongodb.uri=mongodb://mongodb:27017/call-service", "-Dspring.datasource.url=jdbc:postgresql://postgresql:5432/wemakecalls", "-jar", "call-service.jar"]


