import '@testing-library/jest-dom/vitest'

// jsdom exposes Storage on window, but that window/global linkage can be absent
// (or about:blank makes it unavailable). Provide a real in-memory implementation
// so auth/api code behaves deterministically in tests.
class MemoryStorage {
  constructor() {
    this._map = new Map()
  }
  get length() {
    return this._map.size
  }
  clear() {
    this._map.clear()
  }
  getItem(key) {
    return this._map.has(String(key)) ? this._map.get(String(key)) : null
  }
  key(index) {
    return Array.from(this._map.keys())[index] ?? null
  }
  removeItem(key) {
    this._map.delete(String(key))
  }
  setItem(key, value) {
    this._map.set(String(key), String(value))
  }
}
globalThis.localStorage = window.localStorage || new MemoryStorage()
globalThis.sessionStorage = window.sessionStorage || new MemoryStorage()

if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })
}

// jsdom has no WebSocket; components that connect are driven by mocked REST
// fallbacks in the tests.
if (!window.WebSocket) {
  class FakeWebSocket {
    constructor() {}
    close() {}
    send() {}
  }
  window.WebSocket = FakeWebSocket
}

// recharts needs a ResizeObserver-like API in jsdom.
if (!window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}