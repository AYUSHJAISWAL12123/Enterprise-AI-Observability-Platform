export interface MetricSummary {
  total_events: number;
  evaluated_events: number;
  safety_violations: number;
  avg_groundedness: number;
  avg_relevance: number;
  avg_latency_ms: number;
}

export interface TraceSummary {
  trace_id: string;
  event_id: string;
  application_name: string;
  model_name: string;
  latency_ms: number;
  groundedness_score: number | null;
  relevance_score: number | null;
  safety_flag: boolean | null;
  embedding_distance: number | null;
  timestamp: string;
}

export interface TraceDetail extends TraceSummary {
  messages: Array<{ role: string; content: string }>;
  judge_rationale: string | null;
  attributes: Record<string, string>;
}
