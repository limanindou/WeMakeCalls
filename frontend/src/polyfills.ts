// Ensure libraries expecting Node-style global can run in browser bundles.
if (typeof globalThis !== 'undefined' && !(globalThis as any).global) {
  (globalThis as any).global = globalThis;
}
