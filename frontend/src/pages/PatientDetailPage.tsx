import { useState, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import type { Patient, PriorAuthList } from '../types';
import { Card, Spinner, StatusBadge, ConfidenceMeter, Empty } from '../components/ui';
import { ArrowLeft, User, Calendar, Shield, FileCheck, Brain, CheckCircle, XCircle, Upload, FileText, X, Loader2 } from 'lucide-react';

export default function PatientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: patient, isLoading } = useQuery<Patient>({
    queryKey: ['patient', id],
    queryFn: () => api.get(`/patients/${id}`).then((r) => r.data),
  });

  const { data: allPAs, refetch: refetchPAs } = useQuery<PriorAuthList[]>({
    queryKey: ['prior-auth'],
    queryFn: () => api.get('/prior-auth/').then((r) => r.data),
  });

  // Filter PAs for this patient
  const patientPAs = allPAs?.filter((pa) => pa.patient_id === id) || [];

  if (isLoading) return <Spinner />;
  if (!patient) return <Empty message="Patient not found" />;

  return (
    <div className="space-y-5 animate-in">
      {/* Back */}
      <button onClick={() => navigate('/patients')} className="flex items-center gap-1.5 text-[11px] text-[#888] hover:text-[#111] transition-colors">
        <ArrowLeft className="h-3 w-3" /> Back to Patients
      </button>

      {/* Patient Header */}
      <Card className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-[#111] flex items-center justify-center text-white font-bold text-[12px]">
              {patient.first_name?.charAt(0)}{patient.last_name?.charAt(0)}
            </div>
            <div>
              <h1 className="text-[15px] font-bold text-[#111]">{patient.first_name} {patient.last_name}</h1>
              <p className="text-[11px] text-[#888] font-mono">{patient.mrn}</p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <span className="text-[10px] font-bold text-emerald-600">Active</span>
          </div>
        </div>
      </Card>

      {/* Patient Info Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
        <Card className="p-3">
          <div className="flex items-center gap-2 mb-1.5">
            <Calendar className="h-3 w-3 text-[#bbb]" />
            <span className="text-[9px] font-bold text-[#999] uppercase tracking-wider">DOB</span>
          </div>
          <p className="text-[12px] font-semibold text-[#111]">{new Date(patient.date_of_birth).toLocaleDateString()}</p>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2 mb-1.5">
            <User className="h-3 w-3 text-[#bbb]" />
            <span className="text-[9px] font-bold text-[#999] uppercase tracking-wider">Gender</span>
          </div>
          <p className="text-[12px] font-semibold text-[#111] capitalize">{patient.gender}</p>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2 mb-1.5">
            <Shield className="h-3 w-3 text-[#bbb]" />
            <span className="text-[9px] font-bold text-[#999] uppercase tracking-wider">Payer</span>
          </div>
          <p className="text-[12px] font-semibold text-[#111]">{patient.payer_name || patient.payer_id || '—'}</p>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2 mb-1.5">
            <FileCheck className="h-3 w-3 text-[#bbb]" />
            <span className="text-[9px] font-bold text-[#999] uppercase tracking-wider">PA Requests</span>
          </div>
          <p className="text-[12px] font-semibold text-[#111] font-mono">{patientPAs.length}</p>
        </Card>
      </div>

      {/* Admin Document Upload */}
      <AdminDocUpload patientId={id!} patientName={`${patient.first_name} ${patient.last_name}`} onUploaded={() => refetchPAs()} />

      {/* AI Processing History */}
      <Card className="overflow-hidden">
        <div className="px-4 py-3 border-b border-[#f0f0f0] flex items-center gap-2">
          <Brain className="h-3.5 w-3.5 text-emerald-600" />
          <h2 className="text-[11px] font-bold text-[#111] uppercase tracking-wide">AI Processing History</h2>
        </div>

        {patientPAs.length > 0 ? (
          <table className="w-full">
            <thead>
              <tr className="text-left text-[10px] text-[#aaa] uppercase tracking-wider border-b border-[#f5f5f5]">
                <th className="px-4 py-2 font-medium">Request ID</th>
                <th className="px-4 py-2 font-medium">CPT Code</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">AI Confidence</th>
                <th className="px-4 py-2 font-medium">AI Processed</th>
                <th className="px-4 py-2 font-medium">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#f8f8f8]">
              {patientPAs.map((pa) => {
                const aiProcessed = pa.status !== 'initiated' && pa.status !== 'intake_received';
                return (
                  <tr
                    key={pa.id}
                    className="hover:bg-[#fafafa] cursor-pointer transition-colors"
                    onClick={() => navigate(`/prior-auth/${pa.id}`)}
                  >
                    <td className="px-4 py-2.5 font-mono text-[10px] text-emerald-600 font-medium">{pa.id.slice(0, 8)}</td>
                    <td className="px-4 py-2.5 text-[11px] font-semibold text-[#333]">{pa.cpt_code}</td>
                    <td className="px-4 py-2.5"><StatusBadge status={pa.status} /></td>
                    <td className="px-4 py-2.5"><ConfidenceMeter score={pa.confidence_score} /></td>
                    <td className="px-4 py-2.5">
                      {aiProcessed ? (
                        <span className="inline-flex items-center gap-1 text-[9px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">
                          <CheckCircle className="h-2.5 w-2.5" /> Yes
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[9px] font-bold text-[#999] bg-[#f5f5f5] px-1.5 py-0.5 rounded">
                          <XCircle className="h-2.5 w-2.5" /> Pending
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-[10px] text-[#999]">{new Date(pa.created_at).toLocaleDateString()}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div className="p-6 text-center">
            <p className="text-[11px] text-[#aaa]">No prior authorization requests for this patient yet.</p>
          </div>
        )}
      </Card>
    </div>
  );
}

/* ── Admin Document Upload Component ──────────────────────── */

function AdminDocUpload({ patientId, patientName, onUploaded }: { patientId: string; patientName: string; onUploaded: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string; refId?: string } | null>(null);
  const [validationResults, setValidationResults] = useState<Record<number, { ok: boolean; message: string; patientMatch?: string }>>({});
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const handleFiles = async (newFiles: FileList | null) => {
    if (!newFiles) return;
    const added = Array.from(newFiles);
    const startIdx = files.length;
    setFiles((prev) => [...prev, ...added]);
    setResult(null);

    // Validate each file
    setValidating(true);
    for (let i = 0; i < added.length; i++) {
      const f = added[i];
      const formData = new FormData();
      formData.append('file', f);
      formData.append('patient_name', patientName);
      // patient DOB would be passed if available

      try {
        const res = await api.post('/ocr/validate', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 30000,
        });
        const d = res.data;
        const idx = startIdx + i;

        if (!d.is_medical) {
          // Check if it's a patient mismatch (document is medical but wrong patient)
          if (d.patient_match?.status === 'mismatch') {
            setValidationResults((prev) => ({
              ...prev,
              [idx]: {
                ok: false,
                message: `PATIENT MISMATCH: Document belongs to "${d.patient_match.document_patient_name || 'another patient'}" — expected "${patientName}". ${d.patient_match.reason || ''}`,
                patientMatch: 'mismatch',
              },
            }));
          } else {
            setValidationResults((prev) => ({
              ...prev,
              [idx]: { ok: false, message: d.message || 'Not a medical document.' },
            }));
          }
        } else if (d.patient_match?.status === 'mismatch') {
          setValidationResults((prev) => ({
            ...prev,
            [idx]: {
              ok: false,
              message: `Patient mismatch: ${d.patient_match.reason}. Document shows "${d.patient_match.document_patient_name || 'unknown'}" but expected "${patientName}".`,
              patientMatch: 'mismatch',
            },
          }));
        } else {
          setValidationResults((prev) => ({
            ...prev,
            [idx]: { ok: true, message: d.message || 'Valid medical document.', patientMatch: d.patient_match?.status },
          }));
        }
      } catch {
        const idx = startIdx + i;
        setValidationResults((prev) => ({
          ...prev,
          [idx]: { ok: true, message: 'Accepted (validation unavailable).' },
        }));
      }
    }
    setValidating(false);
  };

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
    setValidationResults((prev) => {
      const next = { ...prev };
      delete next[idx];
      return next;
    });
  };

  // Only allow upload if all files passed validation
  const allValid = files.length > 0 && files.every((_, i) => validationResults[i]?.ok !== false);

  const upload = async () => {
    if (!files.length) return;
    setUploading(true);
    setResult(null);

    try {
      // First generate an intake link for admin upload
      const linkRes = await api.post(`/patients/${patientId}/intake-link`);
      const token = linkRes.data.intake_token;

      // Submit documents via the intake endpoint (same as patient would)
      const formData = new FormData();
      files.forEach((f) => formData.append('documents', f));

      const submitRes = await api.post(`/intake/${token}/submit`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
      });

      setResult({
        success: true,
        message: `${files.length} document(s) uploaded and processed successfully.`,
        refId: submitRes.data.reference_id,
      });
      setFiles([]);
      onUploaded();
    } catch (err: any) {
      setResult({
        success: false,
        message: err.response?.data?.detail || 'Upload failed. Please try again.',
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-3">
        <Upload className="h-3.5 w-3.5 text-emerald-600" />
        <h2 className="text-[11px] font-bold text-[#111] uppercase tracking-wide">UPLOAD DOCUMENTS (ADMIN)</h2>
      </div>
      <p className="text-[10px] text-[#888] mb-3">
        Upload medical documents on behalf of <strong>{patientName}</strong>. Documents will be validated, OCR'd, and a PA request created.
      </p>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
        onClick={() => inputRef.current?.click()}
        className={`border border-dashed rounded-md p-4 text-center cursor-pointer transition-all ${
          dragOver ? 'border-emerald-400 bg-emerald-50/50' : 'border-[#ddd] hover:border-[#bbb] hover:bg-[#fafafa]'
        }`}
      >
        <Upload className="h-4 w-4 text-[#bbb] mx-auto mb-1" />
        <p className="text-[11px] text-[#666]">
          Drop files here or <span className="text-emerald-600 font-semibold">browse</span>
        </p>
        <p className="text-[9px] text-[#aaa] mt-0.5">PDF, JPG, PNG — max 10 MB each</p>
        <input
          ref={inputRef}
          type="file"
          accept="image/*,.pdf"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {files.map((f, i) => {
            const v = validationResults[i];
            return (
              <div key={i} className={`px-2.5 py-2 rounded-md border ${
                v?.ok === false ? 'bg-red-50 border-red-200' : v?.ok === true ? 'bg-emerald-50/50 border-emerald-100' : 'bg-[#f8f8f8] border-[#eee]'
              }`}>
                <div className="flex items-center gap-2">
                  <FileText className={`h-3 w-3 ${v?.ok === false ? 'text-red-500' : v?.ok === true ? 'text-emerald-500' : 'text-[#999]'}`} />
                  <span className="flex-1 text-[10px] font-medium text-[#333] truncate">{f.name}</span>
                  <span className="text-[9px] text-[#aaa]">{(f.size / 1024).toFixed(0)} KB</span>
                  <button onClick={() => removeFile(i)} className="p-0.5 hover:bg-[#eee] rounded">
                    <X className="h-2.5 w-2.5 text-[#999]" />
                  </button>
                </div>
                {v && (
                  <p className={`mt-1 text-[9px] font-medium ${v.ok ? 'text-emerald-600' : 'text-red-600'}`}>
                    {v.ok ? '✓ ' : '✗ '}{v.message}
                  </p>
                )}
              </div>
            );
          })}

          {validating && (
            <div className="flex items-center gap-1.5 px-2 py-1.5 text-[10px] text-[#888]">
              <Loader2 className="h-3 w-3 animate-spin" /> Validating documents...
            </div>
          )}

          <button
            onClick={upload}
            disabled={uploading || !allValid || validating}
            className="w-full h-8 bg-[#111] text-white rounded-md text-[11px] font-semibold hover:bg-[#222] disabled:opacity-50 transition-all flex items-center justify-center gap-1.5 mt-2"
          >
            {uploading ? (
              <><Loader2 className="h-3 w-3 animate-spin" /> Processing documents...</>
            ) : !allValid ? (
              <>Remove rejected files to continue</>
            ) : (
              <><Upload className="h-3 w-3" /> Upload & Process ({files.filter((_, i) => validationResults[i]?.ok !== false).length} file{files.length > 1 ? 's' : ''})</>
            )}
          </button>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className={`mt-3 px-3 py-2 rounded-md text-[10px] font-medium ${
          result.success ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' : 'bg-red-50 text-red-700 border border-red-100'
        }`}>
          {result.message}
          {result.refId && (
            <button
              onClick={() => navigate(`/prior-auth/${result.refId}`)}
              className="ml-2 underline font-bold"
            >
              View PA Request →
            </button>
          )}
        </div>
      )}
    </Card>
  );
}
