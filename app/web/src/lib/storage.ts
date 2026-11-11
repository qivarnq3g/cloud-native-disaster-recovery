export interface KeyValueStore {
  getItem(k: string): string | null;
  setItem(k: string, v: string): void;
  removeItem(k: string): void;
}

const CODE_KEY = 'secret-code';

function openStore(): KeyValueStore | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function safely<T>(fn: () => T, fallback: T): T {
  try {
    return fn();
  } catch {
    return fallback;
  }
}

export const readCode = (store: KeyValueStore | null = openStore()): string | null => safely(() => store?.getItem(CODE_KEY) ?? null, null);
export const saveCode = (code: string, store: KeyValueStore | null = openStore()): void => safely(() => store?.setItem(CODE_KEY, code), undefined);
export const forgetCode = (store: KeyValueStore | null = openStore()): void => safely(() => store?.removeItem(CODE_KEY), undefined);
