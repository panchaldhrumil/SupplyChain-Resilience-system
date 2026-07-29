// Custom polling hook — fetches on mount and every `interval` ms
import { useState, useEffect, useCallback } from 'react';

export function usePolling(fetchFn, interval = 60_000, deps = []) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const run = useCallback(async () => {
    try {
      const result = await fetchFn();
      setData(result);
      setLastUpdated(new Date());
      setError(null);
    } catch (e) {
      setError(e.message || 'Fetch error');
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
    const id = setInterval(run, interval);

    // Automatically refetch when the user returns to the tab
    // This allows picking up newly generated data from the background GitHub Actions pipeline
    const handleFocus = () => {
      if (document.visibilityState === 'visible') {
        run();
      }
    };

    document.addEventListener('visibilitychange', handleFocus);
    window.addEventListener('focus', handleFocus);

    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', handleFocus);
      window.removeEventListener('focus', handleFocus);
    };
  }, [run, interval]);

  return { data, loading, error, lastUpdated, refresh: run };
}
