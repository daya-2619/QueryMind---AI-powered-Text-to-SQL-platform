import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { 
  TrendingUp, AlertOctagon, Calendar, ClipboardList, Trash2, 
  Plus, AlertTriangle, User, Sparkles
} from 'lucide-react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';

interface SavedQuery {
  id: number;
  title: string;
}

interface ScheduledReport {
  id: number;
  report_name: string;
  query_id: number;
  cron_expression: string;
  recipient_email: string;
  is_active: boolean;
}

interface PredictionPoint {
  period: string;
  predicted_amount: number;
}

interface Anomaly {
  order_id: number;
  order_date: string;
  amount: number;
  z_score: number;
  deviation: string;
}

interface QueryLog {
  id: number;
  question: string;
  generated_sql: string;
  execution_time_ms: number;
  row_count: number;
  success: boolean;
  error_message?: string;
  created_at: string;
  user_id?: number;
}

export const ManagerConsole: React.FC = () => {
  const { token } = useAuth();
  const [activeSubTab, setActiveSubTab] = useState<'predictive' | 'anomalies' | 'schedules' | 'history'>('predictive');
  
  // Saved Queries & schedules lists
  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>([]);
  const [schedules, setSchedules] = useState<ScheduledReport[]>([]);
  
  // Predictive Analytics states
  const [predictions, setPredictions] = useState<PredictionPoint[]>([]);
  const [predSummary, setPredSummary] = useState<any>(null);
  const [loadingPred, setLoadingPred] = useState(false);
  const [predError, setPredError] = useState<string | null>(null);

  // Anomaly Detection states
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [anomalySummary, setAnomalySummary] = useState<any>(null);
  const [loadingAnom, setLoadingAnom] = useState(false);
  const [anomError, setAnomError] = useState<string | null>(null);

  // Scheduled Reports scheduling form
  const [schedName, setSchedName] = useState('');
  const [selectedQueryId, setSelectedQueryId] = useState<string>('');
  const [cronExpr, setCronExpr] = useState('0 9 * * *');
  const [recipient, setRecipient] = useState('');
  const [formStatus, setFormStatus] = useState<{ type: 'success' | 'error', msg: string } | null>(null);
  const [loadingSchedules, setLoadingSchedules] = useState(false);

  // Team History states
  const [teamHistory, setTeamHistory] = useState<QueryLog[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    fetchSavedQueries();
    fetchScheduledReports();
    if (activeSubTab === 'predictive') runPredictions();
    else if (activeSubTab === 'anomalies') runAnomalyDetection();
    else if (activeSubTab === 'history') fetchTeamHistory();
  }, [activeSubTab, token]);

  const fetchSavedQueries = async () => {
    try {
      const response = await fetch('/api/saved/', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setSavedQueries(data);
        if (data.length > 0) setSelectedQueryId(data[0].id.toString());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchScheduledReports = async () => {
    setLoadingSchedules(true);
    try {
      const response = await fetch('/api/manager/scheduled-reports', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        setSchedules(await response.json());
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingSchedules(false);
    }
  };

  const runPredictions = async () => {
    setLoadingPred(true);
    setPredError(null);
    try {
      const response = await fetch('/api/manager/predictions', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setPredictions(data.predictions);
        setPredSummary(data);
      } else {
        setPredError(data.detail || data.error || 'Failed to calculate transaction forecasts.');
      }
    } catch (e: any) {
      setPredError(e.message || 'Server calculation timeout.');
    } finally {
      setLoadingPred(false);
    }
  };

  const runAnomalyDetection = async () => {
    setLoadingAnom(true);
    setAnomError(null);
    try {
      const response = await fetch('/api/manager/anomaly-detection', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setAnomalies(data.anomalies);
        setAnomalySummary(data);
      } else {
        setAnomError(data.detail || data.error || 'Anomaly scanner execution failed.');
      }
    } catch (e: any) {
      setAnomError(e.message || 'Server timeout scanning records.');
    } finally {
      setLoadingAnom(false);
    }
  };

  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormStatus(null);
    if (!schedName.trim() || !selectedQueryId || !cronExpr.trim() || !recipient.trim()) {
      setFormStatus({ type: 'error', msg: 'All scheduling parameters are required.' });
      return;
    }

    try {
      const response = await fetch('/api/manager/scheduled-reports', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          report_name: schedName,
          query_id: parseInt(selectedQueryId),
          cron_expression: cronExpr,
          recipient_email: recipient
        })
      });

      if (response.ok) {
        setFormStatus({ type: 'success', msg: 'Report schedule successfully configured.' });
        setSchedName('');
        setRecipient('');
        fetchScheduledReports();
      } else {
        const err = await response.json();
        setFormStatus({ type: 'error', msg: err.detail || 'Creation failed.' });
      }
    } catch (e: any) {
      setFormStatus({ type: 'error', msg: e.message });
    }
  };

  const handleDeleteSchedule = async (id: number) => {
    if (!confirm('Are you sure you want to cancel this report schedule?')) return;
    try {
      const response = await fetch(`/api/manager/scheduled-reports/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        fetchScheduledReports();
      } else {
        alert('Failed to delete schedule.');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchTeamHistory = async () => {
    setLoadingHistory(true);
    try {
      const response = await fetch('/api/history/', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        setTeamHistory(await response.json());
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingHistory(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
      
      {/* Sub tabs header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between px-6 py-4 bg-slate-850 border-b border-slate-800 gap-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-purple-500" />
          <h2 className="font-semibold text-slate-100 font-sans">Manager Governance Console</h2>
        </div>

        {/* Tab triggers */}
        <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800 self-start md:self-auto">
          {[
            { id: 'predictive', name: 'Predictions', icon: TrendingUp },
            { id: 'anomalies', name: 'Anomalies', icon: AlertOctagon },
            { id: 'schedules', name: 'Schedules', icon: Calendar },
            { id: 'history', name: 'Team Queries', icon: ClipboardList }
          ].map(tab => {
            const Icon = tab.icon;
            const isSelected = activeSubTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveSubTab(tab.id as any)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium font-sans transition-all ${
                  isSelected ? 'bg-purple-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Panel Content */}
      <div className="flex-1 p-6 overflow-y-auto">
        
        {/* 1. Predictive Analytics Panel */}
        {activeSubTab === 'predictive' && (
          <div className="space-y-6">
            <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-5 space-y-2">
              <div className="flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-semibold text-slate-200">Revenue Forecasting</h3>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Applies standard linear regression over historical sales volume to forecast future trends.
              </p>
            </div>

            {loadingPred ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
              </div>
            ) : predError ? (
              <div className="p-4 rounded-lg bg-red-950/20 border border-red-800/40 text-xs text-red-400 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                <span>{predError}</span>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                
                {/* Metrics detail cards */}
                <div className="md:col-span-1 space-y-4">
                  <div className="bg-slate-950 border border-slate-805 p-4 rounded-xl space-y-2">
                    <div className="text-[10px] text-slate-500 uppercase font-bold tracking-wider font-sans">Growth Trend (Slope)</div>
                    <div className="text-2xl font-bold text-green-400 font-mono">
                      {predSummary?.slope > 0 ? '+' : ''}{predSummary?.slope} <span className="text-xs font-normal text-slate-400 font-sans">USD/day</span>
                    </div>
                    <p className="text-[10px] text-slate-500 font-sans">Daily average incremental value change</p>
                  </div>
                  
                  <div className="bg-slate-950 border border-slate-805 p-4 rounded-xl space-y-1">
                    <div className="text-[10px] text-slate-500 uppercase font-bold tracking-wider font-sans font-sans">Regression Intercept</div>
                    <div className="text-xl font-bold text-slate-200 font-mono">${predSummary?.intercept}</div>
                  </div>

                  <div className="bg-slate-950 border border-slate-850 p-4 rounded-xl space-y-2">
                    <div className="text-[10px] font-bold text-slate-400 font-sans uppercase">Predictions Timeline</div>
                    <div className="space-y-1.5">
                      {predictions.map((p, idx) => (
                        <div key={idx} className="flex justify-between items-center text-xs">
                          <span className="text-slate-400 font-mono">{p.period}</span>
                          <span className="font-bold text-purple-400 font-mono">${p.predicted_amount}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Forecast Line Chart */}
                <div className="md:col-span-2 bg-slate-950 border border-slate-805 p-5 rounded-xl flex flex-col justify-between">
                  <h4 className="text-xs font-semibold text-slate-300 font-sans mb-4 uppercase tracking-wider">Historical Trend & Projection</h4>
                  <div className="h-60">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={predictions.map((p) => ({
                          day: p.period,
                          Revenue: p.predicted_amount
                        }))}
                        margin={{ top: 5, right: 10, left: -20, bottom: 0 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis dataKey="day" stroke="#64748b" fontSize={10} />
                        <YAxis stroke="#64748b" fontSize={10} />
                        <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
                        <Legend wrapperStyle={{ fontSize: '10px' }} />
                        <Line type="monotone" dataKey="Revenue" stroke="#a855f7" strokeWidth={2.5} activeDot={{ r: 6 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

              </div>
            )}
          </div>
        )}

        {/* 2. Anomaly Detection Panel */}
        {activeSubTab === 'anomalies' && (
          <div className="space-y-6">
            <div className="bg-slate-950/40 border border-slate-805 rounded-xl p-5 space-y-2">
              <div className="flex items-center gap-1.5">
                <AlertOctagon className="w-4 h-4 text-red-500 animate-pulse" />
                <h3 className="text-sm font-semibold text-slate-200">Revenue Anomaly Detection</h3>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed font-sans">
                Scans targets database records to find transactions deviating beyond <code className="bg-slate-900 px-1 py-0.5 rounded text-purple-400">1.2 standard deviations</code> from the average transaction value.
              </p>
            </div>

            {loadingAnom ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-6 h-6 border-2 border-red-500 border-t-transparent rounded-full animate-spin"></div>
              </div>
            ) : anomError ? (
              <div className="p-4 rounded-lg bg-red-950/20 border border-red-800/40 text-xs text-red-400 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                <span>{anomError}</span>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Stats Summary */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-slate-950 border border-slate-805 p-3 rounded-lg text-center">
                    <span className="text-[10px] text-slate-500 block">Avg Transaction</span>
                    <span className="text-base font-bold text-slate-200 font-mono">${anomalySummary?.mean}</span>
                  </div>
                  <div className="bg-slate-950 border border-slate-805 p-3 rounded-lg text-center">
                    <span className="text-[10px] text-slate-500 block">Std Deviation</span>
                    <span className="text-base font-bold text-slate-200 font-mono">${anomalySummary?.std_dev}</span>
                  </div>
                  <div className="bg-slate-950 border border-slate-805 p-3 rounded-lg text-center">
                    <span className="text-[10px] text-slate-500 block">Anomalies Detected</span>
                    <span className="text-base font-bold text-red-400 font-mono">{anomalySummary?.anomalies_found}</span>
                  </div>
                </div>

                {/* Anomalies List */}
                <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-900 text-slate-400 border-b border-slate-800 font-sans">
                        <th className="p-3">Order ID</th>
                        <th className="p-3">Date</th>
                        <th className="p-3 text-right">Amount</th>
                        <th className="p-3 text-center">Z-Score</th>
                        <th className="p-3 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {anomalies.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="p-8 text-center text-slate-500 italic">No transactions exceed standard thresholds.</td>
                        </tr>
                      ) : (
                        anomalies.map((anom, idx) => (
                          <tr key={idx} className="border-b border-slate-850 hover:bg-slate-900/60 font-mono">
                            <td className="p-3 text-slate-300">#{anom.order_id}</td>
                            <td className="p-3 text-slate-400">{anom.order_date}</td>
                            <td className="p-3 text-right font-bold text-slate-200">${anom.amount}</td>
                            <td className="p-3 text-center text-amber-500 font-bold">{anom.z_score}</td>
                            <td className="p-3 text-center font-sans">
                              <span className="inline-block px-2 py-0.5 rounded bg-red-950/20 border border-red-900/40 text-red-400 text-[10px] font-bold">
                                {anom.deviation} Deviation
                              </span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

              </div>
            )}
          </div>
        )}

        {/* 3. Scheduled Reports scheduling Panel */}
        {activeSubTab === 'schedules' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Scheduling Creation Form */}
            <div className="lg:col-span-1 bg-slate-950 border border-slate-805 p-5 rounded-xl space-y-4 self-start">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-sans border-b border-slate-800 pb-2">Schedule Delivery</h4>
              
              {formStatus && (
                <div className={`p-3 rounded-lg text-xs font-sans ${
                  formStatus.type === 'success' ? 'bg-green-950/20 border border-green-800/40 text-green-400' : 'bg-red-950/20 border border-red-800/40 text-red-400'
                }`}>
                  {formStatus.msg}
                </div>
              )}

              <form onSubmit={handleCreateSchedule} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-[10px] text-slate-400 block font-sans">Report Name</label>
                  <input
                    type="text"
                    required
                    value={schedName}
                    onChange={e => setSchedName(e.target.value)}
                    placeholder="Weekly Sales PDF"
                    className="w-full bg-slate-900 border border-slate-800 focus:border-purple-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none transition-all font-sans"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] text-slate-400 block font-sans">Target Saved Query</label>
                  <select
                    value={selectedQueryId}
                    onChange={e => setSelectedQueryId(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 focus:border-purple-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none cursor-pointer transition-all font-sans"
                  >
                    {savedQueries.map(q => (
                      <option key={q.id} value={q.id}>{q.title}</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] text-slate-400 block font-sans">Cron Schedule</label>
                  <input
                    type="text"
                    required
                    value={cronExpr}
                    onChange={e => setCronExpr(e.target.value)}
                    placeholder="0 9 * * *"
                    className="w-full bg-slate-900 border border-slate-800 focus:border-purple-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none transition-all font-mono"
                  />
                  <p className="text-[9px] text-slate-500 font-sans italic mt-1 leading-relaxed">
                    * e.g., "0 9 * * *" represents Daily at 9:00 AM.
                  </p>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] text-slate-400 block font-sans">Recipient Email</label>
                  <input
                    type="email"
                    required
                    value={recipient}
                    onChange={e => setRecipient(e.target.value)}
                    placeholder="dept-head@company.com"
                    className="w-full bg-slate-900 border border-slate-800 focus:border-purple-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none transition-all font-mono"
                  />
                </div>

                <button
                  type="submit"
                  className="w-full flex items-center justify-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white font-semibold text-xs py-2 px-4 rounded-lg transition-all shadow-md"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Enable Cron Delivery
                </button>
              </form>
            </div>

            {/* List of active schedules */}
            <div className="lg:col-span-2 space-y-4">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-sans border-b border-slate-800 pb-2">Active Schedule List</h4>
              {loadingSchedules ? (
                <div className="flex items-center justify-center py-6">
                  <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
                </div>
              ) : schedules.length === 0 ? (
                <p className="text-xs text-slate-500 italic py-4">No report delivery schedules established.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {schedules.map(sched => (
                    <div key={sched.id} className="bg-slate-950 border border-slate-805 p-4 rounded-xl space-y-3 relative overflow-hidden group">
                      <div className="absolute top-0 left-0 w-1 h-full bg-purple-500"></div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-200 font-sans truncate pr-6">{sched.report_name}</span>
                        <button
                          onClick={() => handleDeleteSchedule(sched.id)}
                          className="text-slate-500 hover:text-red-400 p-1 hover:bg-slate-900 rounded transition-all"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <div className="space-y-1">
                        <div className="text-[10px] text-slate-400 font-mono">
                          Cron expression: <span className="text-purple-400 bg-slate-900 px-1 py-0.5 rounded">{sched.cron_expression}</span>
                        </div>
                        <div className="text-[10px] text-slate-400 font-mono truncate">
                          Target Query ID: <span className="text-slate-300 font-bold">#{sched.query_id}</span>
                        </div>
                        <div className="text-[10px] text-slate-400 font-mono truncate">
                          Email to: <span className="text-slate-300 font-bold">{sched.recipient_email}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>
        )}

        {/* 4. Team Query Audit Logs */}
        {activeSubTab === 'history' && (
          <div className="space-y-4">
            <div className="bg-slate-950/40 border border-slate-805 rounded-xl p-5 space-y-2">
              <div className="flex items-center gap-1.5">
                <ClipboardList className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-semibold text-slate-200">Department execution history</h3>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed font-sans">
                Review audit traces of team members queries, execution status, and translation response times.
              </p>
            </div>

            {loadingHistory ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
              </div>
            ) : (
              <div className="border border-slate-808 rounded-xl overflow-hidden bg-slate-950">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-900 text-slate-400 border-b border-slate-800 font-sans">
                      <th className="p-3">User ID</th>
                      <th className="p-3">Natural Language Question</th>
                      <th className="p-3">Execution DDL/SQL</th>
                      <th className="p-3 text-center">Rows</th>
                      <th className="p-3 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {teamHistory.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-8 text-center text-slate-500 italic">No query traces recorded in active logs.</td>
                      </tr>
                    ) : (
                      teamHistory.map((item, idx) => (
                        <tr key={idx} className="border-b border-slate-850 hover:bg-slate-900/60 font-mono">
                          <td className="p-3 text-slate-400">
                            <span className="inline-flex items-center gap-1">
                              <User className="w-3 h-3 text-purple-500" />
                              {item.user_id ? `User #${item.user_id}` : 'System'}
                            </span>
                          </td>
                          <td className="p-3 text-slate-300 font-sans max-w-xs truncate" title={item.question}>{item.question}</td>
                          <td className="p-3 text-slate-500 truncate max-w-xs" title={item.generated_sql}><code>{item.generated_sql || 'N/A'}</code></td>
                          <td className="p-3 text-center text-slate-300">{item.row_count}</td>
                          <td className="p-3 text-center font-sans">
                            <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              item.success ? 'bg-green-950/20 border border-green-900/40 text-green-400' : 'bg-red-950/20 border border-red-900/40 text-red-400'
                            }`}>
                              {item.success ? 'Success' : 'Error'}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
};
