import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Sparkles, BarChart4, AlertTriangle, RefreshCw, Layers } from 'lucide-react';
import { 
  BarChart, Bar, LineChart, Line, PieChart, Pie, 
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell 
} from 'recharts';

interface WidgetConfig {
  title: string;
  type: 'metric' | 'chart';
  chart_type?: 'bar' | 'line' | 'pie' | 'area';
  query: string;
  x_axis?: string;
  y_axes?: string[];
  width: number; // grid column width (1-12)
}

interface DashboardLayout {
  dashboard_title: string;
  widgets: WidgetConfig[];
}

const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

// Simple widget container that executes its own SQL query dynamically
const DashboardWidget: React.FC<{ widget: WidgetConfig; token: string | null }> = ({ widget, token }) => {
  const [data, setData] = useState<any[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    runWidgetQuery();
  }, [widget.query, token]);

  const runWidgetQuery = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/query/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({ sql: widget.query })
      });
      const resData = await response.json();
      if (response.ok && resData.success) {
        setData(resData.rows);
        setColumns(resData.columns);
      } else {
        setError(resData.error || 'Failed to fetch widget data.');
      }
    } catch (e: any) {
      setError(e.message || 'Network error.');
    } finally {
      setLoading(false);
    }
  };

  const renderWidgetContent = () => {
    if (loading) {
      return (
        <div className="h-40 flex items-center justify-center">
          <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      );
    }

    if (error) {
      return (
        <div className="h-40 flex flex-col items-center justify-center p-4 text-center text-[10px] text-red-400">
          <AlertTriangle className="w-6 h-6 text-red-500 mb-2" />
          <p>{error}</p>
        </div>
      );
    }

    if (data.length === 0) {
      return (
        <div className="h-40 flex items-center justify-center text-slate-500 text-xs">
          <span>No records found.</span>
        </div>
      );
    }

    // 1. Metric widget rendering
    if (widget.type === 'metric') {
      const firstRow = data[0];
      const metricKey = Object.keys(firstRow)[0];
      const metricValue = firstRow[metricKey];
      const formattedVal = typeof metricValue === 'number' 
        ? (metricValue % 1 === 0 ? metricValue.toLocaleString() : `$${metricValue.toFixed(2)}`)
        : String(metricValue);

      return (
        <div className="h-32 flex flex-col justify-center items-center py-6">
          <div className="text-3xl font-extrabold text-white font-mono tracking-tight">{formattedVal}</div>
          <div className="text-[10px] text-slate-500 font-sans mt-1 uppercase font-bold tracking-wider">{metricKey.replace('_', ' ')}</div>
        </div>
      );
    }

    // 2. Chart widget rendering
    const xKey = widget.x_axis || columns[0];
    const yKeys = widget.y_axes || [columns[1]];

    if (widget.chart_type === 'line') {
      return (
        <div className="h-60 pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey={xKey} stroke="#64748b" fontSize={10} />
              <YAxis stroke="#64748b" fontSize={10} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
              {yKeys.map((key, idx) => (
                <Line key={key} type="monotone" dataKey={key} stroke={COLORS[idx % COLORS.length]} strokeWidth={2} activeDot={{ r: 4 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (widget.chart_type === 'pie') {
      return (
        <div className="h-60 pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                labelLine={false}
                outerRadius={65}
                dataKey={yKeys[0]}
                nameKey={xKey}
              >
                {data.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      );
    }

    // Default: Bar Chart
    return (
      <div className="h-60 pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey={xKey} stroke="#64748b" fontSize={10} />
            <YAxis stroke="#64748b" fontSize={10} />
            <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
            {yKeys.map((key, idx) => (
              <Bar key={key} dataKey={key} fill={COLORS[idx % COLORS.length]} radius={[4, 4, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  };

  return (
    <div className={`bg-slate-950 border border-slate-805 rounded-xl p-5 flex flex-col justify-between overflow-hidden shadow-lg relative min-h-[160px] col-span-12 md:col-span-${widget.width}`}>
      <div className="absolute top-0 left-0 w-full h-[3px] bg-gradient-to-r from-brand-500 to-purple-600"></div>
      <div className="flex items-center justify-between border-b border-slate-900 pb-2 mb-3">
        <span className="text-xs font-bold text-slate-200 truncate pr-4">{widget.title}</span>
        <button 
          onClick={runWidgetQuery}
          className="text-slate-500 hover:text-white transition-colors"
          title="Refresh widget metrics"
        >
          <RefreshCw className="w-3 h-3" />
        </button>
      </div>
      <div className="flex-1">
        {renderWidgetContent()}
      </div>
    </div>
  );
};

export const AIDashboardGen: React.FC = () => {
  const { token } = useAuth();
  const [prompt, setPrompt] = useState('');
  const [loadingLayout, setLoadingLayout] = useState(false);
  const [dashboard, setDashboard] = useState<DashboardLayout | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setLoadingLayout(true);
    setDashboard(null);
    setError(null);

    try {
      const response = await fetch('/api/analyst/ai-dashboard', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({ prompt })
      });

      const data = await response.json();
      if (response.ok && data.success) {
        setDashboard({
          dashboard_title: data.dashboard_title,
          widgets: data.widgets
        });
      } else {
        setError(data.detail || 'Layout recommendation generation failed.');
      }
    } catch (e: any) {
      setError(e.message || 'API Server connection issue.');
    } finally {
      setLoadingLayout(false);
    }
  };

  return (
    <div className="flex flex-col h-full space-y-6 overflow-hidden">
      
      {/* Search/Generator Prompter */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4 shadow-xl">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-brand-500 animate-pulse-slow" />
          <h2 className="font-semibold text-slate-100 font-sans">AI Dashboard Layout Generator</h2>
        </div>
        <p className="text-xs text-slate-400 font-sans">
          Describe the analytical views or business KPIs you want to monitor, and the AI agent will suggest and wire up custom widget metrics and visualization charts from your database schema.
        </p>

        <form onSubmit={handleGenerate} className="flex gap-2">
          <input
            type="text"
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            disabled={loadingLayout}
            placeholder="e.g. Sales KPI revenue and monthly transaction trends, Customer distribution..."
            className="flex-1 bg-slate-950 border border-slate-800 focus:border-brand-500 rounded-lg px-4 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500/20 transition-all font-sans"
          />
          <button
            type="submit"
            disabled={loadingLayout || !prompt.trim()}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-semibold text-xs transition-all shadow-md font-sans"
          >
            {loadingLayout ? (
              <div className="w-3.5 h-3.5 border border-white border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <Sparkles className="w-3.5 h-3.5" />
            )}
            Generate
          </button>
        </form>
      </div>

      {/* Main layout widgets display */}
      <div className="flex-1 overflow-y-auto min-h-0 pr-1">
        {error && (
          <div className="p-4 rounded-xl bg-red-950/20 border border-red-800/40 text-xs text-red-400 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}

        {dashboard ? (
          <div className="space-y-6">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
              <Layers className="w-4 h-4 text-brand-500" />
              <h3 className="text-sm font-bold text-slate-200 font-sans tracking-wide">{dashboard.dashboard_title}</h3>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6 pb-6">
              {dashboard.widgets.map((widget, idx) => (
                <DashboardWidget key={idx} widget={widget} token={token} />
              ))}
            </div>
          </div>
        ) : (
          !loadingLayout && (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-3">
              <BarChart4 className="w-12 h-12 text-slate-800 animate-pulse-slow" />
              <h3 className="font-semibold text-slate-400 text-sm">Dashboard is Empty</h3>
              <p className="text-xs text-slate-500 max-w-sm">
                Type an analytical prompt above to automatically model and build dynamic SQL widgets.
              </p>
            </div>
          )
        )}
      </div>

    </div>
  );
};
