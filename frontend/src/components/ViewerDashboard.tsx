import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { AgGridReact } from 'ag-grid-react';
import { 
  BarChart4, Download, RefreshCw, AlertTriangle, Calendar, Clock, 
  Filter, Database, FileText, CheckCircle
} from 'lucide-react';
import { 
  BarChart, Bar, LineChart, Line, 
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';

import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

interface SavedQuery {
  id: number;
  title: string;
  question: string;
  sql_query: string;
  description?: string;
  created_at: string;
}

interface ScheduledReport {
  id: number;
  report_name: string;
  query_id: number;
  cron_expression: string;
  recipient_email: string;
  is_active: boolean;
}

const gridIcons = {
  first: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4"><path d="m11 17-5-5 5-5"/><path d="m18 17-5-5 5-5"/></svg>`,
  paginationFirst: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4"><path d="m11 17-5-5 5-5"/><path d="m18 17-5-5 5-5"/></svg>`,
  previous: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4"><path d="m15 18-6-6 6-6"/></svg>`,
  paginationPrevious: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4"><path d="m15 18-6-6 6-6"/></svg>`,
  next: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4"><path d="m9 18 6-6-6-6"/></svg>`,
  paginationNext: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4"><path d="m9 18 6-6-6-6"/></svg>`,
  last: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4"><path d="m13 17 5-5-5-5"/><path d="m6 17 5-5-5-5"/></svg>`,
  paginationLast: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4"><path d="m13 17 5-5-5-5"/><path d="m6 17 5-5-5-5"/></svg>`,
  sortAscending: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-3.5 h-3.5 text-emerald-500"><path d="m18 15-6-6-6 6"/></svg>`,
  sortDescending: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-3.5 h-3.5 text-emerald-500"><path d="m6 9 6 6 6-6"/></svg>`
};

const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

export const ViewerDashboard: React.FC = () => {
  const { token } = useAuth();
  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>([]);
  const [scheduledReports, setScheduledReports] = useState<ScheduledReport[]>([]);
  const [selectedQuery, setSelectedQuery] = useState<SavedQuery | null>(null);
  
  // Execution result state
  const [loading, setLoading] = useState(false);
  const [execResult, setExecResult] = useState<{
    columns: string[];
    rows: any[];
    success: boolean;
    error: string | null;
  } | null>(null);

  // Global search / filter text state
  const [filterText, setFilterText] = useState('');
  const [loadingReports, setLoadingReports] = useState(false);
  const [loadingQueries, setLoadingQueries] = useState(false);

  useEffect(() => {
    fetchQueriesAndSchedules();
  }, [token]);

  const fetchQueriesAndSchedules = async () => {
    if (!token) return;
    
    setLoadingQueries(true);
    setLoadingReports(true);
    
    try {
      // 1. Fetch saved queries
      const qRes = await fetch('/api/saved/', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (qRes.ok) {
        const qData = await qRes.json();
        setSavedQueries(qData);
        if (qData.length > 0) {
          setSelectedQuery(qData[0]);
          executeSavedQuery(qData[0].id);
        }
      }
    } catch (err) {
      console.error("Failed to load dashboard queries", err);
    } finally {
      setLoadingQueries(false);
    }

    try {
      // 2. Fetch scheduled reports
      const rRes = await fetch('/api/manager/scheduled-reports', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (rRes.ok) {
        const rData = await rRes.json();
        setScheduledReports(rData);
      }
    } catch (err) {
      console.error("Failed to load scheduled reports", err);
    } finally {
      setLoadingReports(false);
    }
  };

  const executeSavedQuery = async (queryId: number) => {
    setLoading(true);
    setExecResult(null);
    try {
      const response = await fetch(`/api/saved/${queryId}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setExecResult(data);
      } else {
        const err = await response.json();
        setExecResult({
          columns: [],
          rows: [],
          success: false,
          error: err.detail || 'Execution failed.'
        });
      }
    } catch (e: any) {
      setExecResult({
        columns: [],
        rows: [],
        success: false,
        error: e.message || 'Connection failed.'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleQuerySelect = (q: SavedQuery) => {
    setSelectedQuery(q);
    executeSavedQuery(q.id);
  };

  // Export filtered rows to CSV
  const handleExportCSV = () => {
    if (!execResult || !execResult.rows || execResult.rows.length === 0) return;
    const columns = execResult.columns;
    
    // Apply filters matching filterText
    const filteredRows = getFilteredRows();
    
    const csvRows = [];
    csvRows.push(columns.join(','));
    
    for (const row of filteredRows) {
      const values = columns.map(col => {
        const val = row[col];
        const stringVal = val === null || val === undefined ? '' : String(val);
        const escaped = stringVal.replace(/"/g, '""');
        return `"${escaped}"`;
      });
      csvRows.push(values.join(','));
    }

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `${selectedQuery?.title.replace(/\s+/g, '_') || 'report'}_export.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const getFilteredRows = () => {
    if (!execResult?.rows) return [];
    if (!filterText.trim()) return execResult.rows;
    const lowerFilter = filterText.toLowerCase();
    return execResult.rows.filter(row => {
      return Object.values(row).some(val => 
        String(val || '').toLowerCase().includes(lowerFilter)
      );
    });
  };

  // Determine chart types locally based on column names (heuristic)
  const renderChartRecommendation = () => {
    if (!execResult?.rows || execResult.rows.length === 0) return null;
    const data = getFilteredRows();
    const columns = execResult.columns;

    // Standard heuristic: look for a label column (string) and a numeric metric column
    let labelCol: string | null = null;
    let numericCols: string[] = [];

    columns.forEach(col => {
      const sampleVal = execResult.rows[0][col];
      if (typeof sampleVal === 'number') {
        numericCols.push(col);
      } else if (typeof sampleVal === 'string' && !labelCol && !col.toLowerCase().includes('date') && !col.toLowerCase().includes('id')) {
        labelCol = col;
      }
    });

    // Fallbacks
    if (!labelCol && columns.length > 0) labelCol = columns[0];
    if (numericCols.length === 0 && columns.length > 1) {
      // try to use second column if first is label
      numericCols.push(columns[1]);
    }

    if (!labelCol || numericCols.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center h-64 text-slate-500">
          <AlertTriangle className="w-8 h-8 text-slate-600 mb-2" />
          <p className="text-xs">No suitable fields found for automatic charting.</p>
        </div>
      );
    }

    // Heuristically pick bar chart for categories, line for times
    const isTimeline = columns.some(c => c.toLowerCase().includes('date') || c.toLowerCase().includes('month') || c.toLowerCase().includes('year'));
    const chartType = isTimeline ? 'line' : 'bar';

    if (chartType === 'line') {
      // Find date column
      const dateCol = columns.find(c => c.toLowerCase().includes('date') || c.toLowerCase().includes('month') || c.toLowerCase().includes('year')) || labelCol;
      return (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey={dateCol} stroke="#64748b" fontSize={10} />
            <YAxis stroke="#64748b" fontSize={10} />
            <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
            <Legend wrapperStyle={{ fontSize: '10px' }} />
            {numericCols.map((key, idx) => (
              <Line key={key} type="monotone" dataKey={key} stroke={COLORS[idx % COLORS.length]} strokeWidth={2} activeDot={{ r: 5 }} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      );
    } else {
      return (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey={labelCol} stroke="#64748b" fontSize={10} />
            <YAxis stroke="#64748b" fontSize={10} />
            <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
            <Legend wrapperStyle={{ fontSize: '10px' }} />
            {numericCols.map((key, idx) => (
              <Bar key={key} dataKey={key} fill={COLORS[idx % COLORS.length]} radius={[4, 4, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      );
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 h-full overflow-hidden">
      
      {/* Sidebar - Saved Report Templates */}
      <div className="lg:col-span-1 bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col space-y-4 overflow-hidden">
        <div className="flex items-center justify-between pb-2 border-b border-slate-800">
          <h3 className="font-semibold text-slate-200 text-xs uppercase tracking-wider font-sans">Reports List</h3>
          <button 
            onClick={fetchQueriesAndSchedules}
            className="p-1 hover:bg-slate-800 text-slate-400 hover:text-white rounded transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
        
        {loadingQueries ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            {savedQueries.length === 0 ? (
              <p className="text-xs text-slate-500 italic p-4 text-center">No reports available.</p>
            ) : (
              savedQueries.map(q => {
                const isSelected = selectedQuery?.id === q.id;
                return (
                  <button
                    key={q.id}
                    onClick={() => handleQuerySelect(q)}
                    className={`w-full text-left p-3 rounded-lg border transition-all text-xs font-sans block ${
                      isSelected 
                        ? 'bg-brand-950/40 border-brand-500/50 text-brand-400' 
                        : 'bg-slate-950/40 border-slate-850 hover:bg-slate-850 hover:text-white text-slate-300'
                    }`}
                  >
                    <div className="font-semibold truncate">{q.title}</div>
                    <p className="text-[10px] text-slate-500 truncate mt-1">{q.question}</p>
                  </button>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* Main Workspace Area */}
      <div className="lg:col-span-3 flex flex-col space-y-6 overflow-hidden h-full">
        {selectedQuery ? (
          <div className="flex-1 flex flex-col space-y-6 overflow-hidden">
            {/* Header info */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 text-[10px] border border-slate-700 font-mono">
                  <Database className="w-3 h-3 text-brand-500" /> Pre-compiled KPI Report
                </div>
                <h2 className="text-lg font-bold text-white font-sans">{selectedQuery.title}</h2>
                <p className="text-xs text-slate-400 font-sans">{selectedQuery.description || 'No description provided.'}</p>
              </div>

              {/* Filters & Export */}
              <div className="flex items-center gap-2">
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 pl-2.5 flex items-center text-slate-500">
                    <Filter className="w-3.5 h-3.5" />
                  </span>
                  <input
                    type="text"
                    value={filterText}
                    onChange={e => setFilterText(e.target.value)}
                    placeholder="Filter table rows..."
                    className="bg-slate-950 border border-slate-800 focus:border-brand-500 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-600 focus:outline-none w-44 transition-all"
                  />
                </div>

                <button
                  disabled={loading || !execResult?.success || !execResult?.rows?.length}
                  onClick={handleExportCSV}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-40 disabled:hover:bg-brand-600 text-white font-medium text-xs transition-all shadow-md"
                >
                  <Download className="w-3.5 h-3.5" />
                  Export CSV
                </button>
              </div>
            </div>

            {/* Results Grid / Chart Layout */}
            <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-6 overflow-hidden">
              
              {/* Visualized Chart Component */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between overflow-hidden">
                <div className="flex items-center gap-1.5 border-b border-slate-800 pb-3 mb-4">
                  <BarChart4 className="w-4 h-4 text-brand-500" />
                  <h4 className="font-semibold text-slate-200 text-xs uppercase tracking-wider font-sans">Data Trend Visualization</h4>
                </div>
                {loading ? (
                  <div className="flex-1 flex items-center justify-center">
                    <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
                  </div>
                ) : execResult?.success ? (
                  <div className="flex-1 flex items-center justify-center">
                    {renderChartRecommendation()}
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs">
                    <AlertTriangle className="w-8 h-8 text-red-500 mb-2" />
                    <p>{execResult?.error || 'Load query data to view chart.'}</p>
                  </div>
                )}
              </div>

              {/* Data Table Component */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col overflow-hidden">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                  <div className="flex items-center gap-1.5">
                    <FileText className="w-4 h-4 text-brand-500" />
                    <h4 className="font-semibold text-slate-200 text-xs uppercase tracking-wider font-sans">Report Data Rows</h4>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500">
                    Row Count: {getFilteredRows().length}
                  </span>
                </div>

                {loading ? (
                  <div className="flex-1 flex items-center justify-center">
                    <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
                  </div>
                ) : execResult?.success ? (
                  <div className="ag-theme-alpine-dark w-full h-full min-h-[300px]">
                    <AgGridReact
                      columnDefs={execResult.columns.map(col => ({
                        field: col,
                        headerName: col.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
                        filter: true,
                        sortable: true,
                        resizable: true,
                        minWidth: col.toLowerCase().includes('name') || col.toLowerCase().includes('text') || col.toLowerCase().includes('desc') || col.toLowerCase().includes('product') || col.toLowerCase().includes('email') || col.toLowerCase().includes('title') || col.toLowerCase().includes('sql') ? 180 : 120
                      }))}
                      defaultColDef={{
                        flex: 1,
                        minWidth: 120,
                        resizable: true,
                        sortable: true,
                        filter: true
                      }}
                      rowData={getFilteredRows()}
                      pagination={true}
                      paginationPageSize={10}
                      icons={gridIcons}
                    />
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs">
                    <AlertTriangle className="w-8 h-8 text-red-500/80 mb-2" />
                    <p>{execResult?.error || 'No report data loaded.'}</p>
                  </div>
                )}
              </div>

            </div>
          </div>
        ) : (
          <div className="flex-1 bg-slate-900 border border-slate-800 rounded-xl flex flex-col items-center justify-center text-center p-8 space-y-3">
            <BarChart4 className="w-12 h-12 text-slate-700 animate-pulse" />
            <h3 className="font-semibold text-slate-300">Welcome to Insight Console</h3>
            <p className="text-xs text-slate-500 max-w-sm">
              Please select a pre-saved report from the left sidebar to render visual graphs and download audit results.
            </p>
          </div>
        )}

        {/* Scheduled Reports List (Bottom section) */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-1.5 border-b border-slate-800 pb-3">
            <Calendar className="w-4 h-4 text-brand-500" />
            <h4 className="font-semibold text-slate-200 text-xs uppercase tracking-wider font-sans">Active Report Delivery Schedules</h4>
          </div>

          {loadingReports ? (
            <div className="flex items-center justify-center py-4">
              <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
          ) : scheduledReports.length === 0 ? (
            <p className="text-xs text-slate-500 italic py-2">No email delivery schedules configured.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {scheduledReports.map(sched => (
                <div key={sched.id} className="bg-slate-950 border border-slate-805 p-3 rounded-lg space-y-2 relative">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-200 font-sans truncate pr-8">{sched.report_name}</span>
                    <span className="flex h-2 w-2 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
                    <Clock className="w-3.5 h-3.5 text-slate-500" />
                    <span>Cron: <code className="bg-slate-900 px-1 py-0.5 rounded text-brand-400">{sched.cron_expression}</code></span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
                    <CheckCircle className="w-3.5 h-3.5 text-slate-500" />
                    <span className="truncate">Recipient: <span className="font-semibold text-slate-300">{sched.recipient_email}</span></span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>

    </div>
  );
};
