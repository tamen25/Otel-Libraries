FROM node:22-slim
WORKDIR /app
# Install the locally-packed CloudOps logs + traces tarballs (from build context).
COPY artifacts/cloudops-otel-logs-0.1.0.tgz /tmp/
COPY artifacts/cloudops-otel-traces-0.1.0.tgz /tmp/
COPY apps/node/package.json .
RUN npm install --no-audit --no-fund /tmp/cloudops-otel-logs-0.1.0.tgz /tmp/cloudops-otel-traces-0.1.0.tgz
COPY apps/node/server.js .
EXPOSE 8090
CMD ["node", "server.js"]
