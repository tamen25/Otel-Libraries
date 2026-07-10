# Build the React app, then serve the static bundle with nginx.
FROM node:22-slim AS build
WORKDIR /app
COPY apps/frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY apps/frontend/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
