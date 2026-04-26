ARG CLOAKBROWSER_IMAGE=cloakhq/cloakbrowser@sha256:535b228133d3efffa25fa2a50fbff47ffcee21464bd7dcb69bcdaee144cc8100
ARG NEKO_BASE_IMAGE=ghcr.io/m1k1o/neko/google-chrome@sha256:5511a426db00c474ff15e21fcdaa3887d737f9d379080a2cd5d05bea81872fce
ARG BASE_IMAGE

FROM ${CLOAKBROWSER_IMAGE} AS cloakbrowser
ARG NEKO_BASE_IMAGE
ARG BASE_IMAGE
FROM ${NEKO_BASE_IMAGE}

USER root

COPY --from=cloakbrowser /usr/local /usr/local
COPY --from=cloakbrowser /root/.cloakbrowser /opt/cloakbrowser-root

RUN set -eux; \
    mkdir -p /etc/cloakbrowser/policies/managed /home/neko/.config/cloakbrowser/Default /root/.cloakbrowser; \
    bin_dir="$(find /opt/cloakbrowser-root -mindepth 1 -maxdepth 1 -type d -name 'chromium-*' | head -n1)"; \
    test -n "$bin_dir"; \
    rm -rf /opt/cloakbrowser-bin; \
    mv "$bin_dir" /opt/cloakbrowser-bin; \
    ln -sfn /opt/cloakbrowser-bin /root/.cloakbrowser/$(basename /opt/cloakbrowser-bin); \
    rm -f /etc/neko/supervisord/google-chrome.conf; \
    mkdir -p /home/neko/Downloads; \
    chown -R neko:neko /home/neko/.config/cloakbrowser /home/neko/Downloads; \
    rm -rf /opt/cloakbrowser-root

COPY supervisord.conf /etc/neko/supervisord/cloakbrowser.conf
COPY --chown=neko:neko preferences.json /home/neko/.config/cloakbrowser/Default/Preferences
COPY policies.json /etc/cloakbrowser/policies/managed/policies.json
COPY openbox.xml /etc/neko/openbox.xml
COPY entrypoint.sh /usr/local/bin/neko-cloakbrowser-entrypoint.sh
COPY cdp-healthcheck.sh /usr/local/bin/neko-cloakbrowser-cdp-healthcheck.sh
COPY cdp-proxy.py /usr/local/bin/neko-cloakbrowser-cdp-proxy.py
COPY proxy-auth-forwarder.py /usr/local/bin/neko-cloakbrowser-proxy-auth-forwarder.py

RUN chmod +x /usr/local/bin/neko-cloakbrowser-entrypoint.sh /usr/local/bin/neko-cloakbrowser-cdp-healthcheck.sh /usr/local/bin/neko-cloakbrowser-cdp-proxy.py /usr/local/bin/neko-cloakbrowser-proxy-auth-forwarder.py

ENV PATH=/usr/local/bin:${PATH} \
    PYTHONPATH=/usr/local/lib/python3.12/site-packages \
    CLOAKBROWSER_PROFILE_DIR=/home/neko/.config/cloakbrowser \
    CLOAKBROWSER_CDP_PORT=9222 \
    CLOAKBROWSER_PROXY_PORT=9223 \
    CLOAKBROWSER_WINDOW_SIZE=1920,1080 \
    CLOAKBROWSER_REMOTE_DEBUGGING_ADDRESS=127.0.0.1 \
    CLOAKBROWSER_BIN=/opt/cloakbrowser-bin/chrome \
    CLOAKBROWSER_EXTRA_ARGS="" \
    CLOAKBROWSER_PROXY_SERVER="" \
    CLOAKBROWSER_PROXY_USERNAME="" \
    CLOAKBROWSER_PROXY_PASSWORD="" \\
    CLOAKBROWSER_PROXY_BYPASS_LIST="<-loopback>" \
    CLOAKBROWSER_LOCAL_PROXY_HOST=127.0.0.1 \
    CLOAKBROWSER_LOCAL_PROXY_PORT=18080 \
    CLOAKBROWSER_STEALTH_ARGS_ENABLED=true \
    CLOAKBROWSER_FINGERPRINT_PLATFORM=windows \
    CLOAKBROWSER_FINGERPRINT="" \
    CLOAKBROWSER_START_URL=about:blank

HEALTHCHECK --interval=10s --timeout=5s --retries=12 \
  CMD /usr/local/bin/neko-cloakbrowser-cdp-healthcheck.sh
