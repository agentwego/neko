// Stealth initialization script for pages controlled through Playwright MCP.
//
// The sidecar connects to the already-running CloakBrowser instance by CDP, so
// we cannot replace the browser process with playwright-extra at runtime.  This
// script applies the high-value evasions at document start for every MCP page.
// It intentionally keeps values conservative and browser-derived where possible
// so it does not fight CloakBrowser's own fingerprint layer.
(() => {
  const defineGetter = (target, prop, getter) => {
    try {
      Object.defineProperty(target, prop, {
        configurable: true,
        enumerable: true,
        get: getter,
      })
    } catch (_) {}
  }

  const patchToString = (fn, nativeName) => {
    try {
      Object.defineProperty(fn, 'toString', {
        configurable: true,
        value: () => `function ${nativeName || fn.name || ''}() { [native code] }`,
      })
    } catch (_) {}
  }

  defineGetter(Navigator.prototype, 'webdriver', () => undefined)

  if (!globalThis.chrome) {
    try {
      Object.defineProperty(globalThis, 'chrome', {
        configurable: true,
        enumerable: true,
        value: {},
      })
    } catch (_) {}
  }
  if (globalThis.chrome && !globalThis.chrome.runtime) {
    try {
      Object.defineProperty(globalThis.chrome, 'runtime', {
        configurable: true,
        enumerable: true,
        value: {},
      })
    } catch (_) {}
  }

  const languages = (globalThis.__NEKO_STEALTH_LANGUAGES__ || 'en-US,en')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean)
  if (languages.length) {
    defineGetter(Navigator.prototype, 'languages', () => Object.freeze([...languages]))
    defineGetter(Navigator.prototype, 'language', () => languages[0])
  }

  const pluginsLength = Number(globalThis.__NEKO_STEALTH_PLUGINS_LENGTH__ || '5')
  if (pluginsLength > 0) {
    defineGetter(Navigator.prototype, 'plugins', () => {
      const plugins = []
      for (let i = 0; i < pluginsLength; i += 1) {
        plugins.push({
          name: `Chrome PDF Plugin ${i + 1}`,
          filename: `internal-pdf-viewer-${i + 1}`,
          description: 'Portable Document Format',
          length: 1,
          item: () => null,
          namedItem: () => null,
        })
      }
      Object.defineProperty(plugins, 'item', { value: (i) => plugins[i] || null })
      Object.defineProperty(plugins, 'namedItem', { value: (name) => plugins.find((p) => p.name === name) || null })
      return Object.freeze(plugins)
    })
  }

  const vendor = globalThis.__NEKO_STEALTH_VENDOR__ || 'Google Inc.'
  defineGetter(Navigator.prototype, 'vendor', () => vendor)

  const hardwareConcurrency = Number(globalThis.__NEKO_STEALTH_HARDWARE_CONCURRENCY__ || '')
  if (Number.isFinite(hardwareConcurrency) && hardwareConcurrency > 0) {
    defineGetter(Navigator.prototype, 'hardwareConcurrency', () => hardwareConcurrency)
  }

  const deviceMemory = Number(globalThis.__NEKO_STEALTH_DEVICE_MEMORY__ || '')
  if (Number.isFinite(deviceMemory) && deviceMemory > 0) {
    defineGetter(Navigator.prototype, 'deviceMemory', () => deviceMemory)
  }

  const permissionsQuery = globalThis.navigator?.permissions?.query
  if (permissionsQuery) {
    const patchedQuery = function query(parameters) {
      if (parameters && parameters.name === 'notifications') {
        return Promise.resolve({ state: Notification.permission, onchange: null })
      }
      return Reflect.apply(permissionsQuery, this, arguments)
    }
    patchToString(patchedQuery, 'query')
    try {
      globalThis.navigator.permissions.query = patchedQuery
    } catch (_) {}
  }

  const originalGetParameter = globalThis.WebGLRenderingContext?.prototype?.getParameter
  if (originalGetParameter) {
    const webglVendor = globalThis.__NEKO_STEALTH_WEBGL_VENDOR__ || ''
    const webglRenderer = globalThis.__NEKO_STEALTH_WEBGL_RENDERER__ || ''
    const patchedGetParameter = function getParameter(parameter) {
      if (parameter === 37445 && webglVendor) return webglVendor
      if (parameter === 37446 && webglRenderer) return webglRenderer
      return Reflect.apply(originalGetParameter, this, arguments)
    }
    patchToString(patchedGetParameter, 'getParameter')
    try {
      globalThis.WebGLRenderingContext.prototype.getParameter = patchedGetParameter
    } catch (_) {}
  }
})()
