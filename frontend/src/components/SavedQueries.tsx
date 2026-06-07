import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { BookOpen, Trash2, Edit3, Copy, Check, ChevronDown, ChevronUp } from 'lucide-react';

interface SavedQuery {
  id: number;
  user_id: number;
  title: string;
  question: string;
  sql_query: string;
  description: string | null;
  created_at: string;
}

export const SavedQueries: React.FC = () => {
  const { token, user } = useAuth();
  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Edit states
  const [editingQuery, setEditingQuery] = useState<SavedQuery | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editError, setEditError] = useState<string | null>(null);

  const fetchSaved = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/saved/', {
        headers: {
          'Authorization': token ? `Bearer ${token}` : ''
        }
      });
      if (!response.ok) {
        throw new Error('Failed to retrieve saved query templates.');
      }
      const data = await response.json();
      setSavedQueries(data);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSaved();
  }, []);

  const handleCopy = (sql: string, id: number) => {
    navigator.clipboard.writeText(sql);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this query template?")) return;
    try {
      const response = await fetch(`/api/saved/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': token ? `Bearer ${token}` : ''
        }
      });
      if (response.ok) {
        setSavedQueries(prev => prev.filter(q => q.id !== id));
      } else {
        const err = await response.json();
        throw new Error(err.detail || 'Delete operation failed.');
      }
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleEditClick = (q: SavedQuery) => {
    setEditingQuery(q);
    setEditTitle(q.title);
    setEditDescription(q.description || '');
    setEditError(null);
  };

  const handleEditSubmit = async () => {
    if (!editingQuery || !editTitle.trim()) return;
    try {
      const response = await fetch(`/api/saved/${editingQuery.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({
          title: editTitle,
          question: editingQuery.question,
          sql_query: editingQuery.sql_query,
          description: editDescription
        })
      });
      if (response.ok) {
        const updated = await response.json();
        setSavedQueries(prev => prev.map(q => q.id === editingQuery.id ? updated : q));
        setEditingQuery(null);
      } else {
        const err = await response.json();
        throw new Error(err.detail || 'Edit operation failed.');
      }
    } catch (e: any) {
      setEditError(e.message);
    }
  };

  // Ownership validator
  const canModify = (q: SavedQuery): boolean => {
    if (!user) return false;
    if (user.role === 'Admin' || user.role === 'Manager') return true;
    return user.role === 'Analyst' && q.user_id === q.user_id; // backend verifies exact ownership
  };

  return (
    <div className="space-y-6 h-full flex flex-col">
      {/* Title block */}
      <div className="flex items-center justify-between px-6 py-4 bg-slate-900 border border-slate-800 rounded-xl">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-brand-500" />
          <h2 className="text-base font-semibold text-slate-100 font-sans">Saved Queries Library</h2>
        </div>
      </div>

      {loading ? (
        <div className="flex-1 flex flex-col items-center justify-center space-y-3">
          <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
          <span className="text-xs text-slate-400 font-sans">Loading saved queries...</span>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          {savedQueries.length === 0 ? (
            <div className="text-center text-slate-500 text-sm py-12">
              No saved query templates in library.
            </div>
          ) : (
            savedQueries.map(q => (
              <div 
                key={q.id}
                className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow hover:border-slate-750 transition-all"
              >
                {/* Header Row */}
                <div 
                  onClick={() => setExpandedId(prev => prev === q.id ? null : q.id)}
                  className="px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-slate-850/30 transition-all"
                >
                  <div className="space-y-0.5 flex-1 min-w-0 pr-4">
                    <h3 className="text-xs font-semibold text-slate-200 truncate font-sans">{q.title}</h3>
                    <p className="text-[10px] text-slate-400 truncate italic font-sans font-medium">"{q.question}"</p>
                  </div>
                  
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCopy(q.sql_query, q.id);
                      }}
                      className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-all"
                      title="Copy SQL"
                    >
                      {copiedId === q.id ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                    
                    {canModify(q) && (
                      <>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleEditClick(q);
                          }}
                          className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-amber-500 transition-all"
                          title="Edit Template"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(q.id);
                          }}
                          className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-red-500 transition-all"
                          title="Delete Template"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                    
                    <span className="ml-2 text-slate-500">
                      {expandedId === q.id ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </span>
                  </div>
                </div>

                {/* Expanded DDL/Description */}
                {expandedId === q.id && (
                  <div className="px-5 pb-5 border-t border-slate-850/60 pt-4 space-y-3 bg-slate-950/20">
                    {q.description && (
                      <p className="text-xs text-slate-400 leading-normal font-sans">
                        {q.description}
                      </p>
                    )}
                    <div className="space-y-1">
                      <span className="text-[10px] font-semibold text-slate-400 font-sans block">SQL Statement:</span>
                      <pre className="p-3.5 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-brand-500 overflow-x-auto">
                        <code>{q.sql_query}</code>
                      </pre>
                    </div>
                    <div className="text-[9px] text-slate-500 font-mono">
                      Owner User ID: {q.user_id} • Created: {new Date(q.created_at).toLocaleDateString()}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Edit modal */}
      {editingQuery && (
        <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-6">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 p-6 rounded-xl shadow-2xl space-y-4">
            <h3 className="font-semibold text-slate-100 font-sans">Edit Query Template</h3>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 font-sans">Title</label>
                <input 
                  type="text" 
                  value={editTitle} 
                  onChange={e => setEditTitle(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 font-sans">Description (Optional)</label>
                <textarea 
                  value={editDescription} 
                  onChange={e => setEditDescription(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-brand-500 h-24 resize-none"
                />
              </div>
            </div>
            {editError && <p className="text-xs text-red-500">{editError}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <button 
                onClick={() => setEditingQuery(null)}
                className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 rounded font-sans"
              >
                Cancel
              </button>
              <button 
                onClick={handleEditSubmit}
                className="px-3 py-2 bg-brand-600 hover:bg-brand-500 text-xs text-white rounded font-sans"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
