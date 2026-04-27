#!/usr/bin/env python3
"""Register an init script on every current CDP page target.

This is a small companion process for the Neko CloakBrowser container.  The
patched Chromium binary supports --inject-script only for some embedder paths;
for the raw binary launched by Neko we use CDP's
Page.addScriptToEvaluateOnNewDocument instead.  Existing and future pages in the
current browser session then receive the same narrow desktop consistency guard.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.request

import websockets

CDP_HOST = os.environ.get("CLOAKBROWSER_CDP_HOST", "127.0.0.1")
CDP_PORT = int(os.environ.get("CLOAKBROWSER_CDP_PORT", "9222"))
SCRIPT_PATH = os.environ.get(
    "CLOAKBROWSER_DESKTOP_GUARD_SCRIPT",
    "/usr/local/share/neko/desktop-fingerprint-guard.js",
)
INTERVAL = float(os.environ.get("CLOAKBROWSER_CDP_INIT_INTERVAL", "2"))
MARKER_PREFIX = "neko-guard-"
DATA_PRELOAD_URL = "data:text/html,<script>window.name='neko-cdp-guard-preload';</script>"


def read_json(path: str):
    with urllib.request.urlopen(f"http://{CDP_HOST}:{CDP_PORT}{path}", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


async def call(ws, counter, method: str, params: dict | None = None):
    counter[0] += 1
    message_id = counter[0]
    await ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
    while True:
        message = json.loads(await ws.recv())
        if message.get("id") == message_id:
            return message


def build_source_with_marker(source: str, marker: str) -> str:
    return (
        "try { Object.defineProperty(window, '__nekoDesktopGuardMarker', "
        f"{{value: {json.dumps(marker)}, configurable: true, enumerable: false, writable: false}}); }} catch (_) {{}}\n"
        f"{source}"
    )


def build_recursive_install_expression(source: str, marker: str) -> str:
    """Install the guard into the top page and same-origin about:blank/srcdoc frames.

    CDP's Page.addScriptToEvaluateOnNewDocument covers normal document creation,
    but in this Neko/CloakBrowser runtime same-origin about:blank/srcdoc iframes
    created by fingerprinting pages can remain unpatched. Pixelscan/Sannysoft can
    then compare top-window WebGL/touch values with iframe values and flag masking.
    """
    source_with_marker = build_source_with_marker(source, marker)
    return """
