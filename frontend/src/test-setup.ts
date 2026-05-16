import "@testing-library/jest-dom";

// jsdom lacks matchMedia — ThemeProvider needs it for prefers-color-scheme.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
}

// vitest 4 + jsdom 29 leaves window.localStorage undefined. ThemeProvider
// reads from it on mount, so provide a minimal in-memory shim.
if (typeof window !== "undefined" && !window.localStorage) {
  const store = new Map<string, string>();
  window.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k)! : null),
    setItem: (k, v) => void store.set(k, String(v)),
    removeItem: (k) => void store.delete(k),
    clear: () => store.clear(),
    key: (i) => Array.from(store.keys())[i] ?? null,
    get length() {
      return store.size;
    },
  } as Storage;
}
