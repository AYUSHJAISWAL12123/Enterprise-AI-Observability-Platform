import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { MetricSummary, TraceSummary } from '../types';
import { AlertCircle, CheckCircle2, ShieldAlert } from 'lucide-react';

export default function Dashboard() {
  const [metrics, setMetrics] = useState<MetricSummary | null>(null);
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getMetrics(), api.listTraces()])
      .then(([m, t]) => {
        setMetrics(m);
        setTraces(t);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-500 animate-pulse">Loading dashboard...</div>;
  if (error) return <div className="text-red-500 font-medium">Error: {error}</div>;
  if (!metrics) return null;

  return (
    <div className="space-y-8">
      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <div className="text-sm text-gray-500 font-medium uppercase">Total Events (24h)</div>
          <div className="mt-2 text-3xl font-bold text-gray-900">{metrics.total_events}</div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <div className="text-sm text-gray-500 font-medium uppercase">Avg Groundedness</div>
          <div className="mt-2 text-3xl font-bold text-indigo-600">
            {metrics.avg_groundedness.toFixed(1)} <span className="text-lg text-gray-400">/ 5</span>
          </div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <div className="text-sm text-gray-500 font-medium uppercase">Avg Relevance</div>
          <div className="mt-2 text-3xl font-bold text-blue-600">
            {metrics.avg_relevance.toFixed(1)} <span className="text-lg text-gray-400">/ 5</span>
          </div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-red-100 bg-red-50/30">
          <div className="text-sm text-red-600 font-medium uppercase flex items-center gap-1">
            <ShieldAlert className="w-4 h-4" /> Safety Violations
          </div>
          <div className="mt-2 text-3xl font-bold text-red-700">{metrics.safety_violations}</div>
        </div>
      </div>

      {/* Traces Table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <h2 className="text-lg font-semibold text-gray-800">Recent Traces</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-white text-gray-500 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 font-medium">Trace ID</th>
                <th className="px-6 py-3 font-medium">Application</th>
                <th className="px-6 py-3 font-medium">Groundedness</th>
                <th className="px-6 py-3 font-medium">Safety</th>
                <th className="px-6 py-3 font-medium">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {traces.map((t) => (
                <tr key={t.trace_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-3">
                    <Link to={`/traces/${t.trace_id}`} className="text-indigo-600 hover:underline font-mono">
                      {t.trace_id.substring(0, 8)}...
                    </Link>
                  </td>
                  <td className="px-6 py-3 text-gray-700">{t.application_name}</td>
                  <td className="px-6 py-3">
                    {t.groundedness_score ? (
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${t.groundedness_score < 4 ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}`}>
                        {t.groundedness_score} / 5
                      </span>
                    ) : (
                      <span className="text-gray-400">Pending</span>
                    )}
                  </td>
                  <td className="px-6 py-3">
                    {t.safety_flag === true ? (
                      <AlertCircle className="w-5 h-5 text-red-500" />
                    ) : t.safety_flag === false ? (
                      <CheckCircle2 className="w-5 h-5 text-green-500" />
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-6 py-3 text-gray-500">
                    {new Date(t.timestamp).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
              {traces.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                    No traces found. Ensure the ingestion gateway and evaluator worker are running.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
