import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api';
import { TraceDetail } from '../types';
import { ArrowLeft, ShieldAlert, CheckCircle2, Terminal } from 'lucide-react';

export default function TraceView() {
  const { traceId } = useParams<{ traceId: string }>();
  const [trace, setTrace] = useState<TraceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!traceId) return;
    api.getTrace(traceId)
      .then(setTrace)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [traceId]);

  if (loading) return <div className="text-gray-500 animate-pulse">Loading trace details...</div>;
  if (error) return <div className="text-red-500 font-medium">Error: {error}</div>;
  if (!trace) return <div className="text-gray-500">Trace not found.</div>;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <Link to="/" className="inline-flex items-center text-sm text-gray-500 hover:text-gray-900 mb-4 transition-colors">
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Dashboard
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          Trace <span className="font-mono text-lg text-gray-500 font-normal">{trace.trace_id}</span>
        </h1>
        <div className="mt-2 flex items-center gap-4 text-sm text-gray-600">
          <span>App: <strong>{trace.application_name}</strong></span>
          <span>Model: <strong>{trace.model_name}</strong></span>
          <span>Latency: <strong>{trace.latency_ms.toFixed(0)}ms</strong></span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Messages Chat View */}
        <div className="md:col-span-2 space-y-4">
          <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">Interaction</h2>
          <div className="space-y-4">
            {trace.messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-lg p-4 ${
                  msg.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-white border border-gray-200 text-gray-800'
                }`}>
                  <div className={`text-xs font-medium mb-1 ${msg.role === 'user' ? 'text-indigo-200' : 'text-gray-500'}`}>
                    {msg.role.toUpperCase()}
                  </div>
                  <pre className="whitespace-pre-wrap font-sans text-sm">{msg.content}</pre>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Evaluation Scores Sidebar */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">Evaluation</h2>
          
          <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm space-y-4">
            <div>
              <div className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-1">Safety</div>
              {trace.safety_flag === true ? (
                <div className="flex items-center text-red-600 gap-1.5"><ShieldAlert className="w-5 h-5"/> Violation Detected</div>
              ) : trace.safety_flag === false ? (
                <div className="flex items-center text-green-600 gap-1.5"><CheckCircle2 className="w-5 h-5"/> Safe</div>
              ) : (
                <div className="text-gray-400">Pending Evaluation</div>
              )}
            </div>

            <div>
              <div className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-1">Scores</div>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-gray-700">Groundedness</span>
                  <span className="font-semibold text-gray-900">{trace.groundedness_score ?? '-'}/5</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-700">Relevance</span>
                  <span className="font-semibold text-gray-900">{trace.relevance_score ?? '-'}/5</span>
                </div>
              </div>
            </div>

            {trace.judge_rationale && (
              <div>
                <div className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-1">LLM Judge Rationale</div>
                <p className="text-sm text-gray-700 bg-gray-50 p-3 rounded italic border border-gray-100">
                  "{trace.judge_rationale}"
                </p>
              </div>
            )}
          </div>

          <div className="bg-gray-900 p-5 rounded-lg shadow-sm text-gray-300">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
              <Terminal className="w-4 h-4" /> Custom Attributes
            </div>
            <pre className="text-xs font-mono overflow-x-auto">
              {JSON.stringify(trace.attributes, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
