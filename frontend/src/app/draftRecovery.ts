import { useEffect, useLayoutEffect, useState } from 'react';

let current: (() => {key: string; value: unknown} | undefined) | undefined;
let retained: {userId: string; key: string; value: unknown} | undefined;

export function retainDraftOnExpiry(userId: string) {
  const snapshot = current?.();
  if (snapshot) retained = {userId, ...snapshot};
  return Boolean(snapshot);
}

export function clearDraftForOtherUsers(userId?: string) {
  if (retained?.userId !== userId) retained = undefined;
}

// The copy stays in tab memory and is available only after the owner signs in again.
export function useRecoveredDraft<T>(key: string, userId: string) {
  const [recovered] = useState(() =>
    retained?.key === key && retained.userId === userId ? retained.value as T : undefined);
  useEffect(() => {
    if (recovered && retained?.key === key && retained.userId === userId) retained = undefined;
  }, [key, recovered, userId]);
  return recovered;
}

export function useDraftSnapshot<T>(key: string, value: T | undefined) {
  useLayoutEffect(() => {
    const getSnapshot = () => value ? {key, value} : undefined;
    current = getSnapshot;
    return () => { if (current === getSnapshot) current = undefined; };
  }, [key, value]);
}
