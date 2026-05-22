from __future__ import annotations

"""Portal RPA â€” Playwright-based browser automation for payer portals.

Automates PA submission for payers that only support web portal submission
(no FHIR API or X12 EDI available).
"""

import asyncio
import structlog
from typing import Any

from app.config import get_settings

logger = structlog.get_logger()

_playwright_available = False


def _check_playwright():
    global _playwright_available
    try:
        import playwright  # noqa: F401
        _playwright_available = True
    except ImportError:
        _playwright_available = False
    return _playwright_available


# â”€â”€ Payer Portal Configurations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

PORTAL_CONFIGS: dict[str, dict] = {
    "BCBS": {
        "name": "BlueCross BlueShield",
        "url": "https://portal.bcbs.com/prior-auth",
        "login_selector": "#username",
        "password_selector": "#password",
        "submit_button": "#login-btn",
        "steps": [
            {"action": "navigate", "url": "/prior-auth/new"},
            {"action": "fill", "selector": "#member-id", "field": "subscriber_id"},
            {"action": "fill", "selector": "#patient-name", "field": "patient_name"},
            {"action": "fill", "selector": "#dob", "field": "date_of_birth"},
            {"action": "fill", "selector": "#cpt-code", "field": "cpt_code"},
            {"action": "fill", "selector": "#icd-code", "field": "icd10_primary"},
            {"action": "fill", "selector": "#provider-npi", "field": "ordering_provider_npi"},
            {"action": "fill", "selector": "#clinical-notes", "field": "clinical_notes"},
            {"action": "upload", "selector": "#attachments", "field": "attachment_path"},
            {"action": "click", "selector": "#submit-pa"},
            {"action": "wait_for", "selector": "#confirmation-number"},
            {"action": "extract", "selector": "#confirmation-number", "output": "tracking_number"},
        ],
    },
    "AETNA": {
        "name": "Aetna",
        "url": "https://portal.aetna.com/preauthorization",
        "login_selector": "#email",
        "password_selector": "#pass",
        "submit_button": "#sign-in",
        "steps": [
            {"action": "navigate", "url": "/preauthorization/submit"},
            {"action": "fill", "selector": "#memberId", "field": "subscriber_id"},
            {"action": "fill", "selector": "#patientFirstName", "field": "patient_first_name"},
            {"action": "fill", "selector": "#patientLastName", "field": "patient_last_name"},
            {"action": "fill", "selector": "#serviceCode", "field": "cpt_code"},
            {"action": "fill", "selector": "#diagnosisCode", "field": "icd10_primary"},
            {"action": "fill", "selector": "#providerNPI", "field": "ordering_provider_npi"},
            {"action": "fill", "selector": "#justification", "field": "medical_necessity"},
            {"action": "click", "selector": "#submitRequest"},
            {"action": "wait_for", "selector": ".confirmation-message"},
            {"action": "extract", "selector": ".reference-number", "output": "tracking_number"},
        ],
    },
    "UNITED": {
        "name": "UnitedHealthcare",
        "url": "https://portal.uhc.com/priorauth",
        "login_selector": "#userId",
        "password_selector": "#userPassword",
        "submit_button": "#loginButton",
        "steps": [
            {"action": "navigate", "url": "/priorauth/new-request"},
            {"action": "fill", "selector": "#memberNumber", "field": "subscriber_id"},
            {"action": "fill", "selector": "#patientName", "field": "patient_name"},
            {"action": "fill", "selector": "#dateOfBirth", "field": "date_of_birth"},
            {"action": "fill", "selector": "#procedureCode", "field": "cpt_code"},
            {"action": "fill", "selector": "#diagnosisCode", "field": "icd10_primary"},
            {"action": "fill", "selector": "#requestingProvider", "field": "ordering_provider_npi"},
            {"action": "fill", "selector": "#clinicalInfo", "field": "clinical_notes"},
            {"action": "click", "selector": "#submitPA"},
            {"action": "wait_for", "selector": "#authNumber"},
            {"action": "extract", "selector": "#authNumber", "output": "tracking_number"},
        ],
    },
}


