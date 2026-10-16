import { MetricSummary, TraceDetail, TraceSummary } from './types';

const API_BASE = '/api/v1';

export const api = {
  getMetrics: async (hours: number = 24): Promise<MetricSummary> => {
    const res = await fetch(`${API_BASE}/metrics?hours=${hours}`);
    if (!res.ok) throw new Error('Failed to fetch metrics');
    return res.json();
  },

  listTraces: async (limit: number = 50, offset: number = 0): Promise<TraceSummary[]> => {
    const res = await fetch(`${API_BASE}/traces?limit=${limit}&offset=${offset}`);
    if (!res.ok) throw new Error('Failed to fetch traces');
    return res.json();
  },

  getTrace: async (traceId: string): Promise<TraceDetail> => {
    const res = await fetch(`${API_BASE}/traces/${traceId}`);
    if (!res.ok) throw new Error('Failed to fetch trace detail');
    return res.json();
  },
};
