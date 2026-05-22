import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { Card, Spinner, StatusBadge, Empty } from '../components/ui';
import type { Appeal } from '../types';
import { ChevronDown, ChevronRight, Download, Edit3, Save, X, User, Calendar, FileText, Scale } from 'lucide-react';

export default function AppealsPage() {
  const qc = useQueryClient();
  const { data: appeals, isLoading } = useQuery({
    queryKey: ['appeals'],
    queryFn: async () => {
      const res = await api.get('/appeals/');
      return res.data as Appeal[];
    },
  });

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');

  const saveMutation = useMutation({
    mutationFn: ({ id, letter }: { id: string; letter: string }) =>
      api.patch(`/appeals/${id}/letter`, { appeal_letter: letter }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['appeals'] });
      setEditingId(null);
    },
  });

  const downloadPdf = async (appealId: string) => {
    try {
      const res = await api.get(`/appeals/${appealId}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `appeal_letter_${appealId.slice(0, 8)}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Failed to download PDF');
    }
  };

  if (isLoading) return <Spinner />;

  return (
    <div className="space-y-4 animate-in">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Scale className="h-4 w-4 text-emerald-600" />
          <h1 className="text-[22px] font-bold text-[#111] dark:text-white">Appeals</h1>
        </div>
        <span className="text-[10px] text-[#888] dark:text-gray-400 font-mono">{appeals?.length || 0} total</span>
      </div>

      {!appeals?.length ? (
        <Empty message="No appeals found" />
      ) : (
        <div className="space-y-3">
          {appeals.map((appeal) => {
            const open = expandedId === appeal.id;
            const isEditing = editingId === appeal.id;
            return (
              <Card key={appeal.id} className="overflow-hidden">
                {/* Header row */}
                <button
                  className="w-full flex items-center gap-3 px-4 py-3.5 text-left hover:bg-[#fafafa] dark:hover:bg-white/[0.03] transition-colors"
                  onClick={() => setExpandedId(open ? null : appeal.id)}
                >
                  {open ? <ChevronDown className="h-3 w-3 text-[#999] dark:text-gray-500 shrink-0" /> : <ChevronRight className="h-3 w-3 text-[#999] dark:text-gray-500 shrink-0" />}

                  {/* Patient info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-[12px] font-bold text-[#111] dark:text-white">
                        {appeal.patient_name || 'Unknown Patient'}
                      </span>
                      <StatusBadge status={appeal.status as any} />
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-[#888] dark:text-gray-400">
                      <span className="font-mono">{appeal.patient_mrn || '—'}</span>
                      <span>•</span>
                      <span>CPT: <strong className="text-[#555] dark:text-gray-300">{appeal.cpt_code || '—'}</strong></span>
                      <span>•</span>
                      <span>{appeal.payer_name || '—'}</span>
                      <span>•</span>
                      <span>Attempt #{appeal.attempt_number}</span>
                    </div>
                  </div>

                  {/* Right side */}
                  <div className="text-right shrink-0">
                    <p className="text-[10px] font-medium text-[#555] dark:text-gray-300 capitalize">
                      {appeal.denial_reason?.replace(/_/g, ' ') || 'Unknown'}
                    </p>
                    <p className="text-[9px] text-[#aaa] dark:text-gray-500 flex items-center gap-1 justify-end mt-0.5">
                      <Calendar className="h-2.5 w-2.5" />
                      {new Date(appeal.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </button>

                {/* Expanded content */}
                {open && (
                  <div className="px-4 pb-4 pt-2 border-t border-[#f0f0f0] dark:border-white/5 space-y-4 animate-in">
                    {/* Patient details bar */}
                    <div className="flex items-center gap-4 p-2.5 bg-[#f8f8f8] dark:bg-white/5 rounded-md">
                      <div className="flex items-center gap-1.5">
                        <User className="h-3 w-3 text-[#bbb] dark:text-gray-500" />
                        <span className="text-[9px] text-[#999] dark:text-gray-500">PATIENT:</span>
                        <span className="text-[10px] font-bold text-[#333] dark:text-gray-200">{appeal.patient_name || '—'}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[9px] text-[#999] dark:text-gray-500">MRN:</span>
                        <span className="text-[10px] font-mono font-medium text-[#333] dark:text-gray-200">{appeal.patient_mrn || '—'}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[9px] text-[#999] dark:text-gray-500">GENERATED:</span>
                        <span className="text-[10px] font-medium text-[#333] dark:text-gray-200">{new Date(appeal.created_at).toLocaleString()}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[9px] text-[#999] dark:text-gray-500">PA ID:</span>
                        <span className="text-[10px] font-mono text-emerald-600">{appeal.prior_auth_id.slice(0, 8)}</span>
                      </div>
                    </div>

                    {/* Denial details */}
                    {appeal.denial_details && (
                      <div>
                        <p className="text-[9px] font-bold text-[#999] dark:text-gray-500 uppercase tracking-wider mb-1">DENIAL DETAILS</p>
                        <p className="text-[11px] text-[#555] dark:text-gray-300 p-2.5 bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-700/30 rounded-md">{appeal.denial_details}</p>
                      </div>
                    )}

                    {/* Appeal Letter */}
                    {appeal.appeal_letter && (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-1.5">
                            <FileText className="h-3 w-3 text-emerald-600" />
                            <p className="text-[9px] font-bold text-[#999] dark:text-gray-500 uppercase tracking-wider">APPEAL LETTER</p>
                          </div>
                          <div className="flex items-center gap-1.5">
                            {!isEditing ? (
                              <>
                                <button
                                  onClick={(e) => { e.stopPropagation(); setEditingId(appeal.id); setEditText(appeal.appeal_letter || ''); }}
                                  className="inline-flex items-center gap-1 h-6 px-2 text-[9px] font-bold text-[#666] dark:text-gray-300 bg-[#f0f0f0] dark:bg-white/5 rounded hover:bg-[#e5e5e5] dark:hover:bg-white/10 transition-colors"
                                >
                                  <Edit3 className="h-2.5 w-2.5" /> EDIT
                                </button>
                                <button
                                  onClick={(e) => { e.stopPropagation(); downloadPdf(appeal.id); }}
                                  className="inline-flex items-center gap-1 h-6 px-2 text-[9px] font-bold text-white bg-emerald-600 rounded hover:bg-emerald-700 transition-colors"
                                >
                                  <Download className="h-2.5 w-2.5" /> DOWNLOAD PDF
                                </button>
                              </>
                            ) : (
                              <>
                                <button
                                  onClick={(e) => { e.stopPropagation(); saveMutation.mutate({ id: appeal.id, letter: editText }); }}
                                  disabled={saveMutation.isPending}
                                  className="inline-flex items-center gap-1 h-6 px-2 text-[9px] font-bold text-white bg-[#111] dark:bg-white dark:text-black rounded hover:bg-[#222] dark:hover:bg-gray-200 transition-colors disabled:opacity-50"
                                >
                                  <Save className="h-2.5 w-2.5" /> SAVE
                                </button>
                                <button
                                  onClick={(e) => { e.stopPropagation(); setEditingId(null); }}
                                  className="inline-flex items-center gap-1 h-6 px-2 text-[9px] font-bold text-[#666] dark:text-gray-300 bg-[#f0f0f0] dark:bg-white/5 rounded hover:bg-[#e5e5e5] dark:hover:bg-white/10 transition-colors"
                                >
                                  <X className="h-2.5 w-2.5" /> CANCEL
                                </button>
                              </>
                            )}
                          </div>
                        </div>

                        {isEditing ? (
                          <textarea
                            value={editText}
                            onChange={(e) => setEditText(e.target.value)}
                            className="w-full h-80 p-3 bg-white dark:bg-[#0d1117] border border-[#ddd] dark:border-white/10 rounded-md text-[11px] text-[#333] dark:text-gray-200 font-mono leading-relaxed resize-y focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/20 outline-none"
                          />
                        ) : (
                          <div className="p-4 bg-white dark:bg-[#0d1117] border border-[#eee] dark:border-white/5 rounded-md text-[11px] text-[#333] dark:text-gray-200 whitespace-pre-wrap max-h-96 overflow-y-auto leading-[1.7] shadow-inner">
                            {appeal.appeal_letter}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Cited References */}
                    {appeal.cited_references && appeal.cited_references.length > 0 && (
                      <div>
                        <p className="text-[9px] font-bold text-[#999] dark:text-gray-500 uppercase tracking-wider mb-1.5">CITED REFERENCES</p>
                        <div className="space-y-1.5">
                          {appeal.cited_references.map((ref: any, i: number) => (
                            <div key={i} className="flex gap-2 text-[10px] text-[#555] dark:text-gray-300 p-2.5 bg-[#fafafa] dark:bg-white/[0.02] border border-[#eee] dark:border-white/5 rounded-md">
                              <span className="text-[#bbb] dark:text-gray-600 font-mono font-bold shrink-0">[{i + 1}]</span>
                              <div>
                                <p className="font-medium text-[#333] dark:text-gray-200">{ref.citation || JSON.stringify(ref)}</p>
                                {ref.relevance && <p className="text-[#888] dark:text-gray-400 mt-0.5 italic">{ref.relevance}</p>}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Additional Evidence */}
                    {appeal.additional_evidence && appeal.additional_evidence.length > 0 && (
                      <div>
                        <p className="text-[9px] font-bold text-[#999] dark:text-gray-500 uppercase tracking-wider mb-1.5">ADDITIONAL EVIDENCE NEEDED</p>
                        <div className="space-y-1.5">
                          {appeal.additional_evidence.map((ev: any, i: number) => (
                            <div key={i} className="text-[10px] p-2.5 bg-orange-50 dark:bg-orange-900/20 border border-orange-100 dark:border-orange-700/30 rounded-md">
                              <p className="font-bold text-orange-700 dark:text-orange-400">{ev.type || JSON.stringify(ev)}</p>
                              {ev.rationale && <p className="text-orange-600 dark:text-orange-300 mt-0.5">{ev.rationale}</p>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Timestamps */}
                    <div className="flex gap-4 text-[9px] text-[#aaa] dark:text-gray-500 pt-2 border-t border-[#f5f5f5] dark:border-white/5">
                      <span>GENERATED: {new Date(appeal.created_at).toLocaleString()}</span>
                      {appeal.submitted_at && <span>SUBMITTED: {new Date(appeal.submitted_at).toLocaleString()}</span>}
                      {appeal.response_at && <span>RESPONSE: {new Date(appeal.response_at).toLocaleString()}</span>}
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
