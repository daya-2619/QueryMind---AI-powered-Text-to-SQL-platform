import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { History, Search, CheckCircle2, XCircle, Clock, Database, ChevronDown, ChevronUp } from 'lucide-react';

interface HistoryLog {
  id: number;
  session_id: string;
  question: string;
  generated_sql: string | null;
  execution_time_ms: number;
  row_count: number;
  success: boolean;
  error_message: string | null;
  chart_type: string | null;
  created_at: string;
}

export const QueryHistory: React.FC = () => {
  const { token } = useAuth();
  const [history, setHistory] = useState<HistoryLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [expandedLogs, setExpandedLogs] = useState<Record<number, boolean>>({});

  const fetchHistory = async (searchVal: string, filterVal: string) => {
    setLoading(true);
    try {
      let url = `/api/history/?limit=50&search=${encodeURIComponent(searchVal)}`;
      if (filterVal === 'success') {
        url += '&success=true';
      } else if (filterVal === 'failure') {
        url += '&success=false';
      }
      console.log("Fetching history from URL:", url);

      const response = await fetch(url, {
        headers: {
          'Authorization': token ? `Bearer ${token}` : ''
        }
      });
      if (!response.ok) {
        throw new Error('Failed to retrieve history logs.');
      }
      const data = await response.json();
      setHistory(data);
    } catch (e: any) {
      console.error("Error fetching history:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Debounce search query triggers
    const delayDebounceFn = setTimeout(() => {
      fetchHistory(search, statusFilter);
    }, 300);

    return () => clearTimeout(delayDebounceFn);
  }, [search, statusFilter]);

  const toggleExpand = (id: number) => {
    setExpandedLogs(prev => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="space-y-6 h-full flex flex-col">
      {/* Title & Filter Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-slate-900 border border-slate-800 rounded-xl">
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-brand-500" />
          <h2 className="text-base font-semibold text-slate-100 font-sans">Query Audit Logs</h2>
        </div>
        
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-lg w-64 focus-within:border-brand-500 transition-all">
            <Search className="w-3.5 h-3.5 text-slate-500" />
            <input 
              type="text" 
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search question or SQL..."
              className="bg-transparent border-none outline-none text-xs text-slate-200 placeholder-slate-500 w-full"
            />
          </div>
          
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-xs text-slate-300 px-3 py-1.5 rounded-lg outline-none cursor-pointer focus:border-brand-500"
          >
            <option value="all">All Statuses</option>
            <option value="success">Success Only</option>
            <option value="failure">Failure Only</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex-1 flex flex-col items-center justify-center space-y-3">
          <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
          <span className="text-xs text-slate-400 font-sans">Loading history logs...</span>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          {history.length === 0 ? (
            <div className="text-center text-slate-500 text-sm py-12">
              No matching query logs found.
            </div>
          ) : (
            history.map(log => (
              <div 
                key={log.id}
                className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow hover:border-slate-750 transition-all"
              >
                {/* Row Header */}
                <div 
                  onClick={() => toggleExpand(log.id)}
                  className="px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-slate-850/30 transition-all"
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0 pr-4">
                    {log.success ? (
                      <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                    )}
                    <span className="text-xs font-medium text-slate-200 truncate font-sans">{log.question}</span>
                  </div>

                  <div className="flex items-center gap-4 text-[10px] text-slate-400 flex-shrink-0 font-mono">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3 text-slate-500" />
                      {log.execution_time_ms.toFixed(1)}ms
                    </span>
                    <span className="flex items-center gap-1">
                      <Database className="w-3 h-3 text-slate-500" />
                      {log.row_count} rows
                    </span>
                    <span className="text-slate-500">
                      {new Date(log.created_at).toLocaleTimeString()}
                    </span>
                    {expandedLogs[log.id] ? <ChevronUp className="w-3.5 h-3.5 text-slate-500" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-500" />}
                  </div>
                </div>

                {/* Expanded Details body */}
                {expandedLogs[log.id] && (
                  <div className="px-5 pb-5 border-t border-slate-850/60 pt-4 space-y-3 bg-slate-950/20">
                    {log.generated_sql && (
                      <div className="space-y-1">
                        <span className="text-[10px] font-semibold text-slate-400 font-sans block">Executed SQL Query:</span>
                        <pre className="p-3.5 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-brand-500 overflow-x-auto">
                          <code>{log.generated_sql}</code>
                        </pre>
                      </div>
                    )}
                    
                    {!log.success && log.error_message && (
                      <div className="space-y-1">
                        <span className="text-[10px] font-semibold text-red-400 font-sans block">Execution Failure Log:</span>
                        <pre className="p-3.5 bg-red-950/10 border border-red-900/40 rounded-lg text-xs font-mono text-red-400 overflow-x-auto">
                          <code>{log.error_message}</code>
                        </pre>
                      </div>
                    )}
                    
                    <div className="flex items-center gap-3 text-[10px] text-slate-500 font-mono">
                      <span>Log ID: {log.id}</span>
                      <span>•</span>
                      <span>Session ID: {log.session_id}</span>
                      {log.chart_type && (
                        <>
                          <span>•</span>
                          <span>Recommends: {log.chart_type.toUpperCase()}</span>
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
