import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { 
  Users, Database, ShieldAlert, Activity, Shield, Trash2, 
  Plus, Check, Play, RefreshCw, AlertTriangle, Key, Ban, CheckCircle
} from 'lucide-react';

interface UserResponse {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface DatabaseConfig {
  id: number;
  name: string;
  connection_url: string;
  provider: string;
  is_active: boolean;
}

interface MaskingRule {
  id: number;
  column_name: string;
  masking_pattern: string;
  is_active: boolean;
}

interface RLSPolicy {
  id: number;
  table_name: string;
  filter_clause: string;
  role: string;
  is_active: boolean;
}

interface CustomRole {
  id: number;
  name: string;
  description: string;
  permissions: string[];
}

interface PlatformMetrics {
  total_queries: number;
  average_latency_ms: number;
  accuracy_rate: number;
  failed_queries: number;
}

export const AdminConsole: React.FC = () => {
  const { token } = useAuth();
  const [subTab, setSubTab] = useState<'users' | 'databases' | 'security' | 'metrics' | 'roles'>('users');

  // Operational states
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [databases, setDatabases] = useState<DatabaseConfig[]>([]);
  const [maskingRules, setMaskingRules] = useState<MaskingRule[]>([]);
  const [rlsPolicies, setRLSPolicies] = useState<RLSPolicy[]>([]);
  const [customRoles, setCustomRoles] = useState<CustomRole[]>([]);
  const [metrics, setMetrics] = useState<PlatformMetrics | null>(null);

  // Forms statuses & loadings
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error', msg: string } | null>(null);

  // Form: Create User
  const [newUsername, setNewUsername] = useState('');
  const [newUserPassword, setNewUserPassword] = useState('');
  const [newUserRole, setNewUserRole] = useState('Analyst');

  // Form: Reset Password
  const [resettingUserId, setResettingUserId] = useState<number | null>(null);
  const [resetPasswordVal, setResetPasswordVal] = useState('');

  // Form: Add Database
  const [dbName, setDbName] = useState('');
  const [dbUrl, setDbUrl] = useState('');
  const [dbProvider, setDbProvider] = useState('postgresql');
  const [testingDbId, setTestingDbId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<{ [id: number]: { success: boolean, msg: string } }>({});

  // Form: Add Masking Rule
  const [maskCol, setMaskCol] = useState('');
  const [maskPattern, setMaskPattern] = useState('*****');

  // Form: Add RLS Policy
  const [rlsTable, setRlsTable] = useState('');
  const [rlsFilter, setRlsFilter] = useState('');
  const [rlsRole, setRlsRole] = useState('Analyst');

  // Form: Create Role
  const [roleName, setRoleName] = useState('');
  const [roleDesc, setRoleDesc] = useState('');
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);

  useEffect(() => {
    setStatusMsg(null);
    if (subTab === 'users') fetchUsers();
    else if (subTab === 'databases') fetchDatabases();
    else if (subTab === 'security') {
      fetchMaskingRules();
      fetchRLSPolicies();
    }
    else if (subTab === 'metrics') fetchMetrics();
    else if (subTab === 'roles') fetchCustomRoles();
  }, [subTab, token]);

  // --- Users management API fetches ---
  const fetchUsers = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/users/', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) setUsers(await response.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUsername.trim() || !newUserPassword.trim()) return;
    try {
      const response = await fetch('/api/users/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          username: newUsername,
          password: newUserPassword,
          role: newUserRole
        })
      });
      if (response.ok) {
        setStatusMsg({ type: 'success', msg: 'User account created.' });
        setNewUsername('');
        setNewUserPassword('');
        fetchUsers();
      } else {
        const err = await response.json();
        setStatusMsg({ type: 'error', msg: err.detail || 'Failed to create user.' });
      }
    } catch (e: any) { setStatusMsg({ type: 'error', msg: e.message }); }
  };

  const toggleUserActive = async (user: UserResponse) => {
    try {
      const targetState = !user.is_active;
      const response = await fetch(`/api/users/${user.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ is_active: targetState })
      });
      if (response.ok) fetchUsers();
    } catch (e) { console.error(e); }
  };

  const handleResetPassword = async (userId: number) => {
    if (!resetPasswordVal.trim()) return;
    try {
      const response = await fetch(`/api/users/${userId}/reset-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ new_password: resetPasswordVal })
      });
      if (response.ok) {
        alert('Password reset successfully.');
        setResetPasswordVal('');
        setResettingUserId(null);
      } else {
        alert('Reset password operation failed.');
      }
    } catch (e) { console.error(e); }
  };

  const handleDeleteUser = async (userId: number) => {
    if (!confirm('Are you sure you want to permanently delete this user?')) return;
    try {
      const response = await fetch(`/api/users/${userId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) fetchUsers();
    } catch (e) { console.error(e); }
  };

  // --- Databases management API fetches ---
  const fetchDatabases = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/databases/', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) setDatabases(await response.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const handleAddDatabase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dbName.trim() || !dbUrl.trim()) return;
    try {
      const response = await fetch('/api/databases/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          name: dbName,
          connection_url: dbUrl,
          provider: dbProvider
        })
      });
      if (response.ok) {
        setStatusMsg({ type: 'success', msg: 'Database connection registered.' });
        setDbName('');
        setDbUrl('');
        fetchDatabases();
      } else {
        const err = await response.json();
        setStatusMsg({ type: 'error', msg: err.detail || 'Registration failed.' });
      }
    } catch (e: any) { setStatusMsg({ type: 'error', msg: e.message }); }
  };

  const handleTestConnection = async (dbId: number) => {
    setTestingDbId(dbId);
    try {
      const response = await fetch(`/api/databases/${dbId}/test`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setTestResult(prev => ({
        ...prev,
        [dbId]: { success: data.success, msg: data.message }
      }));
    } catch (e: any) {
      setTestResult(prev => ({
        ...prev,
        [dbId]: { success: false, msg: e.message }
      }));
    } finally {
      setTestingDbId(null);
    }
  };

  const handleDeleteDatabase = async (dbId: number) => {
    if (!confirm('Are you sure you want to remove this database connection?')) return;
    try {
      const response = await fetch(`/api/databases/${dbId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) fetchDatabases();
    } catch (e) { console.error(e); }
  };

  // --- Security rules management API fetches ---
  const fetchMaskingRules = async () => {
    try {
      const response = await fetch('/api/security/masking', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) setMaskingRules(await response.json());
    } catch (e) { console.error(e); }
  };

  const fetchRLSPolicies = async () => {
    try {
      const response = await fetch('/api/security/rls', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) setRLSPolicies(await response.json());
    } catch (e) { console.error(e); }
  };

  const handleAddMaskingRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!maskCol.trim()) return;
    try {
      const response = await fetch('/api/security/masking', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          column_name: maskCol,
          masking_pattern: maskPattern
        })
      });
      if (response.ok) {
        setMaskCol('');
        fetchMaskingRules();
      } else {
        const err = await response.json();
        alert(err.detail || 'Failed to add rule.');
      }
    } catch (e) { console.error(e); }
  };

  const handleDeleteMaskingRule = async (id: number) => {
    try {
      const response = await fetch(`/api/security/masking/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) fetchMaskingRules();
    } catch (e) { console.error(e); }
  };

  const handleAddRLSPolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rlsTable.trim() || !rlsFilter.trim()) return;
    try {
      const response = await fetch('/api/security/rls', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          table_name: rlsTable,
          filter_clause: rlsFilter,
          role: rlsRole
        })
      });
      if (response.ok) {
        setRlsTable('');
        setRlsFilter('');
        fetchRLSPolicies();
      } else {
        const err = await response.json();
        alert(err.detail || 'Failed to apply policy.');
      }
    } catch (e) { console.error(e); }
  };

  const handleDeleteRLSPolicy = async (id: number) => {
    try {
      const response = await fetch(`/api/security/rls/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) fetchRLSPolicies();
    } catch (e) { console.error(e); }
  };

  // --- Platform metrics API fetches ---
  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/monitoring/metrics', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) setMetrics(await response.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  // --- Custom roles API fetches ---
  const fetchCustomRoles = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/roles/', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) setCustomRoles(await response.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const handleCreateCustomRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!roleName.trim()) return;
    try {
      const response = await fetch('/api/roles/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          name: roleName,
          description: roleDesc,
          permissions: selectedPermissions
        })
      });
      if (response.ok) {
        setStatusMsg({ type: 'success', msg: 'Custom role created.' });
        setRoleName('');
        setRoleDesc('');
        setSelectedPermissions([]);
        fetchCustomRoles();
      } else {
        const err = await response.json();
        setStatusMsg({ type: 'error', msg: err.detail || 'Failed to create role.' });
      }
    } catch (e: any) { setStatusMsg({ type: 'error', msg: e.message }); }
  };

  const togglePermission = (perm: string) => {
    setSelectedPermissions(prev => 
      prev.includes(perm) ? prev.filter(p => p !== perm) : [...prev, perm]
    );
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
      
      {/* Subnavigation Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between px-6 py-4 bg-slate-850 border-b border-slate-800 gap-4">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-amber-500" />
          <h2 className="font-semibold text-slate-100 font-sans">Admin Control Center</h2>
        </div>

        <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800 self-start md:self-auto">
          {[
            { id: 'users', name: 'Users', icon: Users },
            { id: 'databases', name: 'Databases', icon: Database },
            { id: 'security', name: 'Security Rules', icon: ShieldAlert },
            { id: 'roles', name: 'Custom Roles', icon: Shield },
            { id: 'metrics', name: 'Monitoring', icon: Activity }
          ].map(tab => {
            const Icon = tab.icon;
            const isSelected = subTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setSubTab(tab.id as any)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium font-sans transition-all ${
                  isSelected ? 'bg-amber-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Panel */}
      <div className="flex-1 p-6 overflow-y-auto">
        
        {statusMsg && (
          <div className={`mb-6 p-4 rounded-xl text-xs font-sans flex items-center justify-between ${
            statusMsg.type === 'success' ? 'bg-green-950/20 border border-green-800/40 text-green-400' : 'bg-red-950/20 border border-red-800/40 text-red-400'
          }`}>
            <span>{statusMsg.msg}</span>
            <button onClick={() => setStatusMsg(null)} className="text-[10px] font-bold underline font-sans">Dismiss</button>
          </div>
        )}

        {/* 1. User Administration */}
        {subTab === 'users' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Create user block */}
            <div className="lg:col-span-1 bg-slate-950 border border-slate-805 p-5 rounded-xl space-y-4 self-start">
              <h4 className="text-xs font-semibold text-slate-350 uppercase tracking-wider font-sans border-b border-slate-800 pb-2">Manually Add User</h4>
              <form onSubmit={handleCreateUser} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-[10px] text-slate-400 block font-sans">Username</label>
                  <input
                    type="text"
                    required
                    value={newUsername}
                    onChange={e => setNewUsername(e.target.value)}
                    placeholder="john_doe"
                    className="w-full bg-slate-900 border border-slate-800 focus:border-amber-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none transition-all font-sans"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] text-slate-400 block font-sans">Password</label>
                  <input
                    type="password"
                    required
                    value={newUserPassword}
                    onChange={e => setNewUserPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-slate-900 border border-slate-800 focus:border-amber-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none transition-all font-sans"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] text-slate-400 block font-sans">Role Privilege</label>
                  <select
                    value={newUserRole}
                    onChange={e => setNewUserRole(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 focus:border-amber-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none cursor-pointer transition-all font-sans"
                  >
                    <option value="Admin">Admin</option>
                    <option value="Manager">Manager</option>
                    <option value="Analyst">Analyst</option>
                    <option value="Viewer">Viewer</option>
                  </select>
                </div>

                <button
                  type="submit"
                  className="w-full flex items-center justify-center gap-1.5 bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs py-2 px-4 rounded-lg transition-all shadow-md font-sans"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Register Account
                </button>
              </form>
            </div>

            {/* List users block */}
            <div className="lg:col-span-2 space-y-4">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-sans border-b border-slate-800 pb-2">Registered Workspace Users</h4>
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
                </div>
              ) : (
                <div className="border border-slate-805 rounded-xl overflow-hidden bg-slate-950">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-900 text-slate-400 border-b border-slate-800 font-sans">
                        <th className="p-3">Username</th>
                        <th className="p-3 text-center">Assigned Role</th>
                        <th className="p-3 text-center">Status</th>
                        <th className="p-3 text-center">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map(u => (
                        <tr key={u.id} className="border-b border-slate-850 hover:bg-slate-900/60 font-mono">
                          <td className="p-3 text-slate-200">{u.username}</td>
                          <td className="p-3 text-center">
                            <span className="inline-block px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px] text-amber-400 font-bold">
                              {u.role}
                            </span>
                          </td>
                          <td className="p-3 text-center font-sans">
                            <button
                              onClick={() => toggleUserActive(u)}
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border transition-all ${
                                u.is_active 
                                  ? 'bg-green-950/20 border-green-900/30 text-green-400' 
                                  : 'bg-red-950/20 border-red-900/30 text-red-400'
                              }`}
                            >
                              {u.is_active ? 'Active' : 'Disabled'}
                            </button>
                          </td>
                          <td className="p-3 text-center font-sans">
                            <div className="flex items-center justify-center gap-2">
                              <button
                                onClick={() => setResettingUserId(resettingUserId === u.id ? null : u.id)}
                                className="text-slate-400 hover:text-white p-1 hover:bg-slate-905 rounded transition-all"
                                title="Force password reset"
                              >
                                <Key className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleDeleteUser(u.id)}
                                className="text-slate-500 hover:text-red-400 p-1 hover:bg-slate-905 rounded transition-all"
                                title="Delete user"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                            
                            {resettingUserId === u.id && (
                              <div className="absolute bg-slate-900 border border-slate-800 p-3 rounded-lg mt-2 right-6 z-50 flex gap-2 shadow-2xl items-center">
                                <input
                                  type="text"
                                  placeholder="New password"
                                  value={resetPasswordVal}
                                  onChange={e => setResetPasswordVal(e.target.value)}
                                  className="bg-slate-950 border border-slate-800 rounded px-2 py-1 text-[11px] focus:outline-none w-36 font-mono"
                                />
                                <button
                                  onClick={() => handleResetPassword(u.id)}
                                  className="p-1 bg-amber-600 hover:bg-amber-500 text-white rounded text-[10px] font-bold"
                                >
                                  Save
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

          </div>
        )}

        {/* 2. Database Connections */}
        {subTab === 'databases' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Form */}
            <div className="lg:col-span-1 bg-slate-950 border border-slate-805 p-5 rounded-xl space-y-4 self-start">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-sans border-b border-slate-800 pb-2">Register Connection</h4>
              <form onSubmit={handleAddDatabase} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-[10px] text-slate-400 block font-sans">Database Name</label>
                  <input
                    type="text"
                    required
                    value={dbName}
                    onChange={e => setDbName(e.target.value)}
                    placeholder="Staging PostgreSQL"
                    className="w-full bg-slate-900 border border-slate-800 focus:border-amber-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none transition-all font-sans"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] text-slate-400 block font-sans">Provider Type</label>
                  <select
                    value={dbProvider}
                    onChange={e => setDbProvider(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 focus:border-amber-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none cursor-pointer transition-all font-sans"
                  >
                    <option value="postgresql">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                    <option value="oracle">Oracle</option>
                    <option value="mssql">SQL Server</option>
                    <option value="sqlite">SQLite</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] text-slate-400 block font-sans">SQL Connection String URL</label>
                  <textarea
                    required
                    value={dbUrl}
                    onChange={e => setDbUrl(e.target.value)}
                    placeholder="postgresql://user:pass@host:5432/dbname"
                    className="w-full bg-slate-900 border border-slate-800 focus:border-amber-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none h-20 resize-none font-mono"
                  />
                </div>

                <button
                  type="submit"
                  className="w-full flex items-center justify-center gap-1.5 bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs py-2 px-4 rounded-lg transition-all shadow-md font-sans"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Connect Database
                </button>
              </form>
            </div>

            {/* List */}
            <div className="lg:col-span-2 space-y-4">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-sans border-b border-slate-800 pb-2">Registered Infrastructure Data Targets</h4>
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {databases.map(db => (
                    <div key={db.id} className="bg-slate-950 border border-slate-805 p-4 rounded-xl space-y-3 relative group">
                      <div className="absolute top-0 left-0 w-1 h-full bg-amber-500"></div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-200 font-sans truncate pr-6">{db.name}</span>
                        <div className="flex items-center gap-1">
                          <button
                            disabled={testingDbId === db.id}
                            onClick={() => handleTestConnection(db.id)}
                            className="p-1 text-slate-400 hover:text-green-400 hover:bg-slate-900 rounded transition-all"
                            title="Test SQL connectivity"
                          >
                            {testingDbId === db.id ? (
                              <div className="w-3.5 h-3.5 border border-slate-400 border-t-transparent rounded-full animate-spin"></div>
                            ) : (
                              <Play className="w-3.5 h-3.5" />
                            )}
                          </button>
                          <button
                            onClick={() => handleDeleteDatabase(db.id)}
                            className="p-1 text-slate-500 hover:text-red-400 hover:bg-slate-900 rounded transition-all"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                      <div className="space-y-1">
                        <div className="text-[10px] text-slate-500 font-mono">Dialect: <span className="text-amber-400">{db.provider}</span></div>
                        <div className="text-[10px] text-slate-500 font-mono truncate" title={db.connection_url}>URL: {db.connection_url}</div>
                      </div>
                      
                      {testResult[db.id] && (
                        <div className={`mt-2 p-2 rounded text-[10px] font-sans flex items-start gap-1.5 ${
                          testResult[db.id].success ? 'bg-green-950/20 border border-green-900/30 text-green-400' : 'bg-red-950/20 border border-red-900/30 text-red-400'
                        }`}>
                          {testResult[db.id].success ? <Check className="w-3 h-3 flex-shrink-0 mt-0.5" /> : <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-0.5" />}
                          <span>{testResult[db.id].msg}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>
        )}

        {/* 3. Security Rules (RLS & Masking) */}
        {subTab === 'security' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            
            {/* Dynamic Column Masking Rules */}
            <div className="space-y-4">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-sans border-b border-slate-800 pb-2">Column Data Masking Rules</h4>
              
              <form onSubmit={handleAddMaskingRule} className="bg-slate-950 border border-slate-805 p-4 rounded-xl flex gap-3 items-end">
                <div className="flex-1 space-y-1">
                  <label className="text-[10px] text-slate-400 font-sans block">Column Target</label>
                  <input
                    type="text"
                    required
                    value={maskCol}
                    onChange={e => setMaskCol(e.target.value)}
                    placeholder="e.g. email, phone, ssn"
                    className="w-full bg-slate-900 border border-slate-800 focus:border-amber-500 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none transition-all font-mono"
                  />
                </div>
                <div className="flex-1 space-y-1">
                  <label className="text-[10px] text-slate-400 font-sans block">Mask Pattern</label>
                  <input
                    type="text"
                    required
                    value={maskPattern}
                    onChange={e => setMaskPattern(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 focus:border-amber-500 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none transition-all font-mono"
                  />
                </div>
                <button
                  type="submit"
                  className="bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs py-1.5 px-3.5 rounded transition-all shadow-md font-sans"
                >
                  Apply Mask
                </button>
              </form>

              <div className="border border-slate-805 rounded-xl overflow-hidden bg-slate-950">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-900 text-slate-400 border-b border-slate-805 font-sans">
                      <th className="p-3">Column Target</th>
                      <th className="p-3">Obfuscation Mask</th>
                      <th className="p-3 text-center">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {maskingRules.length === 0 ? (
                      <tr><td colSpan={3} className="p-6 text-center text-slate-500 italic">No masking rules configured.</td></tr>
                    ) : (
                      maskingRules.map(rule => (
                        <tr key={rule.id} className="border-b border-slate-850 hover:bg-slate-900/60 font-mono">
                          <td className="p-3 text-slate-300 font-bold">{rule.column_name}</td>
                          <td className="p-3 text-slate-400">{rule.masking_pattern}</td>
                          <td className="p-3 text-center font-sans">
                            <button
                              onClick={() => handleDeleteMaskingRule(rule.id)}
                              className="text-slate-500 hover:text-red-400 p-1 hover:bg-slate-900 rounded transition-all"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Row-Level Security Policies */}
            <div className="space-y-4">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-sans border-b border-slate-800 pb-2">Row-Level Security (RLS) Policies</h4>
              
              <form onSubmit={handleAddRLSPolicy} className="bg-slate-950 border border-slate-805 p-4 rounded-xl space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-400 font-sans block">Table Target</label>
                    <input
                      type="text"
                      required
                      value={rlsTable}
                      onChange={e => setRlsTable(e.target.value)}
                      placeholder="e.g. customers"
                      className="w-full bg-slate-900 border border-slate-800 focus:border-amber-500 rounded px-2 py-1 text-xs text-slate-200 focus:outline-none font-mono"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-400 font-sans block">Target Role</label>
                    <select
                      value={rlsRole}
                      onChange={e => setRlsRole(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 focus:border-amber-500 rounded px-2 py-1.5 text-xs text-slate-200 focus:outline-none cursor-pointer"
                    >
                      <option value="Analyst">Analyst</option>
                      <option value="Viewer">Viewer</option>
                      <option value="Manager">Manager</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-400 font-sans block">SQL filter (clause)</label>
                    <input
                      type="text"
                      required
                      value={rlsFilter}
                      onChange={e => setRlsFilter(e.target.value)}
                      placeholder="e.g. city = 'Mumbai'"
                      className="w-full bg-slate-900 border border-slate-805 focus:border-amber-500 rounded px-2 py-1 text-xs text-slate-200 focus:outline-none font-mono"
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  className="w-full bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs py-1.5 rounded transition-all shadow-md font-sans"
                >
                  Create AST Injection Rule
                </button>
              </form>

              <div className="border border-slate-805 rounded-xl overflow-hidden bg-slate-950">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-900 text-slate-400 border-b border-slate-805 font-sans">
                      <th className="p-3">Table</th>
                      <th className="p-3">Role</th>
                      <th className="p-3">Filter Clause</th>
                      <th className="p-3 text-center">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rlsPolicies.length === 0 ? (
                      <tr><td colSpan={4} className="p-6 text-center text-slate-500 italic">No RLS injection rules enforced.</td></tr>
                    ) : (
                      rlsPolicies.map(p => (
                        <tr key={p.id} className="border-b border-slate-850 hover:bg-slate-900/60 font-mono">
                          <td className="p-3 text-slate-350">{p.table_name}</td>
                          <td className="p-3 text-amber-500 font-sans font-bold">{p.role}</td>
                          <td className="p-3 text-slate-400">{p.filter_clause}</td>
                          <td className="p-3 text-center font-sans">
                            <button
                              onClick={() => handleDeleteRLSPolicy(p.id)}
                              className="text-slate-500 hover:text-red-400 p-1 hover:bg-slate-900 rounded transition-all"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        )}

        {/* 4. Custom Role Definitions */}
        {subTab === 'roles' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Create custom role */}
            <div className="lg:col-span-1 bg-slate-950 border border-slate-805 p-5 rounded-xl space-y-4 self-start">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-sans border-b border-slate-800 pb-2">Define Custom Role</h4>
              <form onSubmit={handleCreateCustomRole} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-[10px] text-slate-400 block font-sans">Role Name</label>
                  <input
                    type="text"
                    required
                    value={roleName}
                    onChange={e => setRoleName(e.target.value)}
                    placeholder="AuditManager"
                    className="w-full bg-slate-900 border border-slate-800 focus:border-amber-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none transition-all font-sans"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] text-slate-400 block font-sans">Description</label>
                  <textarea
                    required
                    value={roleDesc}
                    onChange={e => setRoleDesc(e.target.value)}
                    placeholder="Role to monitor query history and logs"
                    className="w-full bg-slate-900 border border-slate-800 focus:border-amber-500 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none h-16 resize-none transition-all font-sans"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-[10px] text-slate-400 block font-sans">Explicit Permissions</label>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto bg-slate-900 p-3 rounded-lg border border-slate-800">
                    {[
                      'view_audit_logs',
                      'view_reports',
                      'generate_sql',
                      'manage_databases',
                      'configure_masking',
                      'anomaly_detect'
                    ].map(perm => {
                      const selected = selectedPermissions.includes(perm);
                      return (
                        <button
                          type="button"
                          key={perm}
                          onClick={() => togglePermission(perm)}
                          className={`w-full text-left px-2 py-1 rounded text-[11px] font-mono flex items-center justify-between border ${
                            selected 
                              ? 'bg-amber-950/20 border-amber-900/40 text-amber-400 font-bold' 
                              : 'bg-slate-950 border-slate-850 text-slate-400'
                          }`}
                        >
                          <span>{perm}</span>
                          {selected && <Check className="w-3.5 h-3.5" />}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <button
                  type="submit"
                  className="w-full flex items-center justify-center gap-1.5 bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs py-2 px-4 rounded-lg transition-all shadow-md font-sans"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Establish Role
                </button>
              </form>
            </div>

            {/* Custom Roles List */}
            <div className="lg:col-span-2 space-y-4">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-sans border-b border-slate-800 pb-2">Active Configured Roles</h4>
              {loading ? (
                <div className="flex items-center justify-center py-6">
                  <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
                </div>
              ) : customRoles.length === 0 ? (
                <p className="text-xs text-slate-500 italic py-4">No custom role privileges established.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {customRoles.map(role => (
                    <div key={role.id} className="bg-slate-950 border border-slate-805 p-4 rounded-xl space-y-3 relative group">
                      <div className="absolute top-0 left-0 w-1 h-full bg-amber-500"></div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-200 font-sans truncate pr-6">{role.name}</span>
                      </div>
                      <p className="text-[11px] text-slate-400 font-sans leading-relaxed">{role.description}</p>
                      
                      <div className="space-y-1">
                        <div className="text-[10px] text-slate-500 font-bold font-sans uppercase">Permissions keys:</div>
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {role.permissions.map((perm, idx) => (
                            <span key={idx} className="inline-block px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-[9px] text-slate-400 font-mono">
                              {perm}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>
        )}

        {/* 5. Platform Metrics */}
        {subTab === 'metrics' && (
          <div className="space-y-6">
            <div className="bg-slate-950/40 border border-slate-805 rounded-xl p-5 space-y-2">
              <div className="flex items-center gap-1.5">
                <Activity className="w-4 h-4 text-amber-500" />
                <h3 className="text-sm font-semibold text-slate-200">Real-Time Performance Logs</h3>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed font-sans">
                Review key analytics related to total requests, database connection latency, query accuracy, and failures.
              </p>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
              </div>
            ) : metrics ? (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                
                <div className="bg-slate-950 border border-slate-805 p-5 rounded-xl space-y-2 relative overflow-hidden">
                  <div className="text-[10px] text-slate-500 uppercase font-bold tracking-wider font-sans">Total SQL Executions</div>
                  <div className="text-3xl font-extrabold text-white font-mono">{metrics.total_queries}</div>
                  <div className="absolute right-4 bottom-4 text-slate-800 opacity-20">
                    <Activity className="w-12 h-12" />
                  </div>
                </div>

                <div className="bg-slate-950 border border-slate-805 p-5 rounded-xl space-y-2 relative overflow-hidden">
                  <div className="text-[10px] text-slate-500 uppercase font-bold tracking-wider font-sans">Average Latency</div>
                  <div className="text-3xl font-extrabold text-amber-400 font-mono">{metrics.average_latency_ms} <span className="text-sm font-normal text-slate-400 font-sans">ms</span></div>
                  <div className="absolute right-4 bottom-4 text-slate-800 opacity-20">
                    <RefreshCw className="w-12 h-12 animate-spin-slow" />
                  </div>
                </div>

                <div className="bg-slate-950 border border-slate-805 p-5 rounded-xl space-y-2 relative overflow-hidden">
                  <div className="text-[10px] text-slate-500 uppercase font-bold tracking-wider font-sans">Query Accuracy Rate</div>
                  <div className="text-3xl font-extrabold text-green-400 font-mono">{metrics.accuracy_rate}%</div>
                  <div className="absolute right-4 bottom-4 text-slate-800 opacity-20">
                    <CheckCircle className="w-12 h-12" />
                  </div>
                </div>

                <div className="bg-slate-950 border border-slate-805 p-5 rounded-xl space-y-2 relative overflow-hidden">
                  <div className="text-[10px] text-slate-500 uppercase font-bold tracking-wider font-sans">Failed Query Interceptions</div>
                  <div className="text-3xl font-extrabold text-red-500 font-mono">{metrics.failed_queries}</div>
                  <div className="absolute right-4 bottom-4 text-slate-800 opacity-20">
                    <Ban className="w-12 h-12" />
                  </div>
                </div>

              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">Failed to retrieve monitoring logs.</p>
            )}
          </div>
        )}

      </div>
    </div>
  );
};