(() => {
  const source = %s;
  const marker = %s;
  const install = (win) => {
    try {
      if (!win) return false;
      if (win.__nekoDesktopGuardInstalled) return true;
      if (win.__nekoDesktopGuardMarker === marker) return true;
      win.eval(source);
      return !!win.__nekoDesktopGuardInstalled;
    } catch (_) {
      return !!(win && win.__nekoDesktopGuardInstalled);
    }
  };
  const out = { top: install(window), frames: [] };
  const installFrames = () => {
    const frames = Array.from(document.querySelectorAll('iframe'));
    const snapshot = [];
    for (let i = 0; i < frames.length; i += 1) {
      const frame = frames[i];
      try {
        const win = frame.contentWindow;
        const href = win && win.location ? String(win.location.href) : null;
        snapshot.push({ index: i, href, ok: install(win), guard: !!(win && win.__nekoDesktopGuardInstalled) });
      } catch (error) {
        snapshot.push({ index: i, src: frame.src || '', ok: false, error: String(error) });
      }
    }
    return snapshot;
  };
  out.frames = installFrames();
  try {
    if (!window.__nekoFrameGuardInstaller) {
      Object.defineProperty(window, '__nekoFrameGuardInstaller', { value: true, configurable: false, enumerable: false, writable: false });
      const nativeCreateElement = Document.prototype.createElement;
      Document.prototype.createElement = new Proxy(nativeCreateElement, {
        apply(target, thisArg, args) {
          const element = Reflect.apply(target, thisArg, args);
          try {
            if (String(args && args[0] || '').toLowerCase() === 'iframe') {
              const patchFrame = () => {
                try { install(element.contentWindow); } catch (_) {}
              };
              queueMicrotask(patchFrame);
              setTimeout(patchFrame, 0);
              setTimeout(patchFrame, 10);
              try { element.addEventListener('load', patchFrame, true); } catch (_) {}
            }
          } catch (_) {}
          return element;
        },
      });
      const tick = () => { try { installFrames(); } catch (_) {} };
      setInterval(tick, 250);
      new MutationObserver(tick).observe(document.documentElement || document, { childList: true, subtree: true });
    }
  } catch (_) {}
  return JSON.stringify(out);
})()
""" % (json.dumps(source_with_marker), json.dumps(marker))


async def install_on_target(target: dict, source: str, marker: str) -> None:
    source_with_marker = build_source_with_marker(source, marker)
    async with websockets.connect(target["webSocketDebuggerUrl"], ping_interval=None) as ws:
        counter = [0]
        await call(ws, counter, "Page.enable")
        await call(ws, counter, "Runtime.enable")
        result = await call(ws, counter, "Page.addScriptToEvaluateOnNewDocument", {"source": source_with_marker})
        if "error" in result:
            raise RuntimeError(f"add init script failed: {result['error']}")
        # For a brand-new blank tab opened through CDP (/json/new about:blank),
        # force one neutral top-level navigation immediately after registering
        # the new-document script. This avoids the race where the first *real*
        # navigation happens before the watcher saw the target. Do not do this
        # for already-open real pages, or the installer would steal user tabs.
        target_url = target.get("url") or ""
        if target_url in {"about:blank", "chrome://newtab/"} or target_url.startswith("data:text/html,<script>window.name='neko-cdp-guard-preload'"):
            await call(ws, counter, "Page.navigate", {"url": DATA_PRELOAD_URL})
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                ready = await call(ws, counter, "Runtime.evaluate", {"expression": "document.readyState", "returnByValue": True})
                if ready.get("result", {}).get("result", {}).get("value") in {"interactive", "complete"}:
                    break
                await asyncio.sleep(0.1)
        # Also patch the currently loaded document and same-origin iframes; the
        # init script only applies before the next top-level navigation.
        await call(ws, counter, "Runtime.evaluate", {
            "expression": build_recursive_install_expression(source, marker),
            "returnByValue": True,
            "awaitPromise": True,
        })


async def verify_target(target: dict, source: str, marker: str) -> bool:
    async with websockets.connect(target["webSocketDebuggerUrl"], ping_interval=None) as ws:
        counter = [0]
        expression = build_recursive_install_expression(source, marker)
        result = await call(ws, counter, "Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        value = result.get("result", {}).get("result", {}).get("value")
        try:
            data = json.loads(value or "{}")
        except json.JSONDecodeError:
            return False
        if not data.get("top"):
            return False
        # Cross-origin frames may be unpatchable and reported with error; same-origin
        # frames that expose href should all become guarded.
        for frame in data.get("frames") or []:
            if frame.get("error"):
                continue
            if not frame.get("guard"):
                return False
        return True


async def reinstall_and_reload(target: dict, source: str) -> str:
    marker = f"{MARKER_PREFIX}{time.time_ns()}"
    await install_on_target(target, source, marker)
    # The live current document is already patched by install_on_target(). Avoid
    # reloading arbitrary user pages here: with this CloakBrowser build we observed
    # CDP init scripts not taking effect reliably after forced reloads, while the
    # live Runtime.evaluate path patches top/about:blank/srcdoc contexts correctly.
    return marker


async def main() -> None:
    source = open(SCRIPT_PATH, "r", encoding="utf-8").read()
    installed: dict[str, str] = {}
    print(f"cdp init script installer watching {CDP_HOST}:{CDP_PORT}", flush=True)
    while True:
        try:
            targets = read_json("/json/list")
            live_keys: set[str] = set()
            for target in targets:
                if target.get("type") != "page" or "webSocketDebuggerUrl" not in target:
                    continue
                key = target.get("id") or target["webSocketDebuggerUrl"]
                live_keys.add(key)
                marker = installed.get(key)
                if marker and await verify_target(target, source, marker):
                    continue
                marker = await reinstall_and_reload(target, source)
                # Verify once immediately; transient CDP/page timing can otherwise
                # produce a misleading "installed" log for a page whose current
                # document did not actually retain the guard.
                ok = await verify_target(target, source, marker)
                installed[key] = marker if ok else None
                print(f"installed desktop guard on target {key} marker={marker} ok={ok}", flush=True)
            for stale_key in set(installed) - live_keys:
                installed.pop(stale_key, None)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, KeyError, websockets.WebSocketException) as exc:
            print(f"cdp init script installer retrying after: {exc}", flush=True)
        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    # Give the browser a short head start when supervised together.
    time.sleep(float(os.environ.get("CLOAKBROWSER_CDP_INIT_STARTUP_DELAY", "3")))
    asyncio.run(main())
