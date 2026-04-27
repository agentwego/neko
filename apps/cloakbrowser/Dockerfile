ARG CLOAKBROWSER_BASE_IMAGE=local/neko-cloakbrowser-base:local

FROM ${CLOAKBROWSER_BASE_IMAGE}

ARG TARGETARCH
ARG AGENT_BROWSER_VERSION=v0.26.0

USER root

RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
      amd64) agent_browser_arch="x64" ;; \
      arm64) agent_browser_arch="arm64" ;; \
      *) echo "unsupported TARGETARCH=${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /usr/local/bin/agent-browser \
      "https://github.com/vercel-labs/agent-browser/releases/download/${AGENT_BROWSER_VERSION}/agent-browser-linux-${agent_browser_arch}"; \
    chmod 0755 /usr/local/bin/agent-browser; \
    agent-browser --help >/dev/null

COPY supervisord.conf /etc/neko/supervisord/cloakbrowser.conf
COPY --chown=neko:neko preferences.json /home/neko/.config/cloakbrowser/Default/Preferences
COPY policies.json /etc/cloakbrowser/policies/managed/policies.json
COPY openbox.xml /etc/neko/openbox.xml
COPY entrypoint.sh /usr/local/bin/neko-cloakbrowser-entrypoint.sh
COPY desktop-fingerprint-guard.js /usr/local/share/neko/desktop-fingerprint-guard.js
COPY cdp-healthcheck.sh /usr/local/bin/neko-cloakbrowser-cdp-healthcheck.sh
COPY cdp-proxy.py /usr/local/bin/neko-cloakbrowser-cdp-proxy.py
COPY cdp-init-script.py /usr/local/bin/neko-cloakbrowser-cdp-init-script.py
COPY proxy-auth-forwarder.py /usr/local/bin/neko-cloakbrowser-proxy-auth-forwarder.py
COPY cliproxyapi.py /usr/local/bin/neko-cliproxyapi

RUN chmod +x /usr/local/bin/neko-cloakbrowser-entrypoint.sh /usr/local/bin/neko-cloakbrowser-cdp-healthcheck.sh /usr/local/bin/neko-cloakbrowser-cdp-proxy.py /usr/local/bin/neko-cloakbrowser-cdp-init-script.py /usr/local/bin/neko-cloakbrowser-proxy-auth-forwarder.py /usr/local/bin/neko-cliproxyapi

HEALTHCHECK --interval=10s --timeout=5s --retries=12 \
  CMD /usr/local/bin/neko-cloakbrowser-cdp-healthcheck.sh
