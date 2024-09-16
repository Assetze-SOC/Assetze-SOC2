FROM mcr.microsoft.com/dotnet/core/sdk:3.1-bionic AS build-env
WORKDIR /source

# Copy csproj and restore as distinct layers
COPY *.sln .
COPY WebGoatCore/*.csproj ./WebGoatCore/
RUN dotnet restore -r linux-x64

# Copy everything else and build
COPY WebGoatCore/. ./WebGoatCore/
WORKDIR /source/WebGoatCore
RUN dotnet publish -c Debug -o /app --no-restore

# Build runtime image
FROM mcr.microsoft.com/dotnet/core/aspnet:3.1-bionic
WORKDIR /app
COPY --from=build-env /app ./

EXPOSE 5000/tcp
EXPOSE 5001/tcp

ENTRYPOINT ["dotnet", "/app/WebGoatCore.dll"]