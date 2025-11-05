import { useCallback, useEffect, useMemo, useState } from 'react';
import { EnrichedClusteringData, RawClusteringPayload } from '../types';
import { transformClusteringPayload } from '../utils/dataTransform';

type APIState = {
  availableDates: string[];
  selectedDate: string | null;
  data: EnrichedClusteringData | null;
  loading: boolean;
  error: string | null;
  selectDate: (date: string) => void;
  refresh: () => void;
};

const DATA_ROOT = `${import.meta.env.BASE_URL}data/`;

const buildDataUrl = (relativePath: string) => `${DATA_ROOT}${relativePath}`;

const fetchJSON = async <T>(url: string, signal: AbortSignal): Promise<T> => {
  const response = await fetch(url, { signal, cache: 'no-cache' });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
};

export const useClusteringData = (): APIState => {
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [data, setData] = useState<EnrichedClusteringData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [dataRefreshToken, setDataRefreshToken] = useState(0);

  const loadDates = useCallback(async (signal: AbortSignal) => {
    try {
      const result = await fetchJSON<{ dates: string[] }>(buildDataUrl('index.json'), signal);
      const sorted = result.dates.slice().sort((a, b) => b.localeCompare(a));
      setAvailableDates(sorted);
      if (!selectedDate && sorted.length > 0) {
        setSelectedDate(sorted[0]);
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError((err as Error).message);
      }
    }
  }, [selectedDate]);

  const loadData = useCallback(
    async (signal: AbortSignal, date: string) => {
      setLoading(true);
      setError(null);
      setData(null);

      try {
        const payload = await fetchJSON<RawClusteringPayload>(
          buildDataUrl(`${date}/arxiv_clustering_results.json`),
          signal
        );
        setData(transformClusteringPayload(date, payload));
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          setError((err as Error).message);
        }
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    const controller = new AbortController();
    loadDates(controller.signal);
    return () => controller.abort();
  }, [loadDates, refreshToken]);

  useEffect(() => {
    if (!selectedDate) {
      return;
    }

    const controller = new AbortController();
    loadData(controller.signal, selectedDate).catch(() => {});
    return () => controller.abort();
  }, [selectedDate, loadData, dataRefreshToken]);

  const selectDate = useCallback((date: string) => {
    setSelectedDate(date);
  }, []);

  const refresh = useCallback(() => {
    setRefreshToken((value) => value + 1);
    setDataRefreshToken((value) => value + 1);
  }, []);

  return useMemo(
    () => ({
      availableDates,
      selectedDate,
      data,
      loading,
      error,
      selectDate,
      refresh
    }),
    [availableDates, selectedDate, data, loading, error, selectDate, refresh]
  );
};
