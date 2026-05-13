import { useEffect, useState } from "react";

export function useAsyncData<T>(loader: () => Promise<T>, initial: T, dependencies: unknown[] = []) {
  const [data, setData] = useState<T>(initial);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    loader()
      .then((result) => {
        if (active) {
          setData(result);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "请求失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [version, ...dependencies]);

  return { data, error, loading, reload: () => setVersion((current) => current + 1) };
}
