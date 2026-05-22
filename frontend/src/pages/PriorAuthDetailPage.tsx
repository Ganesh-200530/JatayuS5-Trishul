import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import type { PriorAuth, ClinicalEvidence, Appeal } from '../types';
import { Card, Spinner, StatusBadge, UrgencyBadge, ConfidenceMeter } from '../components/ui';
import {
  ArrowLeft,
  Brain,
  FileText,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Scale,
  Pill,
  Stethoscope,
  FlaskConical,
  Image,
  Play,
  RotateCcw,
  Eye,
  ClipboardList,
  ThumbsUp,
  ThumbsDown,
  Info,
  ShieldCheck,
  ShieldAlert,
  Send,
  Copy,
  ExternalLink,
  FileUp,
  Download,
} from 'lucide-react';
import { useState, useEffect } from 'react';
import { LiveAgentPipeline, isProcessing } from '../components/AgentPipeline';

/* ── Pipeline Steps ───────────────────────────────────────── */

const STEPS = [
  { key: 'initiated', label: 'Initiated' },
  { key: 'clinical_review', label: 'Clinical Review' },
  { key: 'policy_check', label: 'Policy Check' },
  { key: 'submission_ready', label: 'Ready' },
  { key: 'submitted', label: 'Submitted' },
  { key: 'pending_decision', label: 'Pending' },
];

const TERMINAL = new Set(['approved','denied','appeal_in_progress','appeal_submitted','appeal_approved','appeal_denied','escalated','cancelled','intake_received']);

function stepIdx(status: string) {
  if (TERMINAL.has(status)) return STEPS.length;
  return STEPS.findIndex((s) => s.key === status);
}

/* ── Page ─────────────────────────────────────────────────── */

