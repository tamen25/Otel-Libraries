FROM node:22-slim
WORKDIR /app
# Install the locally-packed logs + traces tarballs (from build context).
COPY artifacts/otel-logs-0.1.0.tgz /tmp/
COPY artifacts/otel-traces-0.1.0.tgz /tmp/
COPY apps/node/package.json .
RUN npm install --no-audit --no-fund /tmp/otel-logs-0.1.0.tgz /tmp/otel-traces-0.1.0.tgz
COPY apps/node/server.js .
EXPOSE 8090
CMD ["node", "server.js"]
