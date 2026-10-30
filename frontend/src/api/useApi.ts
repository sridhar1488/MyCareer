import { useEffect, useState } from 'react';
import { api } from './client';

export function useApi<T>(path: string, revision = 0) {
  const key = `${path}:${revision}`;
  const [state, setState] = useState<{ data: T | null; error: string; loading: boolean; key: string }>({ data: null, error: '', loading: true, key });
  useEffect(() => {
    let active = true;
    api<T>(path).then(data => { if (active) setState({ data, error: '', loading: false, key }); })
      .catch(error => { if (active) setState({ data: null, error: error.message, loading: false, key }); });
    return () => { active = false; };
  }, [path, key]);
  return state.key === key ? state : { data: null, error: '', loading: true };
}
