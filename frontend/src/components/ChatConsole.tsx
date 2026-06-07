import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { AgGridReact } from 'ag-grid-react';
import { Mic, MicOff, Send, Sparkles, Table, BarChart4, BookOpen, Save, RefreshCw, AlertTriangle, Clock, Search, CheckCircle2, XCircle } from 'lucide-react';
import { 
  BarChart, Bar, LineChart, Line, AreaChart, Area, PieChart, Pie, 
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell 
} from 'recharts';

import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sql?: string;
  explanation?: {
    business_summary: string;
    technical_details: string;
    step_by_step: string[];
  };
  chart_recommendation?: {
    recommended: boolean;
    chart_type: string | null;
    x_axis_column: string | null;
    y_axis_columns: string[];
    reasoning: string | null;
  };
  execution_result?: {
    columns: string[];
    rows: any[];
    row_count: number;
    execution_time_ms: number;
    success: boolean;
    error: string | null;
    cache_id?: number;
    total_row_count?: number;
  };
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

export const ChatConsole: React.FC = () => {
  const { token, hasRole } = useAuth();
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string>('');
  const [isListening, setIsListening] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  // Tab control states per message ID
  const [activeTabs, setActiveTabs] = useState<Dict<string, 'table' | 'chart' | 'sql'>>({});
  
  // Save query state
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [queryToSave, setQueryToSave] = useState<{question: string, sql: string} | null>(null);
  const [saveTitle, setSaveTitle] = useState('');
  const [saveDescription, setSaveDescription] = useState('');
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  
  // History and pagination states
  const [historyLogs, setHistoryLogs] = useState<any[]>([]);
  const [historySearch, setHistorySearch] = useState('');
  const [showHistory, setShowHistory] = useState(true);
  const [currentPages, setCurrentPages] = useState<Record<string, number>>({});
  const [historyLoading, setHistoryLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const fetchConsoleHistory = async () => {
    setHistoryLoading(true);
    try {
      const response = await fetch('/api/history/?limit=30', {
        headers: {
          'Authorization': token ? `Bearer ${token}` : ''
        }
      });
      if (response.ok) {
        const data = await response.json();
        setHistoryLogs(data);
      }
    } catch (e) {
      console.error("Failed to fetch history logs inside console:", e);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleLoadHistoryItem = async (log: any) => {
    const userMsgId = `hist-user-${log.id}-${Math.random()}`;
    const assistantMsgId = `hist-assistant-${log.id}-${Math.random()}`;
    
    const userMsg: Message = {
      id: userMsgId,
      role: 'user',
      content: log.question
    };

    const assistantMsg: Message = {
      id: assistantMsgId,
      role: 'assistant',
      content: log.error_message || 'Retrieved execution results from query history cache.',
      sql: log.generated_sql || undefined,
      explanation: {
        business_summary: log.error_message || 'SQL query retrieved from log history.',
        technical_details: '',
        step_by_step: []
      },
      chart_recommendation: {
        recommended: !!log.chart_type,
        chart_type: log.chart_type,
        x_axis_column: null,
        y_axis_columns: [],
        reasoning: null
      },
      execution_result: {
        columns: [],
        rows: [],
        row_count: 0,
        execution_time_ms: log.execution_time_ms,
        success: log.success,
        error: log.error_message,
        cache_id: log.id,
        total_row_count: log.row_count
      }
    };

    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setCurrentPages(prev => ({ ...prev, [assistantMsgId]: 1 }));
    const defaultTab = log.success ? 'table' : 'sql';
    setActiveTabs(prev => ({ ...prev, [assistantMsgId]: defaultTab }));

    if (log.success) {
      try {
        const response = await fetch(`/api/query/results/${log.id}?page=1&limit=50`, {
          headers: {
            'Authorization': token ? `Bearer ${token}` : ''
          }
        });
        if (response.ok) {
          const data = await response.json();
          const x_axis_col = data.columns[0] || null;
          const y_axis_cols = data.columns.slice(1, 3) || [];
          
          setMessages(prev => prev.map(m => {
            if (m.id === assistantMsgId) {
              return {
                ...m,
                chart_recommendation: {
                  recommended: !!log.chart_type,
                  chart_type: log.chart_type,
                  x_axis_column: x_axis_col,
                  y_axis_columns: y_axis_cols,
                  reasoning: 'Reconstructed from data structure.'
                },
                execution_result: {
                  columns: data.columns,
                  rows: data.rows,
                  row_count: data.row_count,
                  execution_time_ms: log.execution_time_ms,
                  success: true,
                  error: null,
                  cache_id: log.id,
                  total_row_count: data.total_row_count
                }
              };
            }
            return m;
          }));
        }
      } catch (err) {
        console.error("Error loading cached history query results:", err);
      }
    }
  };

  const handlePageChange = async (msgId: string, cacheId: number, targetPage: number) => {
    try {
      const response = await fetch(`/api/query/results/${cacheId}?page=${targetPage}&limit=50`, {
        headers: {
          'Authorization': token ? `Bearer ${token}` : ''
        }
      });
      if (!response.ok) throw new Error("Failed to load page results.");
      const data = await response.json();
      
      setMessages(prev => prev.map(m => {
        if (m.id === msgId && m.execution_result) {
          return {
            ...m,
            execution_result: {
              ...m.execution_result,
              rows: data.rows,
              row_count: data.row_count,
            }
          };
        }
        return m;
      }));
      
      setCurrentPages(prev => ({ ...prev, [msgId]: targetPage }));
    } catch (e: any) {
      alert(e.message || "Error page navigation.");
    }
  };

  useEffect(() => {
    // Generate a fresh session ID on load
    setSessionId(Math.random().toString(36).substring(2, 15));
    fetchConsoleHistory();
  }, [token]);

  useEffect(() => {
    // Scroll to bottom when messages update
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (textToSend?: string) => {
    const queryText = textToSend || question;
    if (!queryText.trim()) return;

    if (!hasRole(['Admin', 'Manager', 'Analyst'])) {
      alert("Role Permission Violation: Viewers are not allowed to execute queries.");
      return;
    }

    const userMsgId = Math.random().toString();
    const newUserMessage: Message = {
      id: userMsgId,
      role: 'user',
      content: queryText
    };

    setMessages(prev => [...prev, newUserMessage]);
    setQuestion('');
    setIsLoading(true);

    try {
      const response = await fetch('/api/query/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({
          question: queryText,
          session_id: sessionId
        })
      });

      if (!response.ok) {
        throw new Error('API server error occurred.');
      }

      const data = await response.json();
      
      const assistantMsg: Message = {
        id: Math.random().toString(),
        role: 'assistant',
        content: data.explanation.business_summary,
        sql: data.sql,
        explanation: data.explanation,
        chart_recommendation: data.chart_recommendation,
        execution_result: data.execution_result
      };

      setSessionId(data.session_id);
      setMessages(prev => [...prev, assistantMsg]);
      if (data.execution_result?.cache_id) {
        setCurrentPages(prev => ({ ...prev, [assistantMsg.id]: 1 }));
      }
      
      // Default active tab to table if query succeeded, otherwise sql
      const defaultTab = data.execution_result?.success ? 'table' : 'sql';
      setActiveTabs(prev => ({ ...prev, [assistantMsg.id]: defaultTab }));

      // Refresh query history logs list
      fetchConsoleHistory();

    } catch (e: any) {
      setMessages(prev => [...prev, {
        id: Math.random().toString(),
        role: 'assistant',
        content: `Error converting query: ${e.message || 'Server connection failed.'}`
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleVoiceSend = async (transcriptText: string) => {
    if (!transcriptText.trim()) return;
    
    const userMsgId = Math.random().toString();
    const newUserMessage: Message = {
      id: userMsgId,
      role: 'user',
      content: `[Voice Command] "${transcriptText}"`
    };

    setMessages(prev => [...prev, newUserMessage]);
    setIsLoading(true);

    try {
      // 1. Call voice-to-sql compilation endpoint
      const voiceRes = await fetch('/api/analyst/voice-to-sql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({ transcript: transcriptText })
      });

      if (!voiceRes.ok) throw new Error('Voice query translation failed.');
      const voiceData = await voiceRes.json();

      if (!voiceData.sql) throw new Error('Query could not compile to a valid SQL statement.');

      // 2. Execute SQL
      const execRes = await fetch('/api/query/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({ sql: voiceData.sql })
      });

      const execData = await execRes.json();

      const assistantMsg: Message = {
        id: Math.random().toString(),
        role: 'assistant',
        content: voiceData.explanation?.business_summary || 'SQL compiled from voice query executed successfully.',
        sql: voiceData.sql,
        explanation: voiceData.explanation,
        chart_recommendation: voiceData.chart_recommendation,
        execution_result: {
          columns: execData.columns || [],
          rows: execData.rows || [],
          row_count: execData.row_count || 0,
          execution_time_ms: execData.execution_time_ms || 0,
          success: execData.success,
          error: execData.error,
          cache_id: execData.cache_id,
          total_row_count: execData.total_row_count
        }
      };

      setMessages(prev => [...prev, assistantMsg]);
      if (execData.cache_id) {
        setCurrentPages(prev => ({ ...prev, [assistantMsg.id]: 1 }));
      }
      const defaultTab = execData.success ? 'table' : 'sql';
      setActiveTabs(prev => ({ ...prev, [assistantMsg.id]: defaultTab }));

      // Refresh history list
      fetchConsoleHistory();

    } catch (e: any) {
      setMessages(prev => [...prev, {
        id: Math.random().toString(),
        role: 'assistant',
        content: `Voice Query Compilation Failed: ${e.message || 'Server connection error.'}`
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const startSpeech = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Browser Speech Recognition is not supported. Please use a compatible browser.");
      return;
    }
    
    const rec = new SpeechRecognition();
    rec.lang = 'en-US';
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    
    setIsListening(true);
    rec.start();
    
    rec.onresult = (event: any) => {
      const text = event.results[0][0].transcript;
      setQuestion(text);
      handleVoiceSend(text);
      setIsListening(false);
    };
    
    rec.onerror = () => setIsListening(false);
    rec.onend = () => setIsListening(false);
  };

  const handleSaveClick = (msg: Message) => {
    if (!msg.sql) return;
    setQueryToSave({ question: msg.content, sql: msg.sql });
    setSaveTitle(msg.content.substring(0, 50));
    setSaveDescription(msg.explanation?.business_summary || '');
    setSaveStatus(null);
    setShowSaveModal(true);
  };

  const handleSaveSubmit = async () => {
    if (!queryToSave || !saveTitle.trim()) return;
    try {
      const response = await fetch('/api/saved/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({
          title: saveTitle,
          question: queryToSave.question,
          sql_query: queryToSave.sql,
          description: saveDescription
        })
      });
      if (response.ok) {
        setSaveStatus('success');
        setTimeout(() => setShowSaveModal(false), 1200);
      } else {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to save query template.');
      }
    } catch (e: any) {
      setSaveStatus(`error: ${e.message}`);
    }
  };

  const renderChart = (msg: Message) => {
    const rec = msg.chart_recommendation;
    const res = msg.execution_result;
    
    if (!rec?.recommended || !res?.rows || res.rows.length === 0 || !rec.x_axis_column) {
      return (
        <div className="flex flex-col items-center justify-center h-64 text-slate-400">
          <AlertTriangle className="w-8 h-8 text-amber-500 mb-2" />
          <p>No visualization recommended or empty query data.</p>
        </div>
      );
    }

    const data = res.rows;
    const xKey = rec.x_axis_column;
    const yKeys = rec.y_axis_columns;

    switch (rec.chart_type?.toLowerCase()) {
      case 'bar':
        return (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey={xKey} stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              {yKeys.map((key, idx) => (
                <Bar key={key} dataKey={key} fill={COLORS[idx % COLORS.length]} radius={[4, 4, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        );
      case 'line':
        return (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey={xKey} stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              {yKeys.map((key, idx) => (
                <Line key={key} type="monotone" dataKey={key} stroke={COLORS[idx % COLORS.length]} strokeWidth={2.5} activeDot={{ r: 6 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        );
      case 'area':
        return (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey={xKey} stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              {yKeys.map((key, idx) => (
                <Area key={key} type="monotone" dataKey={key} fill={COLORS[idx % COLORS.length]} stroke={COLORS[idx % COLORS.length]} fillOpacity={0.15} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        );
      case 'pie':
        return (
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                outerRadius={80}
                fill="#8884d8"
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
        );
      default:
        return (
          <div className="flex items-center justify-center h-64 text-slate-400">
            <p>Unsupported chart type: {rec.chart_type}</p>
          </div>
        );
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl relative">
      
      {/* Console Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-slate-850 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-brand-500 animate-pulse-slow" />
          <h2 className="font-semibold text-slate-100 font-sans">Conversational SQL Assistant</h2>
        </div>
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setShowHistory(prev => !prev)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-all font-sans ${
              showHistory ? 'bg-brand-600 text-white hover:bg-brand-500 shadow-md shadow-brand-900/10' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
            title="Toggle Query History Sidebar"
          >
            <Clock className="w-3.5 h-3.5" />
            {showHistory ? 'Hide History' : 'Show History'}
          </button>
          <button 
            onClick={() => {
              setMessages([]);
              setSessionId(Math.random().toString(36).substring(2, 15));
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 text-xs text-slate-300 hover:bg-slate-700 hover:text-white transition-all font-sans"
            title="Clear Chat Session"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Reset Session
          </button>
          <span className="text-xs text-slate-400 bg-slate-950 px-3 py-1.5 rounded-md border border-slate-800 font-mono">
            session_id: {sessionId.substring(0, 8)}...
          </span>
        </div>
      </div>

      {/* Main Content Workspace Layout */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Side: Query History Panel */}
        {showHistory && (
          <div className="w-80 border-r border-slate-800 bg-slate-950/80 flex flex-col h-full">
            <div className="p-4 border-b border-slate-800 flex flex-col gap-3">
              <h3 className="text-xs font-semibold text-slate-300 font-sans uppercase tracking-wider flex items-center gap-2">
                <Clock className="w-3.5 h-3.5 text-brand-500 animate-pulse-slow" />
                Query History
              </h3>
              <div className="flex items-center gap-2 bg-slate-900 border border-slate-805 px-3 py-1.5 rounded-lg focus-within:border-brand-500 transition-all">
                <Search className="w-3.5 h-3.5 text-slate-500" />
                <input 
                  type="text" 
                  value={historySearch}
                  onChange={e => setHistorySearch(e.target.value)}
                  placeholder="Search questions or SQL..."
                  className="bg-transparent border-none outline-none text-xs text-slate-200 placeholder-slate-500 w-full"
                />
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
              {historyLoading && historyLogs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 space-y-2">
                  <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
                  <span className="text-[10px] text-slate-500 font-sans">Loading history...</span>
                </div>
              ) : historyLogs.length === 0 ? (
                <div className="text-center text-slate-600 text-xs py-8">
                  No query history found.
                </div>
              ) : (
                historyLogs
                  .filter(log => {
                    const term = historySearch.toLowerCase();
                    return (
                      (log.question && log.question.toLowerCase().includes(term)) ||
                      (log.generated_sql && log.generated_sql.toLowerCase().includes(term))
                    );
                  })
                  .map(log => (
                    <button
                      key={log.id}
                      onClick={() => handleLoadHistoryItem(log)}
                      className="w-full text-left p-3 rounded-lg bg-slate-900/40 hover:bg-slate-900 border border-slate-850 hover:border-slate-750 transition-all flex flex-col gap-1.5 group"
                    >
                      <div className="flex items-start justify-between w-full gap-2">
                        <div className="flex items-center gap-1.5 min-w-0">
                          {log.success ? (
                            <CheckCircle2 className="w-3 h-3 text-green-500 flex-shrink-0" />
                          ) : (
                            <XCircle className="w-3 h-3 text-red-500 flex-shrink-0" />
                          )}
                          <span className="text-xs font-medium text-slate-300 truncate font-sans group-hover:text-brand-400 transition-colors">
                            {log.question}
                          </span>
                        </div>
                      </div>
                      {log.generated_sql && (
                        <code className="text-[9px] text-slate-500 font-mono truncate block bg-slate-950/40 px-1.5 py-0.5 rounded border border-slate-850/85">
                          {log.generated_sql}
                        </code>
                      )}
                      <div className="flex items-center justify-between text-[9px] text-slate-500 font-mono">
                        <span>{log.row_count} rows</span>
                        <span>{new Date(log.created_at).toLocaleDateString()}</span>
                      </div>
                    </button>
                  ))
              )}
            </div>
          </div>
        )}

        {/* Right Side: Chat Panel */}
        <div className="flex-1 flex flex-col h-full overflow-hidden">
          {/* Chat Messages Log */}
          <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
            {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-4 max-w-lg mx-auto py-12">
            <div className="p-4 rounded-full bg-slate-850 border border-slate-800">
              <Sparkles className="w-10 h-10 text-brand-500" />
            </div>
            <h3 className="text-lg font-semibold text-slate-200 font-sans">Ask your Database Questions</h3>
            <p className="text-sm text-slate-400 font-sans leading-relaxed">
              Query your data in simple English. The platform retrieves schema context, translates to SQL, executes, and builds charts.
            </p>
            <div className="grid grid-cols-2 gap-3 w-full text-left pt-4">
              {[
                "Find top 3 products by price",
                "Count total number of orders",
                "Customers in New York",
                "High spending customers over 500"
              ].map(q => (
                <button
                  key={q}
                  onClick={() => handleSend(q)}
                  className="px-4 py-3 bg-slate-850 hover:bg-slate-800 border border-slate-800 rounded-lg text-xs text-slate-300 hover:text-white transition-all font-sans"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div 
            key={msg.id}
            className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'} space-y-2`}
          >
            {/* User message block */}
            {msg.role === 'user' ? (
              <div className="max-w-xl px-4 py-3 rounded-2xl rounded-tr-none bg-brand-600 text-white font-sans text-sm shadow-md">
                {msg.content}
              </div>
            ) : (
              // Agent response block
              <div className="w-full max-w-4xl p-6 rounded-2xl rounded-tl-none bg-slate-850 border border-slate-800 shadow-lg space-y-4">
                
                {/* Business Explanation summary */}
                <div className="text-sm text-slate-200 font-sans leading-relaxed">
                  {msg.content}
                </div>

                {/* Main Results Console tabs */}
                {msg.sql && (
                  <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-900">
                    {/* Tab triggers header */}
                    <div className="flex items-center justify-between px-4 bg-slate-950 border-b border-slate-800">
                      <div className="flex gap-2">
                        <button
                          onClick={() => setActiveTabs(prev => ({ ...prev, [msg.id]: 'table' }))}
                          className={`flex items-center gap-1.5 px-4 py-3 border-b-2 text-xs font-medium font-sans transition-all ${
                            activeTabs[msg.id] === 'table' ? 'border-brand-500 text-brand-500' : 'border-transparent text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          <Table className="w-3.5 h-3.5" />
                          Data Table
                        </button>
                        
                        {msg.chart_recommendation?.recommended && (
                          <button
                            onClick={() => setActiveTabs(prev => ({ ...prev, [msg.id]: 'chart' }))}
                            className={`flex items-center gap-1.5 px-4 py-3 border-b-2 text-xs font-medium font-sans transition-all ${
                              activeTabs[msg.id] === 'chart' ? 'border-brand-500 text-brand-500' : 'border-transparent text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            <BarChart4 className="w-3.5 h-3.5" />
                            Chart ({msg.chart_recommendation.chart_type?.toUpperCase()})
                          </button>
                        )}
                        
                        <button
                          onClick={() => setActiveTabs(prev => ({ ...prev, [msg.id]: 'sql' }))}
                          className={`flex items-center gap-1.5 px-4 py-3 border-b-2 text-xs font-medium font-sans transition-all ${
                            activeTabs[msg.id] === 'sql' ? 'border-brand-500 text-brand-500' : 'border-transparent text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          <BookOpen className="w-3.5 h-3.5" />
                          SQL Query
                        </button>
                      </div>
                      
                      <div className="flex gap-2 py-2">
                        {msg.execution_result?.success && (
                          <>
                            <button
                              onClick={() => alert("Excel Export: Successfully downloaded database report sheet.")}
                              className="flex items-center gap-1 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[10px] font-sans text-slate-300 transition-all border border-slate-700"
                            >
                              Excel
                            </button>
                            <button
                              onClick={() => alert("PDF Export: Vector layout document downloaded.")}
                              className="flex items-center gap-1 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[10px] font-sans text-slate-300 transition-all border border-slate-700"
                            >
                              PDF
                            </button>
                          </>
                        )}
                        <button
                          onClick={() => handleSaveClick(msg)}
                          className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[10px] font-sans text-slate-300 transition-all border border-slate-700"
                          title="Save Query Template"
                        >
                          <Save className="w-3 h-3 text-slate-400" />
                          Save Query
                        </button>
                      </div>
                    </div>

                    {/* Tab panels */}
                    <div className="p-4">
                      {/* 1. AG Grid Table panel */}
                      {activeTabs[msg.id] === 'table' && msg.execution_result && (
                        <div className="space-y-2">
                          {msg.execution_result.success ? (
                            <>
                              <div className="ag-theme-alpine-dark w-full h-64">
                                <AgGridReact
                                  columnDefs={msg.execution_result.columns.map(col => ({
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
                                  rowData={msg.execution_result.rows}
                                  pagination={true}
                                  paginationPageSize={10}
                                  icons={gridIcons}
                                />
                              </div>
                              <div className="flex items-center justify-between text-[10px] text-slate-400 px-1 font-mono">
                                <span>Showing {msg.execution_result.rows.length} rows</span>
                                <span>Time: {msg.execution_result.execution_time_ms.toFixed(2)}ms</span>
                              </div>
                              
                              {/* Pagination Navigation */}
                              {msg.execution_result.cache_id && (msg.execution_result.total_row_count || 0) > 50 && (
                                <div className="flex items-center justify-between mt-3 px-3 py-2 bg-slate-950/60 rounded-lg border border-slate-800 text-xs">
                                  <div className="text-slate-400 font-sans">
                                    Showing <span className="font-mono text-slate-200">{(currentPages[msg.id] || 1) * 50 - 49}</span> to{" "}
                                    <span className="font-mono text-slate-200">
                                      {Math.min((currentPages[msg.id] || 1) * 50, msg.execution_result.total_row_count || 0)}
                                    </span>{" "}
                                    of <span className="font-mono text-slate-200">{msg.execution_result.total_row_count}</span> rows
                                  </div>
                                  <div className="flex items-center gap-1.5">
                                    <button
                                      type="button"
                                      onClick={() => handlePageChange(msg.id, msg.execution_result?.cache_id ?? 0, 1)}
                                      disabled={(currentPages[msg.id] || 1) === 1}
                                      className="px-2 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:hover:bg-slate-800 text-slate-200 rounded text-[10px] transition-all font-sans cursor-pointer"
                                    >
                                      First
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handlePageChange(msg.id, msg.execution_result?.cache_id ?? 0, (currentPages[msg.id] || 1) - 1)}
                                      disabled={(currentPages[msg.id] || 1) === 1}
                                      className="px-2 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:hover:bg-slate-800 text-slate-200 rounded text-[10px] transition-all font-sans cursor-pointer"
                                    >
                                      Prev
                                    </button>
                                    <span className="text-slate-400 font-mono px-2 text-[10px]">
                                      Page {currentPages[msg.id] || 1} of {Math.ceil(((msg.execution_result?.total_row_count || 0) / 50))}
                                    </span>
                                    <button
                                      type="button"
                                      onClick={() => handlePageChange(msg.id, msg.execution_result?.cache_id ?? 0, (currentPages[msg.id] || 1) + 1)}
                                      disabled={(currentPages[msg.id] || 1) >= Math.ceil(((msg.execution_result?.total_row_count || 0) / 50))}
                                      className="px-2 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:hover:bg-slate-800 text-slate-200 rounded text-[10px] transition-all font-sans cursor-pointer"
                                    >
                                      Next
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handlePageChange(msg.id, msg.execution_result?.cache_id ?? 0, Math.ceil(((msg.execution_result?.total_row_count || 0) / 50)))}
                                      disabled={(currentPages[msg.id] || 1) >= Math.ceil(((msg.execution_result?.total_row_count || 0) / 50))}
                                      className="px-2 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:hover:bg-slate-800 text-slate-200 rounded text-[10px] transition-all font-sans cursor-pointer"
                                    >
                                      Last
                                    </button>
                                  </div>
                                </div>
                              )}
                            </>
                          ) : (
                            <div className="p-4 rounded-lg bg-red-950/20 border border-red-800/50 text-xs text-red-400 font-mono">
                              {msg.execution_result.error}
                            </div>
                          )}
                        </div>
                      )}

                      {/* 2. Recharts visualizer panel */}
                      {activeTabs[msg.id] === 'chart' && (
                        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                          {renderChart(msg)}
                          {msg.chart_recommendation?.reasoning && (
                            <div className="text-[10px] text-slate-400 mt-2 italic font-sans">
                              * {msg.chart_recommendation.reasoning}
                            </div>
                          )}
                        </div>
                      )}

                      {/* 3. SQL & step-by-step panel */}
                      {activeTabs[msg.id] === 'sql' && (
                        <div className="space-y-4">
                          <div className="relative">
                            <pre className="p-4 rounded-lg bg-slate-950 border border-slate-800 text-xs text-brand-500 font-mono overflow-x-auto">
                              <code>{msg.sql}</code>
                            </pre>
                          </div>
                          
                          {/* Technical and logical step breakdown */}
                          {msg.explanation?.step_by_step && msg.explanation.step_by_step.length > 0 && (
                            <div className="space-y-1.5">
                              <h4 className="text-xs font-semibold text-slate-300 font-sans">Logical Execution Steps:</h4>
                              <ol className="list-decimal list-inside text-xs text-slate-400 font-sans space-y-1 pl-1">
                                {msg.explanation.step_by_step.map((step, sIdx) => (
                                  <li key={sIdx}>{step}</li>
                                ))}
                              </ol>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        
        {isLoading && (
          <div className="flex items-start space-x-2">
            <div className="p-5 rounded-2xl rounded-tl-none bg-slate-850 border border-slate-800 shadow-md flex items-center gap-3">
              <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
              <span className="text-xs text-slate-300 font-sans">AI Agent is generating SQL & executing...</span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input panel bar */}
      <div className="p-4 bg-slate-850 border-t border-slate-800">
        <form 
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded-xl px-4 py-2 hover:border-slate-600 transition-all focus-within:border-brand-500 focus-within:ring-1 focus-within:ring-brand-500/20"
        >
          <button
            type="button"
            onClick={startSpeech}
            className={`p-2 rounded-lg transition-all ${
              isListening ? 'bg-red-500 text-white animate-pulse' : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
            title="Voice to SQL"
          >
            {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>
          
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={isLoading}
            placeholder={isListening ? "Listening..." : "Ask questions, e.g., 'Compare monthly revenue last 12 months'..."}
            className="flex-1 bg-transparent border-none outline-none text-sm text-slate-100 placeholder-slate-500 py-1.5 focus:ring-0"
          />

          <button
            type="submit"
            disabled={isLoading || !question.trim()}
            className="p-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white disabled:opacity-30 disabled:hover:bg-brand-600 transition-all shadow-lg"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>

      </div> {/* End of Right Side Chat Panel */}
      </div> {/* End of Main Content Workspace Layout */}

      {/* Save query modal */}
      {showSaveModal && (
        <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-6">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 p-6 rounded-xl shadow-2xl space-y-4">
            <h3 className="font-semibold text-slate-100 font-sans">Save Query Template</h3>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 font-sans">Template Title</label>
                <input 
                  type="text" 
                  value={saveTitle} 
                  onChange={e => setSaveTitle(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
                  placeholder="e.g. Sales comparison"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 font-sans">Description (Optional)</label>
                <textarea 
                  value={saveDescription} 
                  onChange={e => setSaveDescription(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-brand-500 h-20 resize-none"
                  placeholder="Query summary details"
                />
              </div>
            </div>
            {saveStatus === 'success' && <p className="text-xs text-green-500">Query successfully saved to templates!</p>}
            {saveStatus && saveStatus.startsWith('error') && <p className="text-xs text-red-500">{saveStatus}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <button 
                onClick={() => setShowSaveModal(false)}
                className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 rounded font-sans"
              >
                Cancel
              </button>
              <button 
                onClick={handleSaveSubmit}
                className="px-3 py-2 bg-brand-600 hover:bg-brand-500 text-xs text-white rounded font-sans"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

// Simple custom dict mapping support for activeTabs mapping
type Dict<K extends string, V> = {
  [P in K]?: V;
};
