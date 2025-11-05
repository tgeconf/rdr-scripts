import { useCallback, useEffect, useMemo, useState } from 'react';
import { EnrichedClusteringData, RawClusterResponse } from '../types';
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

const fetchJSON = async <T>(url: string, signal: AbortSignal): Promise<T> => {
  const response = await fetch(url, { signal });
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
      const result = await fetchJSON<{ dates: string[] }>('/api/dates', signal);
      setAvailableDates(result.dates);
      if (!selectedDate && result.dates.length > 0) {
        setSelectedDate(result.dates[0]);
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
        const result = await fetchJSON<RawClusterResponse>(`/api/clusters?date=${date}`, signal);
        setData(transformClusteringPayload(result.date, result.payload));
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