export default function PriorAuthDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [sseStep, setSseStep] = useState<string | null>(null);

  // SSE: real-time pipeline updates
  useEffect(() => {
    if (!id) return;
    const es = new EventSource(`http://127.0.0.1:8000/api/v1/prior-auth/${id}/stream`);
    es.addEventListener('step', (e) => {
      const data = JSON.parse(e.data);
      setSseStep(data.status);
      qc.invalidateQueries({ queryKey: ['prior-auth', id] });
    });
    es.addEventListener('pipeline_complete', (e) => {
      const data = JSON.parse(e.data);
      setSseStep(data.status);
      qc.invalidateQueries({ queryKey: ['prior-auth', id] });
      qc.invalidateQueries({ queryKey: ['evidence', id] });
      es.close();
    });
    es.onerror = () => { es.close(); };
    return () => es.close();
  }, [id, qc]);

  const { data: pa, isLoading } = useQuery<PriorAuth>({
    queryKey: ['prior-auth', id],
    queryFn: () => api.get(`/prior-auth/${id}`).then((r) => r.data),
    refetchInterval: 3000,
  });

  const hasEvidence = pa ? !['initiated', 'intake_received'].includes(pa.status) : false;
  const { data: evidence } = useQuery<ClinicalEvidence>({
    queryKey: ['evidence', id],
    queryFn: () => api.get(`/prior-auth/${id}/evidence`).then((r) => r.status === 204 ? null : r.data),
    retry: false,
    enabled: hasEvidence,
  });

  // Decision breakdown
  const { data: breakdown } = useQuery<any>({
    queryKey: ['breakdown', id],
    queryFn: () => api.get(`/prior-auth/${id}/breakdown`).then((r) => r.data),
    enabled: hasEvidence,
  });

  // SSE real-time updates
  useEffect(() => {
    if (!pa || !isProcessing(pa.status)) return;
    const evtSource = new EventSource(`/api/v1/prior-auth/${id}/stream`);
    evtSource.addEventListener('status_update', (e) => {
      try {
        const data = JSON.parse(e.data);
        setSseStep(data.status || data.step);
      } catch {}
    });
    evtSource.addEventListener('pipeline_complete', () => {
      qc.invalidateQueries({ queryKey: ['prior-auth', id] });
      qc.invalidateQueries({ queryKey: ['evidence', id] });
      qc.invalidateQueries({ queryKey: ['breakdown', id] });
      evtSource.close();
    });
    evtSource.onerror = () => evtSource.close();
    return () => evtSource.close();
  }, [pa?.status, id, qc]);

  const { data: appeals } = useQuery<Appeal[]>({
    queryKey: ['appeals', id],
    queryFn: () => api.get('/appeals/', { params: { prior_auth_id: id } }).then((r) => r.data),
  });

  if (isLoading) return <Spinner />;
  if (!pa) return <p className="text-sm text-gray-500 py-8">Not found</p>;

  const current = stepIdx(pa.status);

  return (
    <div className="space-y-5 animate-in">
      {/* Header */}
      <div className="flex items-start gap-3">
        <Link to="/prior-auth" className="mt-0.5 p-1 hover:bg-gray-100 rounded-md transition-colors">
          <ArrowLeft className="h-4 w-4 text-gray-500" />
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-lg font-semibold text-gray-900">Request</h1>
            <StatusBadge status={pa.status} />
            <UrgencyBadge urgency={pa.urgency} />
          </div>
          <p className="text-xs text-gray-400 font-mono mt-0.5">{pa.id}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {pa.status === 'intake_received' && <StartEvaluationButton paId={pa.id} qc={qc} />}
          <RerunAIButton paId={pa.id} status={pa.status} qc={qc} />
          <ExportPDFButton paId={pa.id} />
          {pa.status === 'denied' && <AppealButton paId={pa.id} qc={qc} />}
        </div>
      </div>

      {/* Pipeline Progress */}
      <Card className="px-5 py-4">
        <div className="flex items-center gap-1">
          {STEPS.map((step, i) => {
            const done = i < current;
            const active = i === current;
            return (
              <div key={step.key} className="flex items-center flex-1 last:flex-none">
                <div className="flex flex-col items-center">
                  <div
                    className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-medium border transition-all ${
                      done
                        ? 'bg-emerald-500 border-emerald-500 text-white'
                        : active
                          ? 'bg-blue-600 border-blue-600 text-white'
                          : 'bg-white border-gray-300 text-gray-400'
                    }`}
                  >
                    {done ? <CheckCircle2 className="h-3.5 w-3.5" /> : i + 1}
                  </div>
                  <span className={`text-[10px] mt-1 font-medium ${done ? 'text-emerald-600' : active ? 'text-blue-600' : 'text-gray-400'}`}>
                    {step.label}
                  </span>
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`flex-1 h-px mx-1.5 mt-[-14px] ${i < current ? 'bg-emerald-400' : 'bg-gray-200'}`} />
                )}
              </div>
            );
          })}
        </div>

        {/* Terminal status */}
        {current === STEPS.length && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            {pa.status === 'approved' || pa.status === 'appeal_approved' ? (
              <div className="inline-flex items-center gap-1.5 text-sm text-emerald-700 bg-emerald-50 px-3 py-1 rounded-md">
                <CheckCircle2 className="h-4 w-4" /> Approved
              </div>
            ) : pa.status === 'denied' || pa.status === 'appeal_denied' ? (
              <div className="inline-flex items-center gap-1.5 text-sm text-red-700 bg-red-50 px-3 py-1 rounded-md">
                <XCircle className="h-4 w-4" /> Denied
              </div>
            ) : (
              <div className="inline-flex items-center gap-1.5 text-sm text-amber-700 bg-amber-50 px-3 py-1 rounded-md">
                <AlertTriangle className="h-4 w-4" /> {pa.status.replace(/_/g, ' ')}
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Live agent pipeline */}
      {isProcessing(sseStep || pa.status) && (
        <Card className="p-4 bg-gray-50/50">
          <LiveAgentPipeline status={sseStep || pa.status} />
        </Card>
      )}

      {/* Human Review */}
      {pa.requires_human_review && (
        <HumanReviewPanel paId={pa.id} reason={pa.human_review_reason} qc={qc} evidence={evidence} />
      )}

      {/* Document Request Status */}
      <DocumentRequestSection paId={pa.id} pa={pa} qc={qc} evidence={evidence} />

      {/* Decision Breakdown */}
      {breakdown && (breakdown.criteria_met?.length > 0 || breakdown.criteria_not_met?.length > 0) && (
        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <ClipboardList className="h-3.5 w-3.5 text-emerald-600" />
              <h3 className="text-[11px] font-bold text-[#111] uppercase tracking-wide">DECISION BREAKDOWN</h3>
            </div>
            <span className="text-[10px] font-mono font-bold text-[#555]">
              {breakdown.met_count}/{breakdown.total_criteria} criteria met ({Math.round(breakdown.overall_score * 100)}%)
            </span>
          </div>

          {/* Progress bar */}
          <div className="w-full h-2 bg-[#f0f0f0] rounded-full mb-3 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${breakdown.overall_score >= 0.8 ? 'bg-emerald-500' : breakdown.overall_score >= 0.5 ? 'bg-amber-500' : 'bg-red-500'}`}
              style={{ width: `${breakdown.overall_score * 100}%` }}
            />
          </div>

          {/* Criteria met */}
          {breakdown.criteria_met?.length > 0 && (
            <div className="space-y-1.5 mb-3">
              {breakdown.criteria_met.map((c: any, i: number) => (
                <div key={i} className="flex items-start gap-2 p-2 bg-emerald-50/50 border border-emerald-100 rounded-md">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] font-bold text-emerald-800">{c.criterion}</p>
                    <p className="text-[9px] text-emerald-600 truncate">{c.evidence_found}</p>
                  </div>
                  <span className="text-[8px] text-emerald-500 font-mono shrink-0">{c.source}</span>
                </div>
              ))}
            </div>
          )}

          {/* Criteria not met */}
          {breakdown.criteria_not_met?.length > 0 && (
            <div className="space-y-1.5">
              {breakdown.criteria_not_met.map((c: any, i: number) => (
                <div key={i} className="flex items-start gap-2 p-2 bg-red-50/50 border border-red-100 rounded-md">
                  <XCircle className="h-3.5 w-3.5 text-red-500 mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] font-bold text-red-800">{c.criterion}</p>
                    <p className="text-[9px] text-red-600">{c.reason_missing}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Details grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-3">Request Details</h2>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <Dt label="CPT Code">{pa.cpt_code}</Dt>
            <Dt label="Description">{pa.cpt_description || '—'}</Dt>
            <Dt label="ICD-10">{pa.icd10_codes.join(', ') || '—'}</Dt>
            <Dt label="Payer">{pa.payer_name || pa.payer_id}</Dt>
            <Dt label="Provider">{pa.ordering_provider_name || pa.ordering_provider_npi}</Dt>
            <Dt label="Facility">{pa.facility_name || '—'}</Dt>
            <Dt label="Confidence"><ConfidenceMeter score={pa.confidence_score} /></Dt>
            <Dt label="Tracking #">{pa.payer_tracking_number || '—'}</Dt>
          </dl>
          {pa.decision_reason && (
            <div className="mt-4 bg-gray-50 rounded-md p-3 text-sm">
              <p className="text-xs font-medium text-gray-500 mb-1">Decision Reason</p>
              <p className="text-gray-700">{pa.decision_reason}</p>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-3">Timeline</h2>
          <dl className="space-y-2.5 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Created</span>
              <span className="font-medium text-gray-900">{new Date(pa.created_at).toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Updated</span>
              <span className="font-medium text-gray-900">{new Date(pa.updated_at).toLocaleString()}</span>
            </div>
            {pa.decision_date && (
              <div className="flex justify-between">
                <span className="text-gray-500">Decision</span>
                <span className="font-medium text-gray-900">{new Date(pa.decision_date).toLocaleString()}</span>
              </div>
            )}
          </dl>

          {appeals && appeals.length > 0 && (
            <div className="mt-4 pt-3 border-t border-gray-100">
              <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">Appeals</h3>
              <div className="space-y-2">
                {appeals.map((a) => (
                  <div key={a.id} className="text-sm bg-purple-50 rounded-md p-2.5">
                    <div className="flex justify-between items-center">
                      <span className="font-medium text-purple-800">Attempt #{a.attempt_number}</span>
                      <StatusBadge status={a.status as any} />
                    </div>
                    {a.denial_reason && <p className="text-xs text-purple-600 mt-1">{a.denial_reason.replace(/_/g, ' ')}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* Clinical Notes / Uploaded Documents */}
      {pa.metadata_?.clinical_notes && <ClinicalNotesSection notes={pa.metadata_.clinical_notes as string} metadata={pa.metadata_} />}

      {/* Evidence */}
      {evidence && <EvidenceSection evidence={evidence} />}

      {/* No evidence yet message */}
      {!evidence && hasEvidence && (
        <Card className="p-5 text-center">
          <Brain className="h-6 w-6 text-gray-300 mx-auto mb-2" />
          <p className="text-sm text-gray-500">AI evidence extraction in progress…</p>
        </Card>
      )}
      {!evidence && !hasEvidence && pa.status === 'intake_received' && (
        <Card className="p-5 border-blue-100 bg-blue-50/30">
          <div className="flex items-center gap-2 mb-1">
            <Info className="h-4 w-4 text-blue-600" />
            <p className="text-sm font-medium text-blue-800">Awaiting AI Evaluation</p>
          </div>
          <p className="text-xs text-blue-600">Click "Start AI Evaluation" above to begin automated clinical review and policy check.</p>
        </Card>
      )}
    </div>
  );
}

/* ── Document Request Section ─────────────────────────────── */

interface DocLink {
  token: string;
  status: string;
  missing_documents: { title: string; why: string }[] | null;
  expires_at: string;
  created_at: string | null;
}

function DocumentRequestSection({ paId, pa, qc, evidence }: { paId: string; pa: PriorAuth; qc: ReturnType<typeof useQueryClient>; evidence?: ClinicalEvidence | null }) {
  const [showRequest, setShowRequest] = useState(false);
  const [generatedLink, setGeneratedLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: docLinks } = useQuery<DocLink[]>({
    queryKey: ['doc-links', paId],
    queryFn: () => api.get(`/prior-auth/${paId}/additional-documents`).then((r) => r.data),
    refetchInterval: 5000,
  });

  const isReal = (v: string | null | undefined) => v && !v.toLowerCase().includes('no clinical notes available') && v.trim().length > 5;

  // Build missing items list from evidence
  const buildMissingItems = () => {
    const items: { title: string; why: string }[] = [];
    if (evidence) {
      if (!isReal(evidence.diagnosis_summary)) {
        items.push({ title: 'Diagnosis summary', why: 'No clear diagnosis was found in the uploaded documents. Consider requesting additional clinical notes.' });
      }
      if (!isReal(evidence.medical_necessity_justification)) {
        items.push({ title: 'Medical necessity statement', why: 'The documents do not contain a clear explanation of why this procedure is needed. A physician letter may be required.' });
      }
      if (!evidence.failed_conservative_therapies?.length) {
        items.push({ title: 'Conservative treatment history', why: 'No record of failed conservative therapies (e.g., physical therapy, medication trials). Most payers require proof that simpler treatments were tried first.' });
      }
      if (!evidence.supporting_findings?.length) {
        items.push({ title: 'Supporting clinical findings', why: 'No specific clinical findings (exam results, test outcomes) were extracted. These help justify the treatment.' });
      }
    }
    return items;
  };

  const requestMutation = useMutation({
    mutationFn: (missingDocs: { title: string; why: string }[]) =>
      api.post(`/prior-auth/${paId}/request-documents`, { missing_documents: missingDocs }),
    onSuccess: (res) => {
      const token = res.data.intake_token;
      const link = `${window.location.origin}/intake/${token}`;
      setGeneratedLink(link);
      qc.invalidateQueries({ queryKey: ['doc-links', paId] });
      qc.invalidateQueries({ queryKey: ['prior-auth', paId] });
    },
  });

  const handleRequestDocs = () => {
    const missingItems = buildMissingItems();
    requestMutation.mutate(missingItems);
  };

  const copyLink = () => {
    if (generatedLink) {
      navigator.clipboard.writeText(generatedLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const activeLink = docLinks?.find((l) => l.status === 'active');
  const usedLinks = docLinks?.filter((l) => l.status === 'used') || [];
  const hasMissingDocs = evidence && buildMissingItems().length > 0;
  const docsReceived = pa.metadata_?.additional_docs_received === true;

  // Show section if: there are missing docs, or there are active/used links, or docs were recently received
  if (!hasMissingDocs && !activeLink && !usedLinks.length && !docsReceived && !generatedLink) return null;

  return (
    <Card className="border-blue-200 bg-blue-50/20 p-5">
      {/* Recently received additional documents banner */}
      {docsReceived && pa.status === 'intake_received' && (
        <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 mb-4">
          <CheckCircle2 className="h-4 w-4 text-emerald-600 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-emerald-800">Additional documents received from patient</p>
            <p className="text-xs text-emerald-600">Click "Start AI Evaluation" to re-analyze with the new documents.</p>
          </div>
        </div>
      )}

      {/* Active link waiting for patient */}
      {activeLink && !generatedLink && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4">
          <div className="flex items-center gap-2 mb-1">
            <FileUp className="h-4 w-4 text-amber-600" />
            <span className="text-sm font-semibold text-amber-800">Waiting for patient documents</span>
          </div>
          <p className="text-xs text-amber-700 mb-2">
            A document request link has been sent. Waiting for the patient to upload.
            Expires: {new Date(activeLink.expires_at).toLocaleDateString()}
          </p>
          <div className="flex items-center gap-2">
            <input
              type="text"
              readOnly
              value={`${window.location.origin}/intake/${activeLink.token}`}
              className="flex-1 text-xs bg-white border border-amber-300 rounded px-2 py-1.5 font-mono text-gray-700"
            />
            <button
              onClick={() => {
                navigator.clipboard.writeText(`${window.location.origin}/intake/${activeLink.token}`);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
              className="h-7 px-2.5 text-xs bg-amber-600 text-white rounded font-medium hover:bg-amber-700 transition-colors flex items-center gap-1"
            >
              <Copy className="h-3 w-3" /> {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
          {activeLink.missing_documents && activeLink.missing_documents.length > 0 && (
            <div className="mt-2 text-xs text-amber-600">
              Requested: {activeLink.missing_documents.map(d => d.title).join(', ')}
            </div>
          )}
        </div>
      )}

      {/* Generated link (just created) */}
      {generatedLink && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 mb-4">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <span className="text-sm font-semibold text-emerald-800">Document request link generated</span>
          </div>
          <p className="text-xs text-emerald-700 mb-2">Share this link with the patient to collect the missing documents:</p>
          <div className="flex items-center gap-2">
            <input
              type="text"
              readOnly
              value={generatedLink}
              className="flex-1 text-xs bg-white border border-emerald-300 rounded px-2 py-1.5 font-mono text-gray-700"
            />
            <button
              onClick={copyLink}
              className="h-7 px-2.5 text-xs bg-emerald-600 text-white rounded font-medium hover:bg-emerald-700 transition-colors flex items-center gap-1"
            >
              <Copy className="h-3 w-3" /> {copied ? 'Copied!' : 'Copy'}
            </button>
            <a
              href={generatedLink}
              target="_blank"
              rel="noopener noreferrer"
              className="h-7 px-2.5 text-xs bg-blue-600 text-white rounded font-medium hover:bg-blue-700 transition-colors flex items-center gap-1"
            >
              <ExternalLink className="h-3 w-3" /> Preview
            </a>
          </div>
        </div>
      )}

      {/* Request Documents Button (when there are missing items and no active link) */}
      {hasMissingDocs && !activeLink && !generatedLink && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Send className="h-4 w-4 text-blue-600" />
              <span className="text-sm font-semibold text-gray-900">Request Missing Documents</span>
            </div>
          </div>
          <p className="text-xs text-gray-600 mb-3">
            Generate a link for the patient to upload the missing documentation identified by AI analysis.
          </p>
          {!showRequest ? (
            <button
              onClick={() => setShowRequest(true)}
              className="h-8 px-4 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 transition-colors flex items-center gap-1.5"
            >
              <Send className="h-3.5 w-3.5" /> Generate Patient Link
            </button>
          ) : (
            <div className="bg-white border border-blue-200 rounded-lg p-3 space-y-2">
              <p className="text-xs font-medium text-gray-700">The following items will be requested:</p>
              <ul className="space-y-1">
                {buildMissingItems().map((item, i) => (
                  <li key={i} className="text-xs bg-amber-50 border border-amber-100 rounded px-2.5 py-1.5">
                    <span className="font-medium text-amber-800">{item.title}</span>
                    <p className="text-amber-600 mt-0.5">{item.why}</p>
                  </li>
                ))}
              </ul>
              <div className="flex gap-2 pt-1">
                <button
                  onClick={handleRequestDocs}
                  disabled={requestMutation.isPending}
                  className="h-7 px-3 text-xs bg-blue-600 text-white rounded font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center gap-1"
                >
                  <Send className="h-3 w-3" />
                  {requestMutation.isPending ? 'Generating…' : 'Send Request'}
                </button>
                <button
                  onClick={() => setShowRequest(false)}
                  className="h-7 px-3 text-xs border border-gray-300 text-gray-600 rounded font-medium hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
              </div>
              {requestMutation.isError && <p className="text-xs text-red-600">Failed to generate link. Try again.</p>}
            </div>
          )}
        </div>
      )}

      {/* Previous document requests */}
      {usedLinks.length > 0 && (
        <div className={activeLink || generatedLink || hasMissingDocs ? 'mt-3 pt-3 border-t border-blue-100' : ''}>
          <p className="text-xs font-medium text-gray-500 mb-1">Previous document requests</p>
          {usedLinks.map((link, i) => (
            <div key={i} className="text-xs text-gray-500 flex items-center gap-1.5">
              <CheckCircle2 className="h-3 w-3 text-emerald-500" />
              Documents received {link.created_at ? new Date(link.created_at).toLocaleDateString() : ''}
              {link.missing_documents && ` (${link.missing_documents.map(d => d.title).join(', ')})`}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

/* ── Clinical Notes / Document View ───────────────────────── */

interface DocRecord {
  filename: string;
  document_type: string;
  summary: string;
  extracted_text: string;
  source?: string;
  file_id?: string;
}

const DOC_TYPE_LABELS: Record<string, string> = {
  medical_record: 'Medical Record',
  lab_report: 'Lab Report',
  prescription: 'Prescription',
  imaging_report: 'Imaging Report',
  referral: 'Referral',
  discharge_summary: 'Discharge Summary',
  operative_report: 'Operative Report',
  clinical_note: 'Clinical Note',
  insurance_form: 'Insurance Form',
  unknown: 'Document',
};

function DocumentCard({ doc }: { doc: DocRecord }) {
  const [expanded, setExpanded] = useState(false);
  const typeLabel = DOC_TYPE_LABELS[doc.document_type] || doc.document_type.replace(/_/g, ' ');
  const hasFullText = doc.extracted_text && doc.extracted_text.trim().length > 0;
  const isAdditional = doc.source === 'additional_request';
  const token = localStorage.getItem('token');
  const viewUrl = doc.file_id ? `http://127.0.0.1:8000/api/v1/prior-auth/documents/${doc.file_id}?token=${token}` : null;

  return (
    <div className={`border rounded-lg overflow-hidden ${isAdditional ? 'border-emerald-200' : 'border-gray-200'}`}>
      {/* Document header */}
      <div className={`px-4 py-2.5 flex items-center justify-between ${isAdditional ? 'bg-emerald-50' : 'bg-gray-50'}`}>
        <div className="flex items-center gap-2 min-w-0">
          <FileText className={`h-4 w-4 flex-shrink-0 ${isAdditional ? 'text-emerald-600' : 'text-blue-600'}`} />
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">{doc.filename}</p>
            <div className="flex items-center gap-2">
              <span className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded ${
                isAdditional ? 'bg-emerald-100 text-emerald-700' : 'bg-blue-100 text-blue-700'
              }`}>
                {typeLabel}
              </span>
              {isAdditional && <span className="text-[10px] text-emerald-600 font-medium">Additional</span>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 ml-2">
          {viewUrl && (
            <a
              href={viewUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs bg-blue-600 text-white px-2.5 py-1 rounded-md font-medium hover:bg-blue-700 transition-colors"
            >
              <Eye className="h-3 w-3" /> View PDF
            </a>
          )}
          {hasFullText && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-blue-600 font-medium hover:underline"
            >
              {expanded ? 'Hide Full Text' : 'View Full Text'}
            </button>
          )}
        </div>
      </div>

      {/* Summary */}
      {doc.summary && (
        <div className="px-4 py-2.5 border-t border-gray-100">
          <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Summary</p>
          <p className="text-sm text-gray-700 leading-relaxed">{doc.summary}</p>
        </div>
      )}

      {/* Full extracted text (expandable) */}
      {expanded && hasFullText && (
        <div className="px-4 py-3 border-t border-gray-100 bg-slate-50">
          <p className="text-xs font-semibold text-gray-500 uppercase mb-1.5">Full Extracted Text</p>
          <div className="max-h-80 overflow-y-auto bg-white border border-gray-200 rounded-md p-3">
            <pre className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed font-sans">{doc.extracted_text}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

function ClinicalNotesSection({ notes, metadata }: { notes: string; metadata?: Record<string, unknown> | null }) {
  const [open, setOpen] = useState(false);
  const [showLegacy, setShowLegacy] = useState(false);

  // Get structured documents from metadata
  const documents: DocRecord[] = (metadata?.documents as DocRecord[]) || [];
  const hasStructured = documents.length > 0;

  // Fallback: parse legacy concatenated notes for old PAs
  const docSeparator = '--- Uploaded Documents ---';
  const addlSeparator = '--- Additional Documents (Requested) ---';
  const hasDocSection = notes.includes(docSeparator);
  const patientNotes = hasDocSection ? notes.split(docSeparator)[0].trim() : '';
  const rawDocText = hasDocSection
    ? notes.split(docSeparator)[1]?.split(addlSeparator)[0]?.trim() || ''
    : notes.trim();
  const hasLegacyContent = !hasStructured && (patientNotes || rawDocText);

  const initialDocs = documents.filter(d => d.source !== 'additional_request');
  const additionalDocs = documents.filter(d => d.source === 'additional_request');

  return (
    <Card className="overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between px-5 py-3 hover:bg-gray-50/50 transition-colors">
        <div className="flex items-center gap-2">
          <Eye className="h-4 w-4 text-indigo-600" />
          <h2 className="text-sm font-semibold text-gray-900">
            Uploaded Documents
            {documents.length > 0 && <span className="text-gray-400 font-normal ml-1">({documents.length})</span>}
          </h2>
        </div>
        <span className="text-xs text-indigo-600 font-medium">{open ? 'Hide' : 'View Documents'}</span>
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-gray-100 pt-4">
          {/* Structured documents view */}
          {hasStructured && (
            <div className="space-y-4">
              {/* Initial documents */}
              {initialDocs.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Initial Submission ({initialDocs.length})</p>
                  <div className="space-y-2">
                    {initialDocs.map((doc, i) => <DocumentCard key={i} doc={doc} />)}
                  </div>
                </div>
              )}

              {/* Additional requested documents */}
              {additionalDocs.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-emerald-600 uppercase mb-2">Additional Documents ({additionalDocs.length})</p>
                  <div className="space-y-2">
                    {additionalDocs.map((doc, i) => <DocumentCard key={i} doc={doc} />)}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Legacy fallback for older PAs without structured docs */}
          {hasLegacyContent && (
            <div className="space-y-3">
              {patientNotes && (
                <div>
                  <div className="flex items-center gap-1.5 mb-2">
                    <ClipboardList className="h-3.5 w-3.5 text-gray-500" />
                    <h3 className="text-xs font-semibold text-gray-600">Patient Notes</h3>
                  </div>
                  <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
                    <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{patientNotes}</p>
                  </div>
                </div>
              )}
              {rawDocText && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-1.5">
                      <FileText className="h-3.5 w-3.5 text-blue-600" />
                      <h3 className="text-xs font-semibold text-gray-600">Extracted Content</h3>
                    </div>
                    <button onClick={() => setShowLegacy(!showLegacy)} className="text-xs text-blue-600 font-medium hover:underline">
                      {showLegacy ? 'Collapse' : 'Expand'}
                    </button>
                  </div>
                  <div className="bg-blue-50/50 border border-blue-200 rounded-md p-3 max-h-96 overflow-y-auto">
                    <pre className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed font-sans">
                      {showLegacy ? rawDocText : rawDocText.split('\n').filter(l => l.trim()).slice(0, 8).join('\n')}
                      {!showLegacy && rawDocText.split('\n').filter(l => l.trim()).length > 8 && '\n\n…'}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* No content at all */}
          {!hasStructured && !hasLegacyContent && (
            <p className="text-sm text-gray-400 text-center py-2">No documents uploaded.</p>
          )}
        </div>
      )}
    </Card>
  );
}

/* ── Evidence Section ─────────────────────────────────────── */

function EvidenceSection({ evidence }: { evidence: ClinicalEvidence }) {
  const [open, setOpen] = useState(true);

  // Filter out placeholder text like "No clinical notes available."
  const isReal = (v: string | null | undefined) => v && !v.toLowerCase().includes('no clinical notes available') && v.trim().length > 5;

  const diagnosisSummary = isReal(evidence.diagnosis_summary) ? evidence.diagnosis_summary : null;
  const medNecessity = isReal(evidence.medical_necessity_justification) ? evidence.medical_necessity_justification : null;
  const treatmentHist = evidence.treatment_history;
  const hasContent = diagnosisSummary || medNecessity ||
    (Array.isArray(treatmentHist) && treatmentHist.length > 0) || (typeof treatmentHist === 'string' && isReal(treatmentHist)) ||
    evidence.failed_conservative_therapies?.length ||
    evidence.medications?.length || evidence.supporting_findings?.length ||
    evidence.relevant_imaging?.length || evidence.relevant_lab_results?.length;

  return (
    <Card className="overflow-hidden border-blue-100">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between px-5 py-3 hover:bg-blue-50/30 transition-colors">
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-blue-600" />
          <h2 className="text-sm font-semibold text-gray-900">AI Analysis & Extracted Evidence</h2>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-medium">{evidence.extraction_model}</span>
          <span>{evidence.extraction_duration_ms}ms</span>
          <ConfidenceMeter score={evidence.confidence_score} />
        </div>
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-blue-100 pt-4">
          {!hasContent && (
            <div className="text-center py-4">
              <AlertTriangle className="h-5 w-5 text-amber-400 mx-auto mb-2" />
              <p className="text-sm text-gray-500">No clinical data could be extracted. Try uploading clearer medical documents and click "Rerun AI".</p>
            </div>
          )}
          {diagnosisSummary && (
            <EvidenceBlock icon={Stethoscope} color="text-blue-600" title="Diagnosis Summary">
              <p className="text-sm text-gray-700 leading-relaxed">{diagnosisSummary}</p>
            </EvidenceBlock>
          )}

          {medNecessity && (
            <EvidenceBlock icon={FileText} color="text-emerald-600" title="Medical Necessity">
              <p className="text-sm text-gray-700 leading-relaxed">{medNecessity}</p>
            </EvidenceBlock>
          )}

          {evidence.treatment_history && (
            (() => {
              const th = evidence.treatment_history;
              if (Array.isArray(th) && th.length > 0) {
                return (
                  <EvidenceBlock icon={ClipboardList} color="text-orange-600" title="Treatment History">
                    <div className="space-y-1.5">
                      {th.map((item: any, i: number) => (
                        <div key={i} className="bg-orange-50 rounded px-2.5 py-1.5 text-xs">
                          <span className="font-medium text-orange-800">{item.treatment || JSON.stringify(item)}</span>
                          {item.date && <span className="text-orange-600 ml-1">({item.date})</span>}
                          {item.outcome && <span className="text-orange-600"> — {item.outcome}</span>}
                        </div>
                      ))}
                    </div>
                  </EvidenceBlock>
                );
              }
              if (typeof th === 'string' && isReal(th)) {
                return (
                  <EvidenceBlock icon={ClipboardList} color="text-orange-600" title="Treatment History">
                    <p className="text-sm text-gray-700 leading-relaxed">{th}</p>
                  </EvidenceBlock>
                );
              }
              return null;
            })()
          )}

          {evidence.failed_conservative_therapies?.length ? (
            <EvidenceBlock icon={XCircle} color="text-red-500" title="Failed Therapies">
              <div className="flex flex-wrap gap-1.5">
                {evidence.failed_conservative_therapies.map((t, i) => (
                  <span key={i} className="bg-red-50 text-red-700 px-2 py-0.5 rounded text-xs font-medium">{t}</span>
                ))}
              </div>
            </EvidenceBlock>
          ) : null}

          {evidence.medications?.length ? (
            <EvidenceBlock icon={Pill} color="text-purple-600" title={`Medications (${evidence.medications.length})`}>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                {evidence.medications.map((m, i) => (
                  <div key={i} className="bg-purple-50 rounded px-2.5 py-1.5 text-xs">
                    <span className="font-medium text-purple-800">{(m as any).name || JSON.stringify(m)}</span>
                    {(m as any).dose && <span className="text-purple-600 ml-1">{(m as any).dose}</span>}
                  </div>
                ))}
              </div>
            </EvidenceBlock>
          ) : null}

          {evidence.supporting_findings?.length ? (
            <EvidenceBlock icon={FlaskConical} color="text-indigo-600" title="Supporting Findings">
              <ul className="space-y-1">
                {evidence.supporting_findings.map((f, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-sm text-gray-700">
                    <span className="text-indigo-400 mt-0.5 text-xs">&#x2022;</span>
                    {(f as any).finding || JSON.stringify(f)}
                  </li>
                ))}
              </ul>
            </EvidenceBlock>
          ) : null}

          {evidence.relevant_imaging?.length ? (
            <EvidenceBlock icon={Image} color="text-teal-600" title="Relevant Imaging">
              <ul className="space-y-1">
                {evidence.relevant_imaging.map((img, i) => (
                  <li key={i} className="text-sm text-gray-700 bg-teal-50 rounded px-2.5 py-1">
                    {(img as any).description || (img as any).type || JSON.stringify(img)}
                  </li>
                ))}
              </ul>
            </EvidenceBlock>
          ) : null}

          {evidence.relevant_lab_results?.length ? (
            <EvidenceBlock icon={FlaskConical} color="text-cyan-600" title="Lab Results">
              <ul className="space-y-1">
                {evidence.relevant_lab_results.map((lab, i) => (
                  <li key={i} className="text-sm text-gray-700 bg-cyan-50 rounded px-2.5 py-1.5">
                    {(lab as any).test && <span className="font-medium">{(lab as any).test}: </span>}
                    {(lab as any).result || (lab as any).value || JSON.stringify(lab)}
                  </li>
                ))}
              </ul>
            </EvidenceBlock>
          ) : null}
        </div>
      )}
    </Card>
  );
}

function EvidenceBlock({ icon: Icon, color, title, children }: { icon: any; color: string; title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon className={`h-3.5 w-3.5 ${color}`} />
        <h3 className="text-xs font-semibold text-gray-700">{title}</h3>
      </div>
      {children}
    </div>
  );
}

/* ── Helpers ──────────────────────────────────────────────── */

function Dt({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-gray-500">{label}</dt>
      <dd className="font-medium text-gray-900 mt-0.5">{children}</dd>
    </div>
  );
}

function HumanReviewPanel({ paId, reason, qc, evidence }: { paId: string; reason: string | null; qc: ReturnType<typeof useQueryClient>; evidence?: ClinicalEvidence | null }) {
  const [notes, setNotes] = useState('');

  const approve = useMutation({
    mutationFn: () => api.post(`/prior-auth/${paId}/review`, null, { params: { decision: 'approve', reason: notes || undefined } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['prior-auth', paId] }),
  });

  const deny = useMutation({
    mutationFn: () => api.post(`/prior-auth/${paId}/review`, null, { params: { decision: 'deny', reason: notes || undefined } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['prior-auth', paId] }),
  });

  const busy = approve.isPending || deny.isPending;

  // Helper to check if evidence field has real content
  const isReal = (v: string | null | undefined) => v && !v.toLowerCase().includes('no clinical notes available') && v.trim().length > 5;

  // Build detailed suggestions from evidence
  const approveReasons: { title: string; detail: string }[] = [];
  const denyReasons: { title: string; detail: string }[] = [];
  const missingItems: { title: string; why: string }[] = [];

  if (evidence) {
    if (isReal(evidence.medical_necessity_justification)) {
      approveReasons.push({ title: 'Medical necessity documented', detail: 'The clinical records provide a clear explanation of why this treatment is needed.' });
    }
    if (evidence.failed_conservative_therapies?.length) {
      approveReasons.push({ title: `${evidence.failed_conservative_therapies.length} failed treatments documented`, detail: `Patient has tried ${evidence.failed_conservative_therapies.join(', ')} without success, supporting the need for the requested procedure.` });
    }
    if (evidence.supporting_findings?.length) {
      approveReasons.push({ title: 'Clinical findings support the request', detail: `${evidence.supporting_findings.length} clinical finding(s) support the diagnosis and treatment plan.` });
    }
    if (evidence.relevant_imaging?.length) {
      approveReasons.push({ title: 'Imaging studies available', detail: 'Diagnostic imaging results are on file and relevant to the requested procedure.' });
    }
    if (evidence.relevant_lab_results?.length) {
      approveReasons.push({ title: 'Lab results support diagnosis', detail: 'Laboratory test results are consistent with the clinical diagnosis.' });
    }
    if (evidence.medications?.length) {
      approveReasons.push({ title: 'Medication history documented', detail: `${evidence.medications.length} medication(s) documented in the clinical records.` });
    }

    if (!isReal(evidence.diagnosis_summary)) {
      missingItems.push({ title: 'Diagnosis summary', why: 'No clear diagnosis was found in the uploaded documents. Consider requesting additional clinical notes.' });
    }
    if (!isReal(evidence.medical_necessity_justification)) {
      missingItems.push({ title: 'Medical necessity statement', why: 'The documents do not contain a clear explanation of why this procedure is needed. A physician letter may be required.' });
      denyReasons.push({ title: 'No medical necessity documentation', detail: 'Without a clear medical necessity statement, payers typically deny the request.' });
    }
    if (!evidence.failed_conservative_therapies?.length) {
      missingItems.push({ title: 'Conservative treatment history', why: 'No record of failed conservative therapies (e.g., physical therapy, medication trials). Most payers require proof that simpler treatments were tried first.' });
    }
    if (!evidence.supporting_findings?.length) {
      missingItems.push({ title: 'Supporting clinical findings', why: 'No specific clinical findings (exam results, test outcomes) were extracted. These help justify the treatment.' });
    }

    if (evidence.confidence_score < 0.3) {
      denyReasons.push({ title: `Very low AI confidence (${Math.round(evidence.confidence_score * 100)}%)`, detail: 'The AI found very little supporting evidence in the documents. The records may be incomplete or unclear.' });
    } else if (evidence.confidence_score < 0.5) {
      denyReasons.push({ title: `Low AI confidence (${Math.round(evidence.confidence_score * 100)}%)`, detail: 'Some evidence was found but it may not be sufficient to meet payer requirements.' });
    }
  } else {
    missingItems.push({ title: 'AI analysis not available', why: 'No AI analysis has been performed yet. Click "Rerun AI" to analyze the uploaded documents.' });
  }

  return (
    <Card className="border-orange-200 bg-orange-50/30 p-5">
      <div className="flex items-center gap-2 mb-1">
        <AlertTriangle className="h-4 w-4 text-orange-600" />
        <h3 className="text-sm font-semibold text-orange-800">Human Review Required</h3>
      </div>
      {reason && <p className="text-sm text-orange-700 mb-4">{reason}</p>}

      {/* AI Recommendation Summary */}
      {evidence && (
        <div className="bg-white border border-orange-200 rounded-lg p-3 mb-4">
          <p className="text-xs font-semibold text-gray-600 mb-1">AI Recommendation</p>
          <p className="text-sm text-gray-700">
            {evidence.confidence_score >= 0.7
              ? 'Based on the available evidence, this request appears to have strong clinical support. Consider approving.'
              : evidence.confidence_score >= 0.4
              ? 'Some supporting evidence was found, but there are gaps. Review the missing items below before deciding.'
              : 'The available evidence is insufficient. Additional documentation is likely needed, or this request may not meet criteria.'}
          </p>
        </div>
      )}

      {/* Detailed suggestions */}
      {(approveReasons.length > 0 || denyReasons.length > 0 || missingItems.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
          {approveReasons.length > 0 && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <ThumbsUp className="h-3.5 w-3.5 text-emerald-600" />
                <span className="text-xs font-semibold text-emerald-800">Reasons to Approve</span>
              </div>
              <ul className="space-y-2">
                {approveReasons.map((r, i) => (
                  <li key={i} className="text-xs">
                    <div className="flex items-start gap-1 text-emerald-800 font-medium">
                      <ShieldCheck className="h-3 w-3 mt-0.5 flex-shrink-0" /> {r.title}
                    </div>
                    <p className="text-emerald-600 ml-4 mt-0.5">{r.detail}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {denyReasons.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <ThumbsDown className="h-3.5 w-3.5 text-red-600" />
                <span className="text-xs font-semibold text-red-800">Concerns to Consider</span>
              </div>
              <ul className="space-y-2">
                {denyReasons.map((r, i) => (
                  <li key={i} className="text-xs">
                    <div className="flex items-start gap-1 text-red-800 font-medium">
                      <ShieldAlert className="h-3 w-3 mt-0.5 flex-shrink-0" /> {r.title}
                    </div>
                    <p className="text-red-600 ml-4 mt-0.5">{r.detail}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {missingItems.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <Info className="h-3.5 w-3.5 text-amber-600" />
                <span className="text-xs font-semibold text-amber-800">Missing Documentation</span>
              </div>
              <ul className="space-y-2">
                {missingItems.map((r, i) => (
                  <li key={i} className="text-xs">
                    <div className="font-medium text-amber-800">{r.title}</div>
                    <p className="text-amber-600 mt-0.5">{r.why}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Add your review notes here (optional)…"
        rows={2}
        className="w-full px-2.5 py-2 text-sm border border-orange-200 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-400 resize-none mb-3"
      />
      <div className="flex gap-2">
        <button onClick={() => approve.mutate()} disabled={busy} className="h-8 px-4 bg-emerald-600 text-white rounded-md text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors flex items-center gap-1.5">
          <ThumbsUp className="h-3.5 w-3.5" />
          {approve.isPending ? 'Approving…' : 'Approve'}
        </button>
        <button onClick={() => deny.mutate()} disabled={busy} className="h-8 px-4 bg-red-600 text-white rounded-md text-sm font-medium hover:bg-red-700 disabled:opacity-50 transition-colors flex items-center gap-1.5">
          <ThumbsDown className="h-3.5 w-3.5" />
          {deny.isPending ? 'Denying…' : 'Deny'}
        </button>
      </div>
      {(approve.isError || deny.isError) && <p className="text-xs text-red-600 mt-2">Action failed — try again.</p>}
    </Card>
  );
}

function AppealButton({ paId, qc }: { paId: string; qc: ReturnType<typeof useQueryClient> }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('medical_necessity_not_met');
  const [details, setDetails] = useState('');

  const mutation = useMutation({
    mutationFn: () => api.post('/appeals/', { prior_auth_id: paId, denial_reason: reason, denial_details: details || undefined }),
    onSuccess: () => { setOpen(false); qc.invalidateQueries({ queryKey: ['prior-auth', paId] }); qc.invalidateQueries({ queryKey: ['appeals', paId] }); },
  });

  const inputCls = 'w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500';

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 h-8 px-3 bg-purple-600 text-white rounded-md text-sm font-medium hover:bg-purple-700 transition-colors">
        <Scale className="h-3.5 w-3.5" /> Appeal
      </button>
    );
  }

  return (
    <Card className="p-4 w-72 shadow-lg">
      <h3 className="text-sm font-semibold mb-2">File Appeal</h3>
      <select value={reason} onChange={(e) => setReason(e.target.value)} className={inputCls + ' mb-2'}>
        <option value="medical_necessity_not_met">Medical Necessity Not Met</option>
        <option value="missing_information">Missing Information</option>
        <option value="coding_error">Coding Error</option>
        <option value="out_of_network">Out of Network</option>
        <option value="administrative">Administrative</option>
        <option value="other">Other</option>
      </select>
      <textarea value={details} onChange={(e) => setDetails(e.target.value)} placeholder="Details…" rows={2} className={inputCls + ' resize-none mb-2'} />
      <div className="flex gap-2">
        <button onClick={() => setOpen(false)} className="h-7 px-2.5 text-xs border rounded-md text-gray-600">Cancel</button>
        <button onClick={() => mutation.mutate()} disabled={mutation.isPending} className="h-7 px-3 text-xs bg-purple-600 text-white rounded-md font-medium disabled:opacity-50">
          {mutation.isPending ? 'Filing…' : 'Submit'}
        </button>
      </div>
    </Card>
  );
}

function StartEvaluationButton({ paId, qc }: { paId: string; qc: ReturnType<typeof useQueryClient> }) {
  const mutation = useMutation({
    mutationFn: () => api.post(`/prior-auth/${paId}/evaluate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['prior-auth', paId] }),
  });

  return (
    <button
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      className="inline-flex items-center gap-1.5 h-8 px-3 bg-emerald-600 text-white rounded-md text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors"
    >
      <Play className="h-3.5 w-3.5" />
      {mutation.isPending ? 'Starting…' : 'Start AI Evaluation'}
    </button>
  );
}

function RerunAIButton({ paId, status, qc }: { paId: string; status: string; qc: ReturnType<typeof useQueryClient> }) {
  const allowedStatuses = new Set(['denied', 'escalated', 'approved', 'appeal_denied', 'cancelled']);
  // Also show when human review is needed (pending_decision with requires_human_review)
  const showRerun = allowedStatuses.has(status) || status === 'pending_decision';

  const mutation = useMutation({
    mutationFn: () => api.post(`/prior-auth/${paId}/retry`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['prior-auth', paId] });
      qc.invalidateQueries({ queryKey: ['evidence', paId] });
    },
  });

  if (!showRerun) return null;

  return (
    <button
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      className="inline-flex items-center gap-1.5 h-8 px-3 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
    >
      <RotateCcw className={`h-3.5 w-3.5 ${mutation.isPending ? 'animate-spin' : ''}`} />
      {mutation.isPending ? 'Rerunning…' : 'Rerun AI'}
    </button>
  );
}

function ExportPDFButton({ paId }: { paId: string }) {
  const [loading, setLoading] = useState(false);
  const handleExport = async () => {
    setLoading(true);
    try {
      const resp = await api.get(`/prior-auth/${paId}/export-pdf`, { responseType: 'blob' });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `PA_Report_${paId.replace(/-/g, '').slice(0, 12)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setLoading(false);
    }
  };
  return (
    <button
      onClick={handleExport}
      disabled={loading}
      className="inline-flex items-center gap-1.5 h-8 px-3 bg-gray-100 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-200 disabled:opacity-50 transition-colors"
    >
      <Download className={`h-3.5 w-3.5 ${loading ? 'animate-bounce' : ''}`} />
      {loading ? 'Exporting…' : 'Export PDF'}
    </button>
  );
}