class PortalAutomation:
    """Automated payer portal interaction using Playwright."""

    def __init__(self):
        self.settings = get_settings()
        self.browser = None
        self.context = None

    def submit_pa(
        self,
        payer_id: str,
        portal_credentials: dict,
        pa_data: dict,
    ) -> dict:
        """
        Submit a PA through a payer's web portal.

        Args:
            payer_id: Payer identifier matching PORTAL_CONFIGS key
            portal_credentials: {"username": "...", "password": "..."}
            pa_data: Dict with field values matching the portal config
        """
        if not _check_playwright():
            return {"success": False, "error": "Playwright not installed", "channel": "portal"}

        config = PORTAL_CONFIGS.get(payer_id.upper())
        if not config:
            return {
                "success": False,
                "error": f"No portal configuration for payer '{payer_id}'",
                "channel": "portal",
                "available_payers": list(PORTAL_CONFIGS.keys()),
            }

        result = {
            "success": False,
            "channel": "portal",
            "payer": config["name"],
            "tracking_number": None,
            "screenshots": [],
            "error": None,
        }

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                self.browser = p.chromium.launch(headless=self.settings.RPA_HEADLESS)
                self.context = self.browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutoAuth/1.0",
                )
                page = self.context.new_page()
                page.set_default_timeout(self.settings.RPA_TIMEOUT_MS)

                # Login
                page.goto(config["url"])
                page.fill(config["login_selector"], portal_credentials.get("username", ""))
                page.fill(config["password_selector"], portal_credentials.get("password", ""))
                page.click(config["submit_button"])
                page.wait_for_load_state("networkidle")

                logger.info("rpa.logged_in", payer=payer_id)

                # Execute steps
                for step in config.get("steps", []):
                    action = step["action"]

                    if action == "navigate":
                        page.goto(config["url"] + step["url"])
                        page.wait_for_load_state("networkidle")

                    elif action == "fill":
                        value = pa_data.get(step["field"], "")
                        if value:
                            page.fill(step["selector"], str(value))

                    elif action == "click":
                        page.click(step["selector"])
                        page.wait_for_load_state("networkidle")

                    elif action == "wait_for":
                        page.wait_for_selector(step["selector"], timeout=self.settings.RPA_TIMEOUT_MS)

                    elif action == "upload":
                        file_path = pa_data.get(step["field"])
                        if file_path:
                            page.set_input_files(step["selector"], file_path)

                    elif action == "extract":
                        element = page.query_selector(step["selector"])
                        if element:
                            text = element.inner_text()
                            result[step["output"]] = text.strip()

                    elif action == "screenshot":
                        screenshot = page.screenshot()
                        result["screenshots"].append(screenshot)

                result["success"] = True
                logger.info("rpa.submission_complete", payer=payer_id, tracking=result.get("tracking_number"))

                self.browser.close()

        except Exception as exc:
            result["error"] = str(exc)[:500]
            logger.error("rpa.submission_failed", payer=payer_id, error=str(exc))
            if self.browser:
                try:
                    self.browser.close()
                except Exception:
                    pass

        return result

    def check_status(
        self,
        payer_id: str,
        portal_credentials: dict,
        tracking_number: str,
    ) -> dict:
        """Check PA status through payer portal."""
        if not _check_playwright():
            return {"success": False, "error": "Playwright not installed"}

        # Simplified â€” each payer would have specific status-check steps
        return {
            "success": False,
            "error": "Status check via portal not yet implemented for this payer",
            "tracking_number": tracking_number,
        }

    @staticmethod
    def get_supported_payers() -> list[dict]:
        """List payers with portal automation support."""
        return [
            {"payer_id": pid, "name": cfg["name"], "url": cfg["url"]}
            for pid, cfg in PORTAL_CONFIGS.items()
        ]


# Module-level singleton
portal_automation = PortalAutomation()


def is_rpa_available() -> bool:
    return _check_playwright()
