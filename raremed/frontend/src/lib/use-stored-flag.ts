"use client";

import { useCallback, useSyncExternalStore } from "react";

type FlagStore = {
  get: () => boolean;
  set: (value: boolean) => void;
  subscribe: (listener: () => void) => () => void;
};

const stores = new Map<string, FlagStore>();

function flagStore(key: string, fallback: boolean): FlagStore {
  const existing = stores.get(key);
  if (existing) return existing;

  const listeners = new Set<() => void>();
  const store: FlagStore = {
    get: () => {
      const stored = window.localStorage.getItem(key);
      if (stored === "1") return true;
      if (stored === "0") return false;
      return fallback;
    },
    set: (value) => {
      window.localStorage.setItem(key, value ? "1" : "0");
      listeners.forEach((listener) => listener());
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
  stores.set(key, store);
  return store;
}

export function useStoredFlag(key: string, fallback: boolean) {
  const store = flagStore(key, fallback);
  const value = useSyncExternalStore(store.subscribe, store.get, () => fallback);
  const update = useCallback((next: boolean) => store.set(next), [store]);
  return [value, update] as const;
}
