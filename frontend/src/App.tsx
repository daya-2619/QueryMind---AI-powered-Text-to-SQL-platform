import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ChatConsole } from './components/ChatConsole';
import { QueryHistory } from './components/QueryHistory';
import { SavedQueries } from './components/SavedQueries';
import { SchemaVisualizer } from './components/SchemaVisualizer';
import { ViewerDashboard } from './components/ViewerDashboard';
import { ManagerConsole } from './components/ManagerConsole';
import { AdminConsole } from './components/AdminConsole';
import { AIDashboardGen } from './components/AIDashboardGen';
import { 
  Terminal, 
  BookOpen, 
  Database, 
  LogOut, 
  User as UserIcon, 
  Shield, 
  Activity,
  Sparkles,
  Lock,
  UserPlus,
  BarChart4
} from 'lucide-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient();

// Secondary component to consume Auth context
const DashboardContent: React.FC = () => {
  const { isAuthenticated, user, logout, login, register, loading } = useAuth();
  const [activeTab, setActiveTab] = useState<
    'console' | 'history' | 'library' | 'schema' | 'viewer-dashboard' | 'manager' | 'admin' | 'ai-dashboard'
  >('console');

  useEffect(() => {
    if (user) {
      if (user.role === 'Viewer') {
        setActiveTab('viewer-dashboard');
      } else {
        setActiveTab('console');
      }
    }
  }, [user]);
  
  // Login / Register Form States
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'Admin' | 'Manager' | 'Analyst' | 'Viewer'>('Analyst');
  const [authError, setAuthError] = useState<string | null>(null);
  const [authSuccess, setAuthSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    setAuthSuccess(null);
    if (username.length < 3) {
      setAuthError('Username must be at least 3 characters.');
      return;
    }
    if (password.length < 6) {
      setAuthError('Password must be at least 6 characters.');
      return;
    }
    
    setSubmitting(true);
    try {
      if (isRegister) {
        await register(username, password, role);
        setAuthSuccess('Account registered successfully! You can now sign in.');
        setIsRegister(false);
        setPassword('');
      } else {
        await login(username, password);
      }
    } catch (err: any) {
      setAuthError(err.message || 'Authentication operation failed.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center space-y-4">
        <div className="w-12 h-12 border-4 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-sm text-slate-400 font-sans tracking-wide">Initializing secure secure console...</p>
      </div>
    );
  }

  // Not authenticated: render premium authentication screen
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 relative overflow-hidden">
        {/* Abstract decorative ambient background blobs */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-brand-500/10 rounded-full blur-[120px] pointer-events-none"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-[120px] pointer-events-none"></div>
        
        <div className="w-full max-w-md z-10 space-y-8">
          {/* Logo Branding */}
          <div className="text-center space-y-2">
            <div className="inline-flex p-3 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl">
              <Sparkles className="w-8 h-8 text-brand-500 animate-pulse-slow" />
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white font-sans bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-200 to-slate-400">
              QueryMind 
              
            </h1>
            <p className="text-xs md:text-sm text-slate-400 font-sans">
              Enterprise Conversational Analytics Platform
            </p>
          </div>

          {/* Authentication Card */}
          <div className="bg-slate-900/60 backdrop-blur-md border border-slate-800/80 shadow-2xl p-8 rounded-2xl space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <h2 className="text-base font-semibold text-slate-200 font-sans">
                {isRegister ? 'Create Workspace Account' : 'Sign In to Workspace'}
              </h2>
              <button
                onClick={() => {
                  setIsRegister(!isRegister);
                  setAuthError(null);
                  setAuthSuccess(null);
                }}
                className="text-xs text-brand-500 hover:text-brand-400 transition-colors font-medium flex items-center gap-1 font-sans"
              >
                {isRegister ? (
                  <>
                    <Lock className="w-3 h-3" /> Already registered?
                  </>
                ) : (
                  <>
                    <UserPlus className="w-3 h-3" /> Need an account?
                  </>
                )}
              </button>
            </div>

            {authError && (
              <div className="p-3 bg-red-950/20 border border-red-800/40 text-xs text-red-400 rounded-lg font-mono">
                {authError}
              </div>
            )}

            {authSuccess && (
              <div className="p-3 bg-green-950/20 border border-green-800/40 text-xs text-green-400 rounded-lg font-sans">
                {authSuccess}
              </div>
            )}

            <form onSubmit={handleAuthSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] uppercase font-bold tracking-wider text-slate-400 block font-sans">
                  Username
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-500">
                    <UserIcon className="w-4 h-4" />
                  </span>
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Enter username"
                    className="w-full bg-slate-950/80 border border-slate-800 focus:border-brand-500 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500/20 transition-all font-sans"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase font-bold tracking-wider text-slate-400 block font-sans">
                  Password
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-500">
                    <Lock className="w-4 h-4" />
                  </span>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter password"
                    className="w-full bg-slate-950/80 border border-slate-800 focus:border-brand-500 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500/20 transition-all font-sans"
                  />
                </div>
              </div>

              {isRegister && (
                <div className="space-y-1">
                  <label className="text-[10px] uppercase font-bold tracking-wider text-slate-400 block font-sans">
                    Assigned Role
                  </label>
                  <div className="relative">
                    <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-500">
                      <Shield className="w-4 h-4" />
                    </span>
                    <select
                      value={role}
                      onChange={(e) => setRole(e.target.value as any)}
                      className="w-full bg-slate-950/80 border border-slate-800 focus:border-brand-500 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-200 focus:outline-none cursor-pointer transition-all font-sans"
                    >
                      <option value="Admin">Admin (Full Control)</option>
                      <option value="Manager">Manager (Edit Libraries)</option>
                      <option value="Analyst">Analyst (Run queries)</option>
                      <option value="Viewer">Viewer (Read logs only)</option>
                    </select>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-1 italic font-sans leading-relaxed">
                    * Viewer role blocks natural language to SQL query executions.
                  </p>
                </div>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="w-full bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-semibold text-sm py-2 px-4 rounded-lg transition-all shadow-lg shadow-brand-900/10 flex items-center justify-center gap-2 font-sans mt-2"
              >
                {submitting && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>}
                {isRegister ? 'Register Account' : 'Authenticate'}
              </button>
            </form>
          </div>
          
          <div className="text-center">
            <span className="text-[10px] text-slate-600 font-mono">
              Secured Session • v1.0.0 Stable
            </span>
          </div>
        </div>
      </div>
    );
  }

  // Define role color mapping for tags
  const getRoleColor = (role: string) => {
    switch (role) {
      case 'Admin': return 'text-amber-400 bg-amber-400/10 border-amber-400/20';
      case 'Manager': return 'text-purple-400 bg-purple-400/10 border-purple-400/20';
      case 'Analyst': return 'text-blue-400 bg-blue-400/10 border-blue-400/20';
      default: return 'text-slate-400 bg-slate-400/10 border-slate-400/20';
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      
      {/* Top Navigation Header */}
      <header className="sticky top-0 z-40 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 px-6 py-4 flex items-center justify-between shadow-md">
        
        {/* Branding & Logo */}
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-slate-950 border border-slate-800 rounded-lg shadow-inner">
            <Sparkles className="w-4.5 h-4.5 text-brand-500 animate-pulse-slow" />
          </div>
          <div>
            <h1 className="font-bold text-sm tracking-tight text-white font-sans">
              QueryMind
            </h1>
            <p className="text-[10px] text-slate-400 flex items-center gap-1 font-sans">
              <Activity className="w-3 h-3 text-brand-500" />
              Active DB: <span className="font-mono text-brand-500 font-medium">sample_ecommerce.db</span>
            </p>
          </div>
        </div>

        {/* User Card Badge & Controls */}
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-3 bg-slate-950/60 border border-slate-800 px-3.5 py-1.5 rounded-xl">
            <div className="p-1 rounded bg-slate-800 text-slate-400">
              <UserIcon className="w-3.5 h-3.5" />
            </div>
            <div className="text-left leading-tight">
              <p className="text-xs font-semibold text-slate-200 font-sans">{user?.username}</p>
              <span className={`inline-block text-[9px] font-bold px-1.5 py-0.5 rounded border mt-0.5 ${getRoleColor(user?.role || '')}`}>
                {user?.role}
              </span>
            </div>
          </div>

          <button
            onClick={logout}
            className="flex items-center justify-center p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-red-400 hover:border-red-500/30 transition-all shadow-inner"
            title="Log Out of Session"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Workspace Panel layout */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Side Tab Navigation */}
        <aside className="w-16 md:w-56 bg-slate-900 border-r border-slate-850/60 flex flex-col py-4 px-2 md:px-3.5 space-y-2">
          {(() => {
            const tabs = [];
            if (user?.role === 'Viewer') {
              tabs.push({ id: 'viewer-dashboard', name: 'Insight Dashboard', icon: BarChart4 });
            } else {
              tabs.push({ id: 'console', name: 'Query Console', icon: Terminal });
              tabs.push({ id: 'schema', name: 'Schema Explorer', icon: Database });
              tabs.push({ id: 'library', name: 'Saved Queries', icon: BookOpen });
              tabs.push({ id: 'ai-dashboard', name: 'AI Dashboard Gen', icon: Sparkles });
              
              if (user?.role === 'Manager' || user?.role === 'Admin') {
                tabs.push({ id: 'manager', name: 'Manager Console', icon: Activity });
              }
              if (user?.role === 'Admin') {
                tabs.push({ id: 'admin', name: 'Admin Control', icon: Shield });
              }
            }
            
            return tabs.map((tab) => {
              const IconComponent = tab.icon;
              const isSelected = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`w-full flex items-center justify-center md:justify-start gap-3 px-3 py-2.5 rounded-xl transition-all font-medium text-xs font-sans group relative ${
                    isSelected 
                      ? 'bg-brand-600 text-white shadow-lg shadow-brand-900/10' 
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850/50'
                  }`}
                >
                  <IconComponent className={`w-4 h-4 flex-shrink-0 transition-transform group-hover:scale-105 ${isSelected ? 'text-white' : 'text-slate-400 group-hover:text-brand-500'}`} />
                  <span className="hidden md:inline">{tab.name}</span>
                  
                  {/* Tooltip for mobile sidebar hover */}
                  <span className="absolute left-16 bg-slate-900 border border-slate-800 px-2 py-1 rounded-md text-[10px] text-slate-200 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none md:hidden z-50 shadow-md">
                    {tab.name}
                  </span>
                </button>
              );
            });
          })()}
        </aside>

        {/* Right Content Workspace Container */}
        <main className="flex-1 overflow-hidden p-6 relative bg-slate-950">
          <div className="h-full w-full max-w-7xl mx-auto flex flex-col">
            {activeTab === 'console' && <ChatConsole />}
            {activeTab === 'history' && <QueryHistory />}
            {activeTab === 'library' && <SavedQueries />}
            {activeTab === 'schema' && <SchemaVisualizer />}
            {activeTab === 'viewer-dashboard' && <ViewerDashboard />}
            {activeTab === 'manager' && <ManagerConsole />}
            {activeTab === 'admin' && <AdminConsole />}
            {activeTab === 'ai-dashboard' && <AIDashboardGen />}
          </div>
        </main>
      </div>
    </div>
  );
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <DashboardContent />
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
