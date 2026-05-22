import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import type { Patient, PatientCreate } from '../types';
import { Card, Spinner, Empty } from '../components/ui';
import { Plus, Search, X, Copy, Check, Link2, RefreshCw, CloudDownload } from 'lucide-react';

export default function PatientsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [showFhir, setShowFhir] = useState(false);
  const [intakeLink, setIntakeLink] = useState<{ token: string; patientName: string } | null>(null);

  const { data: patients, isLoading } = useQuery<Patient[]>({
    queryKey: ['patients', search],
    queryFn: () =>
      api.get('/patients/', { params: search ? { search } : {} }).then((r) => r.data),
  });

  return (
    <div className="space-y-4 animate-in">
      <div className="flex items-center justify-between">
        <h1 className="text-[22px] font-bold text-[#111] dark:text-white">Patients</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFhir(true)}
            className="inline-flex items-center gap-1.5 h-7 px-2.5 bg-[#f5f5f5] dark:bg-white/5 text-[#555] dark:text-gray-300 rounded-md text-[11px] font-medium hover:bg-[#eee] dark:hover:bg-white/10 transition-colors"
          >
            <CloudDownload className="h-3 w-3" /> FHIR Import
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-1.5 h-7 px-2.5 bg-[#111] dark:bg-white dark:text-black text-white rounded-md text-[11px] font-medium hover:bg-[#222] dark:hover:bg-gray-200 transition-colors"
          >
            <Plus className="h-3 w-3" /> Add Patient
          </button>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#bbb] dark:text-gray-500" />
        <input
          type="text"
          placeholder="Search by MRN, name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-xs pl-8 pr-3 h-8 text-[11px] border border-[#e5e5e5] dark:border-white/10 bg-[#fafafa] dark:bg-[#0d1117] dark:text-white dark:placeholder:text-gray-500 rounded-md focus:bg-white dark:focus:bg-[#0d1117] focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/20 outline-none transition-all"
        />
      </div>

      {isLoading ? (
        <Spinner />
      ) : !patients?.length ? (
        <Empty message="No patients found" />
      ) : (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#fafafa] dark:bg-white/[0.02] text-[#aaa] dark:text-gray-500 text-left text-[10px] uppercase tracking-wider">
              <tr>
                <th className="px-4 py-2 font-medium">MRN</th>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">DOB</th>
                <th className="px-4 py-2 font-medium">Gender</th>
                <th className="px-4 py-2 font-medium">Payer</th>
                <th className="px-4 py-2 font-medium">Intake Link</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-white/5">
              {patients.map((p) => (
                <tr key={p.id} className="hover:bg-[#fafafa] dark:hover:bg-white/[0.03] transition-colors">
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => window.location.href = `/patients/${p.id}`}
                      className="font-mono text-[10px] text-emerald-600 font-semibold hover:underline"
                    >
                      {p.mrn}
                    </button>
                  </td>
                  <td className="px-4 py-2.5 font-medium text-gray-900 dark:text-white">{p.first_name} {p.last_name}</td>
                  <td className="px-4 py-2.5 text-gray-600 dark:text-gray-300">{new Date(p.date_of_birth).toLocaleDateString()}</td>
                  <td className="px-4 py-2.5 capitalize text-gray-600 dark:text-gray-300">{p.gender}</td>
                  <td className="px-4 py-2.5 text-gray-600 dark:text-gray-300">{p.payer_name || p.payer_id}</td>
                  <td className="px-4 py-2.5">
                    <IntakeLinkCell patient={p} onRefresh={() => qc.invalidateQueries({ queryKey: ['patients'] })} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {showCreate && (
        <CreatePatientModal
          onClose={() => setShowCreate(false)}
          onCreated={(token, name) => {
            setShowCreate(false);
            qc.invalidateQueries({ queryKey: ['patients'] });
            if (token) setIntakeLink({ token, patientName: name });
          }}
        />
      )}

      {showFhir && (
        <FHIRImportModal
          onClose={() => setShowFhir(false)}
          onImported={(token, name) => {
            setShowFhir(false);
            qc.invalidateQueries({ queryKey: ['patients'] });
            if (token) setIntakeLink({ token, patientName: name });
          }}
        />
      )}

      {intakeLink && (
        <IntakeLinkModal
          token={intakeLink.token}
          patientName={intakeLink.patientName}
          onClose={() => setIntakeLink(null)}
        />
      )}
    </div>
  );
}

function CreatePatientModal({ onClose, onCreated }: { onClose: () => void; onCreated: (token: string | null, name: string) => void }) {
  const [form, setForm] = useState<PatientCreate>({
    mrn: '',
    first_name: '',
    last_name: '',
    date_of_birth: '',
    gender: 'male',
    payer_id: '',
    payer_name: '',
  });
  // MRN is auto-generated on the backend if left empty
  const [error, setError] = useState('');

  const { data: payers } = useQuery<{ payer_id: string; name: string }[]>({
    queryKey: ['payers'],
    queryFn: () => api.get('/payers/').then((r) => r.data.items ?? r.data),
  });

  const mutation = useMutation({
    mutationFn: (data: PatientCreate) => api.post('/patients/', data),
    onSuccess: (res) => {
      const token = res.data?.intake_token || null;
      onCreated(token, `${form.first_name} ${form.last_name}`);
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') setError(detail);
      else if (Array.isArray(detail)) setError(detail.map((d: any) => d.msg).join(', '));
      else setError('Failed to create patient');
    },
  });

  const handle = (field: keyof PatientCreate, value: string) =>
    setForm((f) => ({ ...f, [field]: value }));

  const handlePayerChange = (payerId: string) => {
    const payer = payers?.find((p) => p.payer_id === payerId);
    setForm((f) => ({ ...f, payer_id: payerId, payer_name: payer?.name || '' }));
  };

  const inputCls = 'w-full h-8 px-2.5 text-sm border border-gray-300 dark:border-white/10 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none dark:bg-[#0d1117] dark:text-white dark:placeholder:text-gray-500';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-[2px]">
      <div className="bg-white dark:bg-[#161b22] rounded-lg shadow-lg border dark:border-white/10 w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto animate-in">
        <div className="flex items-center justify-between px-5 py-3 border-b dark:border-white/5">
          <h2 className="text-sm font-semibold dark:text-white">Add Patient</h2>
          <button onClick={onClose} className="p-0.5 hover:bg-gray-100 dark:hover:bg-white/5 rounded-md"><X className="h-4 w-4 text-gray-500 dark:text-gray-400" /></button>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate({
              ...form,
              date_of_birth: new Date(form.date_of_birth).toISOString(),
            });
          }}
          className="p-5 space-y-4"
        >
          {error && <div className="bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 text-sm px-3 py-2 rounded-md">{error}</div>}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Gender</label>
              <select value={form.gender} onChange={(e) => handle('gender', e.target.value)} className={inputCls}>
                <option value="male">male</option>
                <option value="female">female</option>
                <option value="other">other</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">First Name</label>
              <input required value={form.first_name} onChange={(e) => handle('first_name', e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Last Name</label>
              <input required value={form.last_name} onChange={(e) => handle('last_name', e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Date of Birth</label>
              <input type="date" required value={form.date_of_birth} onChange={(e) => handle('date_of_birth', e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Payer</label>
              <select required value={form.payer_id} onChange={(e) => handlePayerChange(e.target.value)} className={inputCls}>
                <option value="">Select payer…</option>
                {payers?.map((p) => (
                  <option key={p.payer_id} value={p.payer_id}>{p.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="h-8 px-3 rounded-md border dark:border-white/10 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors">Cancel</button>
            <button type="submit" disabled={mutation.isPending} className="h-8 px-4 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
              {mutation.isPending ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function IntakeLinkModal({ token, patientName, onClose }: { token: string; patientName: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const link = `${window.location.origin}/intake/${token}`;

  const copyLink = () => {
    navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-[2px]">
      <div className="bg-white dark:bg-[#161b22] rounded-lg shadow-lg border dark:border-white/10 w-full max-w-lg mx-4 animate-in">
        <div className="flex items-center justify-between px-5 py-3 border-b dark:border-white/5">
          <div className="flex items-center gap-2">
            <Link2 className="h-4 w-4 text-blue-600" />
            <h2 className="text-sm font-semibold dark:text-white">Patient Intake Link</h2>
          </div>
          <button onClick={onClose} className="p-0.5 hover:bg-gray-100 dark:hover:bg-white/5 rounded-md"><X className="h-4 w-4 text-gray-500 dark:text-gray-400" /></button>
        </div>
        <div className="p-5 space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-300">
            Share this link with <strong className="dark:text-white">{patientName}</strong> to allow them to upload medical documents for prior authorization.
          </p>
          <div className="flex items-center gap-2">
            <input
              readOnly
              value={link}
              className="flex-1 h-9 px-3 text-xs font-mono bg-gray-50 dark:bg-[#0d1117] border border-gray-200 dark:border-white/10 rounded-md text-gray-700 dark:text-gray-300"
              onClick={(e) => (e.target as HTMLInputElement).select()}
            />
            <button
              onClick={copyLink}
              className="inline-flex items-center gap-1.5 h-9 px-3 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              {copied ? <><Check className="h-3.5 w-3.5" /> Copied</> : <><Copy className="h-3.5 w-3.5" /> Copy</>}
            </button>
          </div>
          <p className="text-xs text-gray-400 dark:text-gray-500">This link expires in 7 days. You can regenerate it from the patients list.</p>
        </div>
      </div>
    </div>
  );
}

function FHIRImportModal({ onClose, onImported }: { onClose: () => void; onImported: (token: string | null, name: string) => void }) {
  const [mode, setMode] = useState<'id' | 'mrn'>('mrn');
  const [fhirId, setFhirId] = useState('');
  const [mrn, setMrn] = useState('');
  const [payerId, setPayerId] = useState('');
  const [payerName, setPayerName] = useState('');
  const [error, setError] = useState('');

  const mutation = useMutation({
    mutationFn: (data: any) => api.post('/patients/import-fhir', data),
    onSuccess: (res) => {
      const token = res.data?.intake_token || null;
      const name = `${res.data?.first_name || ''} ${res.data?.last_name || ''}`.trim();
      onImported(token, name);
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'FHIR import failed');
    },
  });

  const inputCls = 'w-full h-8 px-2.5 text-sm border border-gray-300 dark:border-white/10 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none dark:bg-[#0d1117] dark:text-white dark:placeholder:text-gray-500';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-[2px]">
      <div className="bg-white dark:bg-[#161b22] rounded-lg shadow-lg border dark:border-white/10 w-full max-w-md mx-4 animate-in">
        <div className="flex items-center justify-between px-5 py-3 border-b dark:border-white/5">
          <div className="flex items-center gap-2">
            <CloudDownload className="h-4 w-4 text-blue-600" />
            <h2 className="text-sm font-semibold dark:text-white">Import Patient from FHIR</h2>
          </div>
          <button onClick={onClose} className="p-0.5 hover:bg-gray-100 dark:hover:bg-white/5 rounded-md"><X className="h-4 w-4 text-gray-500 dark:text-gray-400" /></button>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setError('');
            const payload: any = { payer_id: payerId, payer_name: payerName };
            if (mode === 'id') payload.fhir_patient_id = fhirId;
            else payload.mrn = mrn;
            mutation.mutate(payload);
          }}
          className="p-5 space-y-4"
        >
          {error && <div className="bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 text-sm px-3 py-2 rounded-md">{error}</div>}

          <div className="flex gap-2 text-xs">
            <button type="button" onClick={() => setMode('mrn')}
              className={`px-3 py-1.5 rounded-md font-medium transition-colors ${mode === 'mrn' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400' : 'bg-gray-100 dark:bg-white/5 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-white/10'}`}>
              Search by MRN
            </button>
            <button type="button" onClick={() => setMode('id')}
              className={`px-3 py-1.5 rounded-md font-medium transition-colors ${mode === 'id' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400' : 'bg-gray-100 dark:bg-white/5 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-white/10'}`}>
              By FHIR Patient ID
            </button>
          </div>

          {mode === 'mrn' ? (
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Patient MRN</label>
              <input required value={mrn} onChange={(e) => setMrn(e.target.value)} placeholder="e.g. MRN-12345" className={inputCls} />
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">FHIR Patient ID</label>
              <input required value={fhirId} onChange={(e) => setFhirId(e.target.value)} placeholder="e.g. 12345" className={inputCls} />
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Payer ID</label>
              <input required value={payerId} onChange={(e) => setPayerId(e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">Payer Name</label>
              <input value={payerName} onChange={(e) => setPayerName(e.target.value)} className={inputCls} />
            </div>
          </div>

          <p className="text-xs text-gray-400 dark:text-gray-500">Patient demographics will be pulled from the configured FHIR server and an intake link generated automatically.</p>

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="h-8 px-3 rounded-md border dark:border-white/10 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors">Cancel</button>
            <button type="submit" disabled={mutation.isPending} className="h-8 px-4 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
              {mutation.isPending ? 'Importing…' : 'Import'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function IntakeLinkCell({ patient, onRefresh }: { patient: Patient; onRefresh: () => void }) {
  const [copied, setCopied] = useState(false);

  const generateMutation = useMutation({
    mutationFn: () => api.post(`/patients/${patient.id}/intake-link`),
    onSuccess: () => onRefresh(),
  });

  if (patient.intake_token) {
    const link = `${window.location.origin}/intake/${patient.intake_token}`;

    const copy = () => {
      navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    };

    return (
      <div className="flex items-center gap-1.5">
        <button
          onClick={copy}
          title={copied ? 'Copied!' : 'Copy intake link'}
          className={`inline-flex items-center gap-1 h-7 px-2 rounded-md text-xs font-medium transition-colors ${
            copied
              ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400'
              : 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/30'
          }`}
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? 'Copied' : 'Copy Link'}
        </button>
        <button
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
          title="Regenerate link"
          className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3 w-3 ${generateMutation.isPending ? 'animate-spin' : ''}`} />
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={() => generateMutation.mutate()}
      disabled={generateMutation.isPending}
      className="inline-flex items-center gap-1 h-7 px-2 text-xs text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-md transition-colors disabled:opacity-50"
    >
      {generateMutation.isPending ? (
        <RefreshCw className="h-3 w-3 animate-spin" />
      ) : (
        <Link2 className="h-3 w-3" />
      )}
      Generate Link
    </button>
  );
}
