from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS

from app.config import get_settings


def create_app() -> Flask:
    settings = get_settings()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.SECRET_KEY

    CORS(app, origins="*", supports_credentials=True)

    # Simple request logging
    from app.core.middleware import register_logging_middleware
    register_logging_middleware(app)

    # Register blueprints
    from app.api.router import register_routes
    register_routes(app)

    @app.route("/health")
    def health():
        return jsonify({"status": "healthy", "version": "2.0.0"})

    # Error handlers
    from app.core.exceptions import register_error_handlers
    register_error_handlers(app)

    # Create SQLite tables on startup
    from app.database import engine, Base
    from app.models import appeal, audit, clinical_evidence, eligibility, intake_link, patient, payer, policy, prior_auth, submission, user, webhook
    Base.metadata.create_all(bind=engine)
    print(" * SQLite tables created")

    # Migrate existing tables — add new columns if missing
    from sqlalchemy import text, inspect
    with engine.connect() as conn:
        inspector = inspect(engine)
        # patient_intake_links migrations
        cols = {c['name'] for c in inspector.get_columns('patient_intake_links')}
        if 'prior_auth_id' not in cols:
            conn.execute(text('ALTER TABLE patient_intake_links ADD COLUMN prior_auth_id VARCHAR(36)'))
            print(" * Added prior_auth_id to patient_intake_links")
        if 'missing_documents' not in cols:
            conn.execute(text('ALTER TABLE patient_intake_links ADD COLUMN missing_documents JSON'))
            print(" * Added missing_documents to patient_intake_links")
        # patients migrations
        pcols = {c['name'] for c in inspector.get_columns('patients')}
        if 'email' not in pcols:
            conn.execute(text('ALTER TABLE patients ADD COLUMN email VARCHAR(200)'))
            print(" * Added email to patients")
        if 'phone' not in pcols:
            conn.execute(text('ALTER TABLE patients ADD COLUMN phone VARCHAR(30)'))
            print(" * Added phone to patients")
        conn.commit()

    return app


app = create_app()

