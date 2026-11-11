import { describe, expect, it } from 'vitest';

import { readCode, type KeyValueStore, saveCode, forgetCode } from './storage';

function fakeStore(): KeyValueStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
  };
}

const blockedStore: KeyValueStore = {
  getItem: () => {
    throw new Error('SecurityError');
  },
  setItem: () => {
    throw new Error('SecurityError');
  },
  removeItem: () => {
    throw new Error('SecurityError');
  },
};

describe('lưu trữ trên máy', () => {
  it('lưu, đọc, quên mã', () => {
    const k = fakeStore();
    expect(readCode(k)).toBeNull();
    saveCode('abc', k);
    expect(readCode(k)).toBe('abc');
    forgetCode(k);
    expect(readCode(k)).toBeNull();
  });

  it('trình duyệt chặn lưu trữ thì không ném lỗi', () => {
    expect(readCode(blockedStore)).toBeNull();
    expect(() => saveCode('x', blockedStore)).not.toThrow();
    expect(() => forgetCode(blockedStore)).not.toThrow();
    expect(readCode()).toBeNull();
  });
});
