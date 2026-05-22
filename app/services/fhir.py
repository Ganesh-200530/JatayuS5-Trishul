from __future__ import annotations

"""FHIR R4 client for interacting with EHR and payer FHIR servers."""

import structlog
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger()


class FHIRClient:
    """Sync FHIR R4 client."""

    def __init__(self, base_url: str | None = None, auth_token: str | None = None):
        settings = get_settings()
        self.base_url = (base_url or settings.FHIR_BASE_URL).rstrip('/')
        self.auth_token = auth_token or settings.FHIR_AUTH_TOKEN
        self._headers = {'Content-Type': 'application/fhir+json', 'Accept': 'application/fhir+json'}
        if self.auth_token:
            self._headers['Authorization'] = f'Bearer {self.auth_token}'

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, headers=self._headers, timeout=30.0)

    # -- Patient ---

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def get_patient(self, patient_id: str) -> dict:
        with self._client() as client:
            resp = client.get(f'/Patient/{patient_id}')
            resp.raise_for_status()
            return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def search_patient(self, mrn: str) -> dict:
        with self._client() as client:
            resp = client.get('/Patient', params={'identifier': mrn})
            resp.raise_for_status()
            return resp.json()

    # -- Clinical Documents ---

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def get_document_references(self, patient_id: str) -> list[dict]:
        with self._client() as client:
            resp = client.get('/DocumentReference', params={'patient': patient_id, '_count': '100'})
            resp.raise_for_status()
            bundle = resp.json()
            return [entry['resource'] for entry in bundle.get('entry', [])]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def get_conditions(self, patient_id: str) -> list[dict]:
        with self._client() as client:
            resp = client.get('/Condition', params={'patient': patient_id, '_count': '100'})
            resp.raise_for_status()
            bundle = resp.json()
            return [entry['resource'] for entry in bundle.get('entry', [])]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def get_observations(self, patient_id: str, category: str | None = None) -> list[dict]:
        params: dict = {'patient': patient_id, '_count': '100'}
        if category:
            params['category'] = category
        with self._client() as client:
            resp = client.get('/Observation', params=params)
            resp.raise_for_status()
            bundle = resp.json()
            return [entry['resource'] for entry in bundle.get('entry', [])]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def get_medication_requests(self, patient_id: str) -> list[dict]:
        with self._client() as client:
            resp = client.get('/MedicationRequest', params={'patient': patient_id, '_count': '100'})
            resp.raise_for_status()
            bundle = resp.json()
            return [entry['resource'] for entry in bundle.get('entry', [])]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def get_diagnostic_reports(self, patient_id: str) -> list[dict]:
        with self._client() as client:
            resp = client.get('/DiagnosticReport', params={'patient': patient_id, '_count': '100'})
            resp.raise_for_status()
            bundle = resp.json()
            return [entry['resource'] for entry in bundle.get('entry', [])]

    # -- Coverage & Eligibility ---

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def check_coverage_eligibility(self, patient_id: str, payer_id: str) -> dict:
        resource = {
            'resourceType': 'CoverageEligibilityRequest',
            'status': 'active',
            'purpose': ['auth-requirements'],
            'patient': {'reference': f'Patient/{patient_id}'},
            'insurer': {'reference': f'Organization/{payer_id}'},
        }
        with self._client() as client:
            resp = client.post('/CoverageEligibilityRequest', json=resource)
            resp.raise_for_status()
            return resp.json()

    def check_eligibility(self, patient_id: str, payer_id: str, cpt_code: str | None = None) -> dict:
        resource = {
            'resourceType': 'CoverageEligibilityRequest',
            'status': 'active',
            'purpose': ['benefits', 'auth-requirements'],
            'patient': {'reference': f'Patient/{patient_id}'},
            'insurer': {'reference': f'Organization/{payer_id}'},
        }
        if cpt_code:
            resource['item'] = [{'productOrService': {'coding': [{'system': 'http://www.ama-assn.org/go/cpt', 'code': cpt_code}]}}]
        with self._client() as client:
            resp = client.post('/CoverageEligibilityRequest', json=resource)
            resp.raise_for_status()
            result = resp.json()
            return {
                'plan_name': self._extract_plan_name(result),
                'group_number': self._extract_group_number(result),
                'pa_required': self._extract_pa_required(result),
                'in_network': True,
                'raw_response': result,
            }

    @staticmethod
    def _extract_plan_name(response: dict) -> str | None:
        for ins in response.get('insurance', []):
            return ins.get('coverage', {}).get('display')
        return None

    @staticmethod
    def _extract_group_number(response: dict) -> str | None:
        for ins in response.get('insurance', []):
            for item in ins.get('item', []):
                for benefit in item.get('benefit', []):
                    if benefit.get('type', {}).get('text') == 'group':
                        return benefit.get('allowedString')
        return None

    @staticmethod
    def _extract_pa_required(response: dict) -> bool:
        for ins in response.get('insurance', []):
            for item in ins.get('item', []):
                if item.get('authorizationRequired'):
                    return True
        return False

    # -- Prior Authorization Submission (Da Vinci PAS) ---

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=15))
    def submit_prior_auth(self, claim_resource: dict) -> dict:
        bundle = {
            'resourceType': 'Bundle',
            'type': 'collection',
            'entry': [{'resource': claim_resource}],
        }
        with self._client() as client:
            resp = client.post('/Claim/$submit', json=bundle)
            resp.raise_for_status()
            return resp.json()

    # -- Utilities ---

    def build_patient_clinical_text(self, patient_id: str) -> str:
        docs = self.get_document_references(patient_id)
        conditions = self.get_conditions(patient_id)
        observations = self.get_observations(patient_id)
        meds = self.get_medication_requests(patient_id)
        reports = self.get_diagnostic_reports(patient_id)

        parts: list[str] = []

        for doc in docs:
            for content in doc.get('content', []):
                attachment = content.get('attachment', {})
                if 'data' in attachment:
                    import base64
                    text = base64.b64decode(attachment['data']).decode('utf-8', errors='replace')
                    parts.append(f"[Document: {doc.get('type', {}).get('text', 'Unknown')}]\n{text}")

        for cond in conditions:
            code = cond.get('code', {}).get('text', 'Unknown condition')
            status = cond.get('clinicalStatus', {}).get('coding', [{}])[0].get('code', '')
            parts.append(f'[Condition] {code} -- status: {status}')

        for obs in observations:
            code = obs.get('code', {}).get('text', 'Unknown')
            value = obs.get('valueQuantity', {}).get('value', obs.get('valueString', ''))
            unit = obs.get('valueQuantity', {}).get('unit', '')
            parts.append(f'[Observation] {code}: {value} {unit}')

        for med in meds:
            drug = med.get('medicationCodeableConcept', {}).get('text', 'Unknown')
            status = med.get('status', '')
            parts.append(f'[Medication] {drug} -- status: {status}')

        for report in reports:
            code = report.get('code', {}).get('text', 'Unknown')
            conclusion = report.get('conclusion', '')
            parts.append(f'[DiagnosticReport] {code}: {conclusion}')

        return '\n\n'.join(parts) if parts else 'No clinical documents found.'


fhir_client = FHIRClient()
