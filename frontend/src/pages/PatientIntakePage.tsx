import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { CheckCircle2, Upload, AlertTriangle, FileText, Loader2, XCircle, ShieldCheck, X, Eye, ClipboardList } from 'lucide-react';

// Use raw axios (no auth interceptors) for public intake endpoints
const publicApi = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api/v1', timeout: 120000 });

interface MissingDoc {
  title: string;
  why: string;
}

interface PatientInfo {
  valid: boolean;
  patient_name: string;
  patient_mrn: string;
  payer_name: string;
  expires_at: string;
  is_additional?: boolean;
  prior_auth_id?: string;
  missing_documents?: MissingDoc[];
}

interface ValidatedFile {
  file: File;
  status: 'validating' | 'valid' | 'invalid' | 'error';
  message: string;
  document_type?: string;
  confidence?: number;
}

export default function PatientIntakePage() {
  const { token } = useParams<{ token: string }>();
  const [info, setInfo] = useState<PatientInfo | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [refId, setRefId] = useState('');
  const [submitWarnings, setSubmitWarnings] = useState<string[]>([]);

  // Form state
  const [validatedFiles, setValidatedFiles] = useState<ValidatedFile[]>([]);

  useEffect(() => {
    if (!token) return;
    publicApi
      .get(`/intake/${token}/validate`)
      .then((r) => {
        setInfo(r.data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.response?.data?.detail || 'Invalid or expired link.');
        setLoading(false);
      });
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    // Check if any files are still validating
    if (validatedFiles.some((vf) => vf.status === 'validating')) {
      setError('Please wait for document validation to complete.');
      return;
    }

    // Warn about invalid files
    const invalidCount = validatedFiles.filter((vf) => vf.status === 'invalid').length;
    if (invalidCount > 0 && validatedFiles.filter((vf) => vf.status === 'valid').length === 0) {
      setError('None of the uploaded documents appear to be valid medical records. Please upload clinical documents.');
      return;
    }

    setSubmitting(true);
    setError('');

    const formData = new FormData();
    // Only include valid files
    validatedFiles
      .filter((vf) => vf.status === 'valid' || vf.status === 'error')
      .forEach((vf) => formData.append('documents', vf.file));

    try {
      const endpoint = info?.is_additional
        ? `/intake/${token}/upload-additional`
        : `/intake/${token}/submit`;
      const res = await publicApi.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000, // 5 min for large document uploads
      });
      setSubmitted(true);
      setRefId(res.data.reference_id);
      if (res.data.warnings) setSubmitWarnings(res.data.warnings);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Submission failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const validateFile = async (file: File, index: number) => {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await publicApi.post('/ocr/validate', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000,
      });
      const d = res.data;
      setValidatedFiles((prev) =>
        prev.map((vf, i) =>
          i === index
            ? {
                ...vf,
                status: d.is_medical ? 'valid' : 'invalid',
                message: d.message,
                document_type: d.document_type,
                confidence: d.confidence,
              }
            : vf,
        ),
      );
    } catch {
      setValidatedFiles((prev) =>
        prev.map((vf, i) =>
          i === index ? { ...vf, status: 'error', message: 'Validation failed — document will still be included.' } : vf,
        ),
      );
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);
      const startIdx = validatedFiles.length;
      const newValidated: ValidatedFile[] = newFiles.map((f) => ({
        file: f,
        status: 'validating' as const,
        message: 'Checking document…',
      }));
      setValidatedFiles((prev) => [...prev, ...newValidated]);
      newFiles.forEach((f, i) => validateFile(f, startIdx + i));
    }
  };

  const removeFile = (idx: number) => {
    setValidatedFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="flex items-center gap-2 text-blue-700">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm font-medium">Validating your link…</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error && !info) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-red-50 to-orange-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h1 className="text-lg font-bold text-gray-900 mb-2">Link Unavailable</h1>
          <p className="text-sm text-gray-600">{error}</p>
          <p className="text-xs text-gray-400 mt-4">Please contact your healthcare provider for a new link.</p>
        </div>
      </div>
    );
  }

  // Success state
  if (submitted) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <CheckCircle2 className="h-12 w-12 text-emerald-500 mx-auto mb-4" />
          <h1 className="text-lg font-bold text-gray-900 mb-2">Submitted Successfully</h1>
          <p className="text-sm text-gray-600 mb-4">
            {info?.is_additional
              ? 'Your additional documents have been submitted. Your healthcare provider will review them and continue processing your authorization.'
              : 'Your medical documents have been submitted. Your healthcare provider will review them and proceed with the prior authorization.'}
          </p>
          {submitWarnings.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-left">
              <div className="flex items-center gap-1.5 mb-1">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                <span className="text-xs font-semibold text-amber-800">Notices</span>
              </div>
              {submitWarnings.map((w, i) => (
                <p key={i} className="text-xs text-amber-700">{w}</p>
              ))}
            </div>
          )}
          <div className="bg-gray-50 rounded-lg px-4 py-2 text-xs text-gray-500">
            Reference: <span className="font-mono font-medium text-gray-700">{refId}</span>
          </div>
        </div>
      </div>
    );
  }

  // Form
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center gap-2 bg-white rounded-full px-4 py-2 shadow-sm mb-4">
            <FileText className="h-5 w-5 text-blue-600" />
            <span className="font-bold text-blue-900">MEDIX</span>
          </div>
          <h1 className="text-xl font-bold text-gray-900">
            {info?.is_additional ? 'Additional Documents Requested' : 'Patient Document Upload'}
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            {info?.is_additional
              ? 'Your healthcare provider needs additional documentation to process your authorization'
              : 'Submit your medical documents for prior authorization'}
          </p>
        </div>

        {/* Patient Info Card */}
        {info && (
          <div className="bg-white rounded-xl shadow-sm border p-4 mb-6">
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-xs text-gray-500">Patient</p>
                <p className="font-medium text-gray-900">{info.patient_name}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">MRN</p>
                <p className="font-mono text-gray-900">{info.patient_mrn}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Payer</p>
                <p className="text-gray-900">{info.payer_name}</p>
              </div>
            </div>
            <div className="mt-2 text-xs text-gray-400">
              Link expires: {new Date(info.expires_at).toLocaleDateString()}
            </div>
          </div>
        )}

        {/* Missing Documents Checklist (for additional uploads) */}
        {info?.is_additional && info.missing_documents && info.missing_documents.length > 0 && (
          <div className="bg-gradient-to-br from-amber-50 to-orange-50 border-2 border-amber-300 rounded-xl shadow-md p-5 mb-6">
            <div className="flex items-center gap-2 mb-2">
              <div className="bg-amber-100 rounded-lg p-1.5">
                <ClipboardList className="h-5 w-5 text-amber-700" />
              </div>
              <div>
                <h2 className="text-[13px] font-bold text-[#111]">Required Documents</h2>
                <p className="text-[11px] text-amber-700">
                  {info.missing_documents.length} document{info.missing_documents.length > 1 ? 's' : ''} needed to continue
                </p>
              </div>
            </div>
            <div className="bg-white/80 rounded-lg border border-amber-200 p-3 mb-3">
              <p className="text-[11px] text-gray-700 leading-relaxed">
                Your healthcare provider has identified the following missing documentation. Please upload each item below to avoid delays in processing your prior authorization.
              </p>
            </div>
            <ul className="space-y-2">
              {info.missing_documents.map((doc, i) => (
                <li key={i} className="bg-white rounded-lg border border-amber-200 shadow-sm p-3 hover:border-amber-400 transition-colors">
                  <div className="flex items-start gap-3">
                    <label className="flex items-center justify-center flex-shrink-0 mt-0.5 cursor-pointer">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-2 border-amber-400 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                        onChange={(e) => {
                          const target = e.currentTarget.closest('li');
                          if (target) {
                            target.style.opacity = e.currentTarget.checked ? '0.6' : '1';
                            target.style.background = e.currentTarget.checked ? '#f0fdf4' : '';
                          }
                        }}
                      />
                    </label>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center justify-center h-4 min-w-[16px] px-1 rounded bg-amber-100 text-[10px] font-bold text-amber-700">
                          {i + 1}
                        </span>
                        <p className="text-[12px] font-semibold text-[#111]">{doc.title}</p>
                      </div>
                      <p className="text-[11px] text-gray-600 mt-1 leading-relaxed pl-6">{doc.why}</p>
                    </div>
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-500 flex-shrink-0 mt-1" />
                  </div>
                </li>
              ))}
            </ul>
            <div className="mt-3 flex items-center gap-1.5 text-[10px] text-amber-700 bg-amber-100/60 rounded-md px-2.5 py-1.5">
              <AlertTriangle className="h-3 w-3 flex-shrink-0" />
              <span>Check off items as you upload them. All documents must be provided for timely processing.</span>
            </div>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border p-6 space-y-5">
          {error && (
            <div className="bg-red-50 text-red-700 text-sm px-4 py-2.5 rounded-lg flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Document Upload */}
          <div>
            <h2 className="text-sm font-semibold text-gray-800 mb-3">Medical Documents</h2>
            <label className="flex flex-col items-center justify-center w-full h-28 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50/50 transition-colors">
              <Upload className="h-6 w-6 text-gray-400 mb-1" />
              <span className="text-sm text-gray-600">Click to upload medical documents</span>
              <span className="text-xs text-gray-400 mt-0.5">PDF, images (max 10 MB each) — documents are validated automatically</span>
              <input
                type="file"
                multiple
                accept="image/*,application/pdf"
                onChange={handleFileChange}
                className="hidden"
              />
            </label>
            {validatedFiles.length > 0 && (
              <div className="mt-2 space-y-1.5">
                {validatedFiles.map((vf, i) => (
                  <div
                    key={i}
                    className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm border ${
                      vf.status === 'valid'
                        ? 'bg-emerald-50 border-emerald-200'
                        : vf.status === 'invalid'
                        ? 'bg-red-50 border-red-200'
                        : vf.status === 'error'
                        ? 'bg-amber-50 border-amber-200'
                        : 'bg-gray-50 border-gray-200'
                    }`}
                  >
                    {vf.status === 'validating' && <Loader2 className="h-4 w-4 text-blue-500 animate-spin flex-shrink-0" />}
                    {vf.status === 'valid' && <ShieldCheck className="h-4 w-4 text-emerald-600 flex-shrink-0" />}
                    {vf.status === 'invalid' && <XCircle className="h-4 w-4 text-red-500 flex-shrink-0" />}
                    {vf.status === 'error' && <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0" />}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{vf.file.name}</p>
                      <p className={`text-xs ${
                        vf.status === 'valid' ? 'text-emerald-600' :
                        vf.status === 'invalid' ? 'text-red-600' :
                        vf.status === 'error' ? 'text-amber-600' :
                        'text-gray-500'
                      }`}>
                        {vf.message}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        const url = URL.createObjectURL(vf.file);
                        window.open(url, '_blank');
                      }}
                      className="p-0.5 hover:bg-white/50 rounded"
                      title="View document"
                    >
                      <Eye className="h-3.5 w-3.5 text-blue-600" />
                    </button>
                    <button type="button" onClick={() => removeFile(i)} className="p-0.5 hover:bg-white/50 rounded">
                      <X className="h-3.5 w-3.5 text-gray-400" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full h-10 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Submitting…
              </>
            ) : (
              'Submit Documents'
            )}
          </button>

          <p className="text-xs text-gray-400 text-center">
            Your documents will be reviewed by your healthcare provider's team.
          </p>
        </form>
      </div>
    </div>
  );
}
