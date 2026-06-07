import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Database, RefreshCw, Key, ArrowRight, Table, X, Eye } from 'lucide-react';
import { AgGridReact } from 'ag-grid-react';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

interface ColumnMeta {
  name: string;
  data_type: string;
  is_nullable: boolean;
  is_primary: boolean;
  is_foreign: boolean;
  foreign_key_table: string | null;
  foreign_key_column: string | null;
  description: string;
}

interface TableMeta {
  name: string;
  description: string;
  columns: ColumnMeta[];
  estimated_row_count: number;
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

export const SchemaVisualizer: React.FC = () => {
  const { token } = useAuth();
  const [schema, setSchema] = useState<TableMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Table preview states
  const [previewTable, setPreviewTable] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewData, setPreviewData] = useState<{ columns: string[], rows: any[], total_row_count?: number } | null>(null);

  const fetchTablePreview = async (tableName: string) => {
    setPreviewTable(tableName);
    setPreviewLoading(true);
    setPreviewData(null);
    try {
      const response = await fetch(`/api/schema/preview/${encodeURIComponent(tableName)}?limit=50`, {
        headers: {
          'Authorization': token ? `Bearer ${token}` : ''
        }
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to fetch table preview data.');
      }
      const data = await response.json();
      setPreviewData({
        columns: data.columns || [],
        rows: data.rows || [],
        total_row_count: data.total_row_count
      });
    } catch (e: any) {
      alert(e.message || 'Error loading table preview.');
      setPreviewTable(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const fetchSchema = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/schema/view', {
        headers: {
          'Authorization': token ? `Bearer ${token}` : ''
        }
      });
      if (!response.ok) {
        throw new Error('Failed to retrieve schema metadata.');
      }
      const data = await response.json();
      setSchema(data);
    } catch (e: any) {
      setError(e.message || 'Error loading schema.');
    } finally {
      setLoading(false);
    }
  };

  const syncSchema = async () => {
    setSyncing(true);
    try {
      const response = await fetch('/api/schema/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({})
      });
      if (!response.ok) {
        throw new Error('Failed to synchronize schema index.');
      }
      await fetchSchema();
      alert('Schema vector database successfully synchronized!');
    } catch (e: any) {
      alert(e.message || 'Sync failed.');
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    fetchSchema();
  }, []);

  return (
    <div className="space-y-6 h-full flex flex-col">
      {/* Title bar */}
      <div className="flex items-center justify-between px-6 py-4 bg-slate-900 border border-slate-800 rounded-xl">
        <div className="flex items-center gap-2">
          <Database className="w-5 h-5 text-brand-500" />
          <h2 className="text-base font-semibold text-slate-100 font-sans">Database Schema Visualizer</h2>
        </div>
        <button
          onClick={syncSchema}
          disabled={syncing || loading}
          className="flex items-center gap-1.5 px-4 py-2 bg-brand-600 hover:bg-brand-500 text-xs font-semibold text-white rounded-lg transition-all disabled:opacity-30"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
          Sync Schema RAG Index
        </button>
      </div>

      {loading ? (
        <div className="flex-1 flex flex-col items-center justify-center space-y-3">
          <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
          <span className="text-xs text-slate-400 font-sans">Loading database metadata...</span>
        </div>
      ) : error ? (
        <div className="p-4 rounded-xl bg-red-950/20 border border-red-800/50 text-xs text-red-400 font-mono">
          {error}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto pr-1">
          {schema.length === 0 ? (
            <div className="text-center text-slate-500 text-sm py-12">
              No schema information found in target database.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {schema.map((table) => (
                <div 
                  key={table.name}
                  className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg flex flex-col hover:border-slate-700 transition-all"
                >
                  {/* Card Header */}
                  <div className="px-5 py-4 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <Table className="w-4 h-4 text-brand-500 flex-shrink-0" />
                      <span className="font-semibold text-slate-200 text-sm font-sans truncate">{table.name}</span>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => fetchTablePreview(table.name)}
                        className="p-1 rounded bg-slate-850 hover:bg-slate-700 text-slate-400 hover:text-slate-100 transition-all border border-slate-800 cursor-pointer"
                        title="Preview Table Data"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                      <span className="text-[10px] text-slate-400 font-mono px-2 py-0.5 bg-slate-950 rounded-full border border-slate-850">
                        {table.estimated_row_count} rows
                      </span>
                    </div>
                  </div>

                  {/* Card Body Column Fields list */}
                  <div className="p-5 flex-1 space-y-4">
                    {table.description && (
                      <p className="text-[11px] text-slate-400 leading-normal italic font-sans">
                        {table.description}
                      </p>
                    )}
                    
                    <div className="space-y-2.5">
                      {table.columns.map((col) => (
                        <div 
                          key={col.name}
                          className="flex flex-col border-b border-slate-850/50 pb-2 last:border-0 last:pb-0"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                              {col.is_primary && (
                                <span title="Primary Key">
                                  <Key className="w-3 h-3 text-amber-500" />
                                </span>
                              )}
                              <span className={`text-xs font-medium ${col.is_primary ? 'text-slate-100' : 'text-slate-300'} font-mono`}>
                                {col.name}
                              </span>
                            </div>
                            <span className="text-[10px] text-slate-505 font-mono">
                              {col.data_type}
                            </span>
                          </div>
                          
                          {/* FK references */}
                          {col.is_foreign && (
                            <div className="flex items-center gap-1 text-[9px] text-brand-500 mt-0.5 font-mono">
                              <ArrowRight className="w-2.5 h-2.5" />
                              <span>FK to {col.foreign_key_table}({col.foreign_key_column})</span>
                            </div>
                          )}
                          
                          {/* Column Descriptions */}
                          {col.description && col.description !== `Column ${col.name} of type ${col.data_type}` && (
                            <span className="text-[9px] text-slate-500 leading-normal mt-0.5 font-sans">
                              {col.description}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Table Preview Modal */}
      {previewTable && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-6">
          <div className="w-full max-w-5xl bg-slate-900 border border-slate-800 rounded-xl shadow-2xl flex flex-col h-[500px]">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 bg-slate-850 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Database className="w-5 h-5 text-brand-500" />
                <h3 className="font-semibold text-slate-100 font-sans">
                  Data Preview: <span className="font-mono text-brand-400">{previewTable}</span> (First 50 Rows)
                </h3>
              </div>
              <button 
                onClick={() => setPreviewTable(null)}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-all cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 p-6 overflow-hidden flex flex-col">
              {previewLoading ? (
                <div className="flex-1 flex flex-col items-center justify-center space-y-3">
                  <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
                  <span className="text-xs text-slate-400 font-sans">Loading data preview...</span>
                </div>
              ) : previewData ? (
                <div className="flex-1 flex flex-col space-y-2 overflow-hidden">
                  <div className="ag-theme-alpine-dark w-full flex-1 min-h-[300px]">
                    <AgGridReact
                      columnDefs={previewData.columns.map(col => ({
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
                      rowData={previewData.rows}
                      pagination={true}
                      paginationPageSize={10}
                      icons={gridIcons}
                    />
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono text-right">
                    Total loaded: {previewData.rows.length} records
                  </div>
                </div>
              ) : (
                <div className="text-center text-slate-500 py-12">
                  No preview records returned.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
