from __future__ import annotations

from flask import Flask

from app.api.endpoints import (
    auth, patients, prior_auth, appeals, policies, dashboard,
    eligibility, audit_logs, webhooks, submissions, payers, ocr, intake,
)


def register_routes(app: Flask) -> None:
    """Register all API blueprints under /api/v1."""
    app.register_blueprint(auth.bp, url_prefix="/api/v1/auth")
    app.register_blueprint(patients.bp, url_prefix="/api/v1/patients")
    app.register_blueprint(prior_auth.bp, url_prefix="/api/v1/prior-auth")
    app.register_blueprint(appeals.bp, url_prefix="/api/v1/appeals")
    app.register_blueprint(policies.bp, url_prefix="/api/v1/policies")
    app.register_blueprint(dashboard.bp, url_prefix="/api/v1/dashboard")
    app.register_blueprint(eligibility.bp, url_prefix="/api/v1/eligibility")
    app.register_blueprint(audit_logs.bp, url_prefix="/api/v1/audit-logs")
    app.register_blueprint(webhooks.bp, url_prefix="/api/v1/webhooks")
    app.register_blueprint(submissions.bp, url_prefix="/api/v1/submissions")
    app.register_blueprint(payers.bp, url_prefix="/api/v1/payers")
    app.register_blueprint(ocr.bp, url_prefix="/api/v1/ocr")
    app.register_blueprint(intake.bp, url_prefix="/api/v1/intake")
