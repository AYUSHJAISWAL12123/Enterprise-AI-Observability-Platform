import { Routes, Route, Link } from 'react-router-dom';
import { Activity } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import TraceView from './pages/TraceView';

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-indigo-600 text-white shadow">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center gap-3">
          <Activity className="w-6 h-6" />
          <Link to="/" className="text-xl font-bold tracking-tight hover:opacity-90">
            AI Observability
          </Link>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/traces/:traceId" element={<TraceView />} />
        </Routes>
      </main>
    </div>
  );
}
