FROM node:22-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_MCP_PORT=8931 \
    CLIPROXY_PORT=8932 \
    PLAYWRIGHT_MCP_STEALTH_ENABLED=true

WORKDIR /opt/neko-playwright-mcp

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates supervisor; \
    apt-get clean -y; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/*

COPY package.json package-lock.json* ./
RUN set -eux; \
    npm install --omit=dev; \
    npm cache clean --force

COPY start.js cliproxy.js stealth-init.js ./
COPY healthcheck.js /usr/local/bin/neko-playwright-mcp-healthcheck.js
COPY supervisord.conf /etc/supervisor/conf.d/neko-playwright-mcp.conf

RUN set -eux; \
    ln -sf /opt/neko-playwright-mcp/start.js /usr/local/bin/neko-playwright-mcp; \
    ln -sf /opt/neko-playwright-mcp/cliproxy.js /usr/local/bin/neko-cliproxy; \
    chmod +x /opt/neko-playwright-mcp/start.js /opt/neko-playwright-mcp/cliproxy.js

HEALTHCHECK --interval=10s --timeout=5s --retries=12 \
  CMD ["node", "/usr/local/bin/neko-playwright-mcp-healthcheck.js"]

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
