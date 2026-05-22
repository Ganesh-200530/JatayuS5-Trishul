import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import api from '../api';
import type { PriorAuthList, PriorAuthCreate, Patient, PayerPolicy } from '../types';
import { Card, Spinner, StatusBadge, UrgencyBadge, ConfidenceMeter, Empty } from '../components/ui';
import OcrUpload from '../components/OcrUpload';
import { Plus, Search, X, AlertCircle } from 'lucide-react';

export default function PriorAuthListPage() {
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '');
  const [reviewFilter, setReviewFilter] = useState(searchParams.get('review') === 'true');
  const [showCreate, setShowCreate] = useState(false);
  const qc = useQueryClient();

  useEffect(() => {
    const s = searchParams.get('status');
    const r = searchParams.get('review');
    if (s) setStatusFilter(s);
    if (r === 'true') setReviewFilter(true);
  }, [searchParams]);

  const { data: pas, isLoading } = useQuery<PriorAuthList[]>({
    queryKey: ['prior-auth', statusFilter, reviewFilter],
    queryFn: () => {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      if (reviewFilter) params.requires_review = 'true';
      return api.get('/prior-auth/', { params }).then((r) => r.data);
    },
    refetchInterval: 15000,
  });

  const filtered = pas?.filter(
    (p) =>
      !search ||
      p.id.includes(search) ||
      p.cpt_code.includes(search) ||
      p.payer_id.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-4 animate-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold text-[#111] dark:text-white">Prior Auth Requests</h1>
          <p className="text-[11px] text-[#888] dark:text-gray-400">{pas?.length ?? 0} total requests</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-1.5 h-7 px-2.5 bg-[#111] dark:bg-white dark:text-black text-white rounded-md text-[11px] font-medium hover:bg-[#222] dark:hover:bg-gray-200 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" /> New Request
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search ID, CPT, payer…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-8 pl-8 pr-3 text-sm border border-gray-300 dark:border-white/10 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-[#0d1117] dark:text-white dark:placeholder:text-gray-500"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-8 px-2 text-sm border border-gray-300 dark:border-white/10 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-[#0d1117] dark:text-white"
        >
          <option value="">All statuses</option>
          {['initiated','clinical_review','policy_check','submission_ready','submitted','pending_decision','approved','denied','appeal_in_progress','escalated','cancelled'].map((s) => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <button
          onClick={() => setReviewFilter(!reviewFilter)}
          className={`inline-flex items-center gap-1 h-8 px-2.5 text-sm rounded-md border transition-colors ${
            reviewFilter
              ? 'bg-orange-50 dark:bg-orange-900/20 text-orange-700 dark:text-orange-400 border-orange-300 dark:border-orange-700/30'
              : 'text-gray-600 dark:text-gray-300 border-gray-300 dark:border-white/10 hover:bg-gray-50 dark:hover:bg-white/[0.03]'
          }`}
        >
          <AlertCircle className="h-3.5 w-3.5" />
          Review
        </button>
      </div>

      {/* Table */}
      {isLoading ? (
        <Spinner />
      ) : filtered && filtered.length > 0 ? (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[10px] text-[#aaa] dark:text-gray-500 uppercase tracking-wider border-b border-[#f0f0f0] dark:border-white/5">
                <th className="px-4 py-2.5 font-medium">ID</th>
                <th className="px-4 py-2.5 font-medium">PATIENT</th>
                <th className="px-4 py-2.5 font-medium">CPT</th>
                <th className="px-4 py-2.5 font-medium">PAYER</th>
                <th className="px-4 py-2.5 font-medium">STATUS</th>
                <th className="px-4 py-2.5 font-medium">CONFIDENCE</th>
                <th className="px-4 py-2.5 font-medium">REVIEW</th>
                <th className="px-4 py-2.5 font-medium">CREATED</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#f8f8f8] dark:divide-white/5">
              {filtered.map((pa) => (
                <tr key={pa.id} className="hover:bg-[#fafafa] dark:hover:bg-white/[0.03] transition-colors">
                  <td className="px-4 py-2.5">
                    <Link to={`/prior-auth/${pa.id}`} className="text-emerald-600 hover:underline font-mono text-[10px] font-medium">
                      {pa.id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-[11px] font-medium text-[#333] dark:text-gray-200">{pa.patient_name || '—'}</td>
                  <td className="px-4 py-2.5 text-[11px] font-semibold text-[#111] dark:text-white">{pa.cpt_code}</td>
                  <td className="px-4 py-2.5 text-[11px] text-[#666] dark:text-gray-300">{pa.payer_id}</td>
                  <td className="px-4 py-2.5"><StatusBadge status={pa.status} /></td>
                  <td className="px-4 py-2.5"><ConfidenceMeter score={pa.confidence_score} /></td>
                  <td className="px-4 py-2.5">
                    {pa.requires_human_review && (
                      <span className="inline-flex items-center gap-1 text-[10px] text-orange-600 dark:text-orange-400 font-medium">
                        <AlertCircle className="h-3 w-3" /> Yes
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-[10px] text-[#999] dark:text-gray-500">{new Date(pa.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : (
        <Card><Empty message="No requests match your filters" /></Card>
      )}

      {showCreate && (
        <CreatePAModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); qc.invalidateQueries({ queryKey: ['prior-auth'] }); }}
        />
      )}
    </div>
  );
}

/* ── Create Modal ─────────────────────────────────────────── */

function CreatePAModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const navigate = useNavigate();
  const [error, setError] = useState('');

  const { data: patients } = useQuery<Patient[]>({
    queryKey: ['patients'],
    queryFn: () => api.get('/patients/').then((r) => r.data),
  });

  const { data: policies } = useQuery<PayerPolicy[]>({
    queryKey: ['policies'],
    queryFn: () => api.get('/policies/').then((r) => r.data),
  });

  const [form, setForm] = useState<PriorAuthCreate>({
    patient_id: '',
    cpt_code: '',
    cpt_description: '',
    icd10_codes: [],
    ordering_provider_npi: '',
    ordering_provider_name: '',
    facility_npi: '',
    facility_name: '',
    payer_id: '',
    payer_name: '',
    urgency: 'standard',
    clinical_notes: '',
  });

  const handlePolicyChange = (policyId: string) => {
    const pol = policies?.find((p) => p.id === policyId);
    if (pol) {
      setForm((f) => ({
        ...f,
        cpt_code: pol.cpt_code,
        cpt_description: pol.cpt_description || '',
        payer_id: pol.payer_id,
        payer_name: pol.payer_name,
      }));
    }
  };

  const handlePatientChange = (patientId: string) => {
    const pat = patients?.find((p) => p.id === patientId);
    setForm((f) => ({
      ...f,
      patient_id: patientId,
      payer_id: pat?.payer_id || '',
      payer_name: pat?.payer_name || '',
      cpt_code: '',
      cpt_description: '',
    }));
  };


  const mutation = useMutation({
    mutationFn: (data: PriorAuthCreate) => api.post('/prior-auth/', data),
    onSuccess: (res) => { onCreated(); navigate(`/prior-auth/${res.data.id}`); },
    onError: (err: any) => setError(err.response?.data?.detail || 'Failed to create'),
  });

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const inputCls = 'w-full h-8 px-2.5 text-sm border border-gray-300 dark:border-white/10 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-[#0d1117] dark:text-white dark:placeholder:text-gray-500';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-[2px]">
      <div className="bg-white dark:bg-[#161b22] rounded-lg shadow-lg w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto border border-gray-200 dark:border-white/10">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 dark:border-white/5">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">New Prior Auth Request</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-white/5 rounded-md"><X className="h-4 w-4 text-gray-500 dark:text-gray-400" /></button>
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); mutation.mutate(form); }}
          className="p-5 space-y-4"
        >
          {error && <div className="rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700/30 px-3 py-2 text-sm text-red-700 dark:text-red-400">{error}</div>}

          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Patient</label>
            <select required value={form.patient_id} onChange={(e) => handlePatientChange(e.target.value)} className={inputCls}>
              <option value="">Select patient…</option>
              {patients?.map((p) => <option key={p.id} value={p.id}>{p.first_name} {p.last_name} ({p.mrn})</option>)}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Payer</label>
              <input disabled value={form.payer_name || ''} className={inputCls + ' bg-gray-50 dark:bg-white/5 text-gray-500 dark:text-gray-400'} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Urgency</label>
              <select value={form.urgency} onChange={(e) => set('urgency', e.target.value)} className={inputCls}>
                <option value="standard">Standard</option>
                <option value="urgent">Urgent</option>
                <option value="emergent">Emergent</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Provider Name</label>
              <input value={form.ordering_provider_name} onChange={(e) => set('ordering_provider_name', e.target.value)} className={inputCls} placeholder="Dr. Sharma" />
            </div>
          </div>

          <OcrUpload onExtracted={(text) => set('clinical_notes', text)} />

          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Clinical Notes</label>
            <textarea
              rows={6}
              value={form.clinical_notes}
              onChange={(e) => set('clinical_notes', e.target.value)}
              className="w-full px-2.5 py-2 text-sm border border-gray-300 dark:border-white/10 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y dark:bg-[#0d1117] dark:text-white dark:placeholder:text-gray-500"
              placeholder="Paste clinical progress note here. AI will extract evidence and check policy automatically."
            />
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="h-8 px-3 text-sm rounded-md border border-gray-300 dark:border-white/10 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={mutation.isPending} className="h-7 px-3 text-[11px] bg-[#111] dark:bg-white dark:text-black text-white rounded-md font-medium hover:bg-[#222] dark:hover:bg-gray-200 disabled:opacity-50 transition-colors">
              {mutation.isPending ? 'Submitting…' : 'Submit'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
