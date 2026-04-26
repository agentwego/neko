ARG CLOAKBROWSER_BASE_IMAGE=local/neko-cloakbrowser-base:local

FROM ${CLOAKBROWSER_BASE_IMAGE}

USER root

COPY supervisord.conf /etc/neko/supervisord/cloakbrowser.conf
COPY --chown=neko:neko preferences.json /home/neko/.config/cloakbrowser/Default/Preferences
COPY policies.json /etc/cloakbrowser/policies/managed/policies.json
COPY openbox.xml /etc/neko/openbox.xml
COPY entrypoint.sh /usr/local/bin/neko-cloakbrowser-entrypoint.sh
COPY cdp-healthcheck.sh /usr/local/bin/neko-cloakbrowser-cdp-healthcheck.sh
COPY cdp-proxy.py /usr/local/bin/neko-cloakbrowser-cdp-proxy.py
COPY proxy-auth-forwarder.py /usr/local/bin/neko-cloakbrowser-proxy-auth-forwarder.py
COPY browser-use-agent.py /usr/local/bin/browser-use-agent

RUN chmod +x /usr/local/bin/neko-cloakbrowser-entrypoint.sh /usr/local/bin/neko-cloakbrowser-cdp-healthcheck.sh /usr/local/bin/neko-cloakbrowser-cdp-proxy.py /usr/local/bin/neko-cloakbrowser-proxy-auth-forwarder.py /usr/local/bin/browser-use-agent

HEALTHCHECK --interval=10s --timeout=5s --retries=12 \
  CMD /usr/local/bin/neko-cloakbrowser-cdp-healthcheck.sh
