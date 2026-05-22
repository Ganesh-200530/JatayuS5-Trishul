// TypeScript types matching backend schemas

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface Patient {
  id: string;
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  email: string | null;
  phone: string | null;
  payer_id: string;
  payer_name: string | null;
  plan_id: string | null;
  subscriber_id: string | null;
  fhir_patient_id: string | null;
  created_at: string;
  intake_token?: string | null;
}

export interface PatientCreate {
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  email?: string;
  phone?: string;
  payer_id: string;
  payer_name?: string;
  plan_id?: string;
  subscriber_id?: string;
}

export type PAStatus =
  | 'initiated'
  | 'clinical_review'
  | 'policy_check'
  | 'submission_ready'
  | 'submitted'
  | 'pending_decision'
  | 'approved'
  | 'denied'
  | 'appeal_in_progress'
  | 'appeal_submitted'
  | 'appeal_approved'
  | 'appeal_denied'
  | 'escalated'
  | 'cancelled'
  | 'intake_received';

export type Urgency = 'standard' | 'urgent' | 'emergent';

export interface PriorAuth {
  id: string;
  patient_id: string;
  status: PAStatus;
  urgency: Urgency;
  cpt_code: string;
  cpt_description: string | null;
  icd10_codes: string[];
  ordering_provider_npi: string;
  ordering_provider_name: string | null;
  facility_npi: string | null;
  facility_name: string | null;
  payer_id: string;
  payer_name: string | null;
  confidence_score: number | null;
  requires_human_review: boolean;
  human_review_reason: string | null;
  payer_tracking_number: string | null;
  decision_reason: string | null;
  decision_date: string | null;
  metadata_?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface PriorAuthList {
  id: string;
  patient_id: string;
  patient_name: string | null;
  status: PAStatus;
  urgency: Urgency;
  cpt_code: string;
  payer_id: string;
  confidence_score: number | null;
  requires_human_review: boolean;
  created_at: string;
}

export interface PriorAuthCreate {
  patient_id: string;
  cpt_code: string;
  cpt_description?: string;
  icd10_codes: string[];
  ordering_provider_npi: string;
  ordering_provider_name?: string;
  facility_npi?: string;
  facility_name?: string;
  payer_id: string;
  payer_name?: string;
  urgency: Urgency;
  clinical_notes?: string;
}

export interface ClinicalEvidence {
  id: string;
  prior_auth_id: string;
  diagnosis_summary: string | null;
  medical_necessity_justification: string | null;
  treatment_history: string | null;
  failed_conservative_therapies: string[] | null;
  supporting_findings: Record<string, unknown>[] | null;
  relevant_lab_results: Record<string, unknown>[] | null;
  relevant_imaging: Record<string, unknown>[] | null;
  medications: Record<string, unknown>[] | null;
  source_documents: Record<string, unknown>[] | null;
  confidence_score: number;
  extraction_model: string;
  extraction_duration_ms: number;
  created_at: string;
}

export interface PayerPolicy {
  id: string;
  payer_id: string;
  payer_name: string;
  cpt_code: string;
  cpt_description: string | null;
  pa_required: boolean;
  policy_document_url: string | null;
  effective_date: string | null;
  expiration_date: string | null;
  last_synced_at: string | null;
  created_at: string;
}

export interface Appeal {
  id: string;
  prior_auth_id: string;
  attempt_number: number;
  status: string;
  denial_reason: string | null;
  denial_details: string | null;
  appeal_letter: string | null;
  additional_evidence: Record<string, unknown>[] | null;
  cited_references: Record<string, unknown>[] | null;
  submitted_at: string | null;
  response_at: string | null;
  created_at: string;
  patient_name?: string | null;
  patient_mrn?: string | null;
  cpt_code?: string | null;
  payer_name?: string | null;
}

export type DenialReason =
  | 'missing_information'
  | 'medical_necessity_not_met'
  | 'out_of_network'
  | 'coding_error'
  | 'duplicate'
  | 'administrative'
  | 'other';

export interface DashboardStats {
  total_requests: number;
  status_breakdown: Record<string, number>;
  approval_rate: number;
  pending_human_review: number;
  average_confidence_score: number;
  total_appeals: number;
  appeal_success_rate: number;
}

export interface AuditLog {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogList {
  items: AuditLog[];
  total: number;
  limit: number;
  offset: number;
}

export interface WebhookEvent {
  id: string;
  source_payer: string;
  event_type: string;
  processing_status: string;
  pa_tracking_number: string | null;
  pa_request_id: string | null;
  decision: string | null;
  reason: string | null;
  retry_count: number;
  error_message: string | null;
  processed_at: string | null;
  received_at: string;
}

export interface EligibilityCheck {
  id: string;
  patient_id: string;
  payer_id: string;
  status: string;
  is_active: boolean;
  plan_name: string | null;
  group_number: string | null;
  subscriber_id: string | null;
  pa_required_for_cpt: boolean | null;
  checked_cpt_code: string | null;
  copay_amount: string | null;
  coinsurance_pct: string | null;
  deductible_remaining: string | null;
  error_message: string | null;
  checked_at: string;
}

export interface Submission {
  id: string;
  prior_auth_id: string;
  channel: string;
  status: string;
  payer_tracking_number: string | null;
  submitted_at: string | null;
  error_message: string | null;
  created_at: string | null;
}
