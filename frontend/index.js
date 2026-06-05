/**
 * Custom app entry point.
 *
 * IMPORTANT: This file uses CommonJS (require/module.exports), NOT ES modules.
 * That guarantees the polyfill code at the top runs BEFORE any module is
 * imported — including react-dom which references DOMException on load.
 *
 * Load order: polyfills → expo-router/entry → app/_layout.tsx → screens
 */

// ── Web API polyfills for Hermes ─────────────────────────────────────────────

// react-dom v19 references DOMException when handling AbortController errors.
// Hermes does not expose DOMException as a global, so we polyfill it here.
if (typeof global.DOMException === 'undefined') {
  global.DOMException = class DOMException extends Error {
    constructor(message = '', name = 'Error') {
      super(message);
      this.name = name;
      // Preserve stack trace in V8 / Hermes
      if (Error.captureStackTrace) {
        Error.captureStackTrace(this, global.DOMException);
      }
    }
    get code() { return 0; }
  };
}

// AbortController / AbortSignal — needed by some fetch polyfills and react-dom 19
if (typeof global.AbortController === 'undefined') {
  const listeners = new WeakMap();
  global.AbortSignal = class AbortSignal {
    constructor() {
      this.aborted = false;
      this.reason = undefined;
      listeners.set(this, []);
    }
    addEventListener(_type, fn) { listeners.get(this)?.push(fn); }
    removeEventListener(_type, fn) {
      const arr = listeners.get(this);
      if (arr) {
        const i = arr.indexOf(fn);
        if (i >= 0) arr.splice(i, 1);
      }
    }
    dispatchEvent() {}
  };
  global.AbortController = class AbortController {
    constructor() { this.signal = new global.AbortSignal(); }
    abort(reason) {
      if (this.signal.aborted) return;
      this.signal.aborted = true;
      this.signal.reason = reason ?? new global.DOMException('signal is aborted without reason');
    }
  };
}

// ── Hand off to expo-router ──────────────────────────────────────────────────
require('expo-router/entry');
