// Desktop consistency guard for CloakBrowser-in-Neko.
// CloakBrowser's linux fingerprint profile currently exposes a mobile-like
// coarse/touch pointer (maxTouchPoints=10, pointer:coarse=true, hover=false)
// even while the UA/platform/screen are Linux desktop. Pixelscan marks that
// contradiction as fingerprint masking/inconsistency.  Keep the override narrow:
// only pointer/touch media-query surfaces, navigator.maxTouchPoints, and
// WebGL debug renderer strings when they expose a visibly datacenter/gaming GPU.
(() => {
  const GUARD_VERSION = '2026-04-worker-webgl-blob';
  try {
    if (window.__nekoDesktopGuardInstalled && window.__nekoDesktopGuardVersion === GUARD_VERSION) return;
    Object.defineProperty(window, '__nekoDesktopGuardInstalled', {
      value: true,
      configurable: true,
      enumerable: false,
      writable: false,
    });
    Object.defineProperty(window, '__nekoDesktopGuardVersion', {
      value: GUARD_VERSION,
      configurable: true,
      enumerable: false,
      writable: false,
    });
  } catch (_) {}

  const patchedNativeFunctions = new WeakMap();
  const nativeToString = Function.prototype.toString;
  let functionToStringPatched = false;
  const ensureFunctionToStringPatch = () => {
    if (functionToStringPatched) return;
    functionToStringPatched = true;
    try {
      const toStringProxy = new Proxy(nativeToString, {
        apply(target, thisArg, args) {
          if (patchedNativeFunctions.has(thisArg)) return patchedNativeFunctions.get(thisArg);
          return Reflect.apply(target, thisArg, args);
        },
      });
      patchedNativeFunctions.set(toStringProxy, 'function toString() { [native code] }');
      Object.defineProperty(Function.prototype, 'toString', {
        value: toStringProxy,
        writable: true,
        enumerable: false,
        configurable: true,
      });
    } catch (_) {
      functionToStringPatched = false;
    }
  };

  const markNativeLike = (fn, source) => {
    if (typeof fn === 'function') {
      patchedNativeFunctions.set(fn, source || `function ${fn.name || ''}() { [native code] }`);
      ensureFunctionToStringPatch();
    }
    return fn;
  };

  const nativeLikeGetter = (name, value, nativeSource) => {
    const getter = function() { return value; };
    return markNativeLike(getter, nativeSource || `function get ${name}() { [native code] }`);
  };

  const patchNavigatorGetter = (name, value) => {
    try {
      const inherited = Object.getOwnPropertyDescriptor(Navigator.prototype, name);
      const nativeSource = inherited && typeof inherited.get === 'function'
        ? nativeToString.call(inherited.get)
        : `function get ${name}() { [native code] }`;
      Object.defineProperty(Navigator.prototype, name, {
        get: nativeLikeGetter(name, value, nativeSource),
        enumerable: inherited ? inherited.enumerable : true,
        configurable: inherited ? inherited.configurable : true,
      });
    } catch (_) {}
    try {
      // Avoid leaving an own navigator descriptor when possible; own accessors are
      // easier for fingerprinting pages to flag than prototype-level native-like ones.
      delete navigator[name];
    } catch (_) {}
  };

  patchNavigatorGetter('maxTouchPoints', 0);
  patchNavigatorGetter('msMaxTouchPoints', 0);

  try {
    delete window.ontouchstart;
    delete Document.prototype.ontouchstart;
    delete HTMLElement.prototype.ontouchstart;
  } catch (_) {}

  try {
    // A real non-touch Linux desktop normally does not expose touch constructors
    // at all. Returning undefined while keeping an own property still leaves
    // `'TouchEvent' in window === true`, which Pixelscan can treat as masking.
    delete window.TouchEvent;
    delete window.Touch;
    delete window.TouchList;
  } catch (_) {}

  let nativeMatchMedia = null;
  try {
    if (window.__nekoNativeMatchMedia) {
      nativeMatchMedia = window.__nekoNativeMatchMedia;
    } else if (window.matchMedia) {
      nativeMatchMedia = window.matchMedia.bind(window);
      Object.defineProperty(window, '__nekoNativeMatchMedia', {
        value: nativeMatchMedia,
        configurable: true,
        enumerable: false,
        writable: false,
      });
    }
  } catch (_) {
    nativeMatchMedia = window.matchMedia ? window.matchMedia.bind(window) : null;
  }
  if (!nativeMatchMedia) return;

  const normalizeMediaQuery = (query) => String(query)
    .trim()
    .toLowerCase()
    // Chromium canonicalizes `(pointer:coarse)` to `(pointer: coarse)`, but
    // fingerprinting pages often probe both spellings. Normalize optional
    // whitespace around media-feature colons before lookup.
    .replace(/\s*:\s*/g, ':');

  const overrides = new Map([
    ['(pointer:coarse)', false],
    ['(pointer:fine)', true],
    ['(hover:hover)', true],
    ['(hover:none)', false],
    ['(any-pointer:coarse)', false],
    ['(any-pointer:fine)', true],
    ['(any-hover:hover)', true],
    ['(any-hover:none)', false],
  ]);

  const patchedMatchMedia = markNativeLike(function matchMedia(query) {
    const normalized = normalizeMediaQuery(query);
    const native = nativeMatchMedia(query);
    if (!overrides.has(normalized)) {
      return native;
    }

    const matches = overrides.get(normalized);
    try {
      return new Proxy(native, {
        get(target, prop, receiver) {
          if (prop === 'matches') return matches;
          // MediaQueryList accessors are native brand-checked. Reading many of
          // them through a Proxy receiver throws Illegal invocation, so resolve
          // known accessors/methods on the real native object only.
          if (prop === 'media') return target.media;
          if (prop === 'onchange') return target.onchange;
          if (prop === 'addListener') return target.addListener && target.addListener.bind(target);
          if (prop === 'removeListener') return target.removeListener && target.removeListener.bind(target);
          if (prop === 'addEventListener') return target.addEventListener && target.addEventListener.bind(target);
          if (prop === 'removeEventListener') return target.removeEventListener && target.removeEventListener.bind(target);
          if (prop === 'dispatchEvent') return target.dispatchEvent && target.dispatchEvent.bind(target);
          if (prop === Symbol.toStringTag) return target[Symbol.toStringTag];
          try {
            const value = target[prop];
            return typeof value === 'function' ? value.bind(target) : value;
          } catch (_) {
            return undefined;
          }
        },
      });
    } catch (_) {
      return native;
    }
  }, 'function matchMedia() { [native code] }');
  try {
    Object.defineProperty(window, 'matchMedia', {
      value: patchedMatchMedia,
      writable: true,
      enumerable: true,
      configurable: true,
    });
  } catch (_) {
    window.matchMedia = patchedMatchMedia;
  }

  const webglDebugVendor = 'Intel Inc.';
  const webglDebugRenderer = 'ANGLE (Intel Inc., Intel(R) UHD Graphics 630, OpenGL 4.5.0)';
  const webglWorkerPatchSource = `(() => {
    const webglDebugVendor = ${JSON.stringify('Intel Inc.')};
    const webglDebugRenderer = ${JSON.stringify('ANGLE (Intel Inc., Intel(R) UHD Graphics 630, OpenGL 4.5.0)')};
    const patchWebGLDebugInfo = (proto) => {
      if (!proto || proto.__nekoWebGLDebugGuardInstalled) return;
      try {
        const nativeGetParameter = proto.getParameter;
        const nativeGetExtension = proto.getExtension;
        const debugInfo = { UNMASKED_VENDOR_WEBGL: 37445, UNMASKED_RENDERER_WEBGL: 37446 };
        Object.defineProperty(proto, '__nekoWebGLDebugGuardInstalled', { value: true, configurable: false, enumerable: false, writable: false });
        proto.getExtension = function getExtension(name) {
          if (String(name).toUpperCase() === 'WEBGL_DEBUG_RENDERER_INFO') return debugInfo;
          return nativeGetExtension.apply(this, arguments);
        };
        proto.getParameter = function getParameter(parameter) {
          if (parameter === debugInfo.UNMASKED_VENDOR_WEBGL) return webglDebugVendor;
          if (parameter === debugInfo.UNMASKED_RENDERER_WEBGL) return webglDebugRenderer;
          return nativeGetParameter.apply(this, arguments);
        };
        try {
          Object.defineProperty(self, '__nekoDesktopGuardInstalled', { value: true, configurable: true, enumerable: false, writable: false });
          Object.defineProperty(self, '__nekoDesktopGuardVersion', { value: '2026-04-worker-webgl-blob', configurable: true, enumerable: false, writable: false });
        } catch (_) {};
      } catch (_) {}
    };
    patchWebGLDebugInfo(self.WebGLRenderingContext && WebGLRenderingContext.prototype);
    patchWebGLDebugInfo(self.WebGL2RenderingContext && WebGL2RenderingContext.prototype);
  })();\n`;

  const patchWebGLDebugInfo = (proto) => {
    if (!proto || proto.__nekoWebGLDebugGuardInstalled) return;
    try {
      const nativeGetParameter = proto.getParameter;
      const nativeGetExtension = proto.getExtension;
      const debugInfo = { UNMASKED_VENDOR_WEBGL: 37445, UNMASKED_RENDERER_WEBGL: 37446 };
      Object.defineProperty(proto, '__nekoWebGLDebugGuardInstalled', {
        value: true,
        configurable: false,
        enumerable: false,
        writable: false,
      });
      proto.getExtension = markNativeLike(function getExtension(name) {
        if (String(name).toUpperCase() === 'WEBGL_DEBUG_RENDERER_INFO') return debugInfo;
        return nativeGetExtension.apply(this, arguments);
      }, nativeToString.call(nativeGetExtension));
      proto.getParameter = markNativeLike(function getParameter(parameter) {
        if (parameter === debugInfo.UNMASKED_VENDOR_WEBGL) return webglDebugVendor;
        if (parameter === debugInfo.UNMASKED_RENDERER_WEBGL) return webglDebugRenderer;
        return nativeGetParameter.apply(this, arguments);
      }, nativeToString.call(nativeGetParameter));
    } catch (_) {}
  };
  patchWebGLDebugInfo(window.WebGLRenderingContext && WebGLRenderingContext.prototype);
  patchWebGLDebugInfo(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype);

  try {
    if (!window.__nekoWorkerWebGLGuardInstalled && window.Worker && window.Blob && window.URL) {
      Object.defineProperty(window, '__nekoWorkerWebGLGuardInstalled', {
        value: true,
        configurable: false,
        enumerable: false,
        writable: false,
      });
      const nativeWorker = window.Worker;
      const patchWorkerSource = (scriptURL) => {
        try {
          const wrapperSource = `${webglWorkerPatchSource}try { importScripts(${JSON.stringify(String(scriptURL))}); } catch (error) { setTimeout(() => { throw error; }, 0); }`;
          return URL.createObjectURL(new Blob([wrapperSource], { type: 'application/javascript' }));
        } catch (_) {
          return scriptURL;
        }
      };
      const workerProxy = markNativeLike(new Proxy(nativeWorker, {
        construct(target, args, newTarget) {
          if (args && args.length > 0) {
            args = [patchWorkerSource(args[0]), ...Array.prototype.slice.call(args, 1)];
          }
          return Reflect.construct(target, args, newTarget);
        },
        apply(target, thisArg, args) {
          if (args && args.length > 0) {
            args = [patchWorkerSource(args[0]), ...Array.prototype.slice.call(args, 1)];
          }
          return Reflect.apply(target, thisArg, args);
        },
      }), nativeToString.call(nativeWorker));
      Object.defineProperty(window, 'Worker', {
        value: workerProxy,
        writable: true,
        enumerable: false,
        configurable: true,
      });
    }
  } catch (_) {}
})();
