"""Notification service — email/SMS alerts for PA lifecycle events.

Uses Python's built-in smtplib for email, and a pluggable SMS backend.
In development mode, notifications are logged instead of sent.
"""

from __future__ import annotations

import smtplib
import structlog
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import get_settings

logger = structlog.get_logger()


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an email. Returns True on success."""
    settings = get_settings()
    if not settings.SMTP_HOST:
        logger.info('notification.email_skipped', to=to, subject=subject, reason='no SMTP configured')
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = settings.SMTP_FROM
    msg['To'] = to
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.sendmail(settings.SMTP_FROM, [to], msg.as_string())
        logger.info('notification.email_sent', to=to, subject=subject)
        return True
    except Exception as exc:
        logger.error('notification.email_failed', to=to, error=str(exc))
        return False


def send_sms(phone: str, message: str) -> bool:
    """Send an SMS. Returns True on success. Uses Twilio if configured."""
    settings = get_settings()
    if not settings.TWILIO_ACCOUNT_SID:
        logger.info('notification.sms_skipped', phone=phone, reason='no Twilio configured')
        return False

    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=settings.TWILIO_FROM_NUMBER,
            to=phone,
        )
        logger.info('notification.sms_sent', phone=phone)
        return True
    except Exception as exc:
        logger.error('notification.sms_failed', phone=phone, error=str(exc))
        return False


# ── Notification Templates ─────────────────────────────────

def notify_intake_link_created(patient_email: str, patient_name: str, intake_url: str) -> None:
    """Notify patient that an intake link has been created."""
    subject = "MEDIX — Upload Your Medical Documents"
    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1e40af;">MEDIX Prior Authorization</h2>
        <p>Dear <strong>{patient_name}</strong>,</p>
        <p>Your healthcare provider has requested medical documents for a prior authorization review.</p>
        <p>Please upload your documents using the secure link below:</p>
        <p style="margin: 24px 0;">
            <a href="{intake_url}" style="background: #2563eb; color: white; padding: 12px 24px;
               border-radius: 6px; text-decoration: none; font-weight: 600;">
               Upload Documents
            </a>
        </p>
        <p style="color: #6b7280; font-size: 14px;">This link expires in 7 days.</p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
        <p style="color: #9ca3af; font-size: 12px;">MEDIX Healthcare Automation — Confidential</p>
    </div>
    """
    send_email(patient_email, subject, html)


def notify_documents_received(patient_email: str, patient_name: str, doc_count: int) -> None:
    """Notify patient that their documents were received."""
    subject = "MEDIX — Documents Received"
    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1e40af;">MEDIX Prior Authorization</h2>
        <p>Dear <strong>{patient_name}</strong>,</p>
        <p>We have received <strong>{doc_count} document(s)</strong> for your prior authorization request.</p>
        <p>Our AI system is now analyzing your records. You will be notified when a decision is made.</p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
        <p style="color: #9ca3af; font-size: 12px;">MEDIX Healthcare Automation — Confidential</p>
    </div>
    """
    send_email(patient_email, subject, html)


def notify_decision(patient_email: str, patient_name: str, status: str, reason: str = "") -> None:
    """Notify patient of the PA decision."""
    status_labels = {'approved': 'Approved', 'denied': 'Denied', 'escalated': 'Under Review'}
    status_colors = {'approved': '#059669', 'denied': '#dc2626', 'escalated': '#d97706'}
    label = status_labels.get(status, status.replace('_', ' ').title())
    color = status_colors.get(status, '#6b7280')

    subject = f"MEDIX — Prior Authorization {label}"
    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1e40af;">MEDIX Prior Authorization</h2>
        <p>Dear <strong>{patient_name}</strong>,</p>
        <p>Your prior authorization request has been updated:</p>
        <div style="background: #f9fafb; border-left: 4px solid {color}; padding: 16px; margin: 16px 0; border-radius: 4px;">
            <p style="font-size: 18px; font-weight: 700; color: {color}; margin: 0;">{label}</p>
            {"<p style='color: #374151; margin: 8px 0 0 0;'>" + reason + "</p>" if reason else ""}
        </div>
        <p>Please contact your healthcare provider for next steps.</p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
        <p style="color: #9ca3af; font-size: 12px;">MEDIX Healthcare Automation — Confidential</p>
    </div>
    """
    send_email(patient_email, subject, html)


def notify_missing_documents(patient_email: str, patient_name: str, missing_items: list[str], upload_url: str) -> None:
    """Notify patient that additional documents are needed."""
    items_html = "".join(f"<li>{item}</li>" for item in missing_items)
    subject = "MEDIX — Additional Documents Needed"
    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1e40af;">MEDIX Prior Authorization</h2>
        <p>Dear <strong>{patient_name}</strong>,</p>
        <p>Your prior authorization request requires additional documentation:</p>
        <ul style="color: #374151;">{items_html}</ul>
        <p style="margin: 24px 0;">
            <a href="{upload_url}" style="background: #2563eb; color: white; padding: 12px 24px;
               border-radius: 6px; text-decoration: none; font-weight: 600;">
               Upload Additional Documents
            </a>
        </p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
        <p style="color: #9ca3af; font-size: 12px;">MEDIX Healthcare Automation — Confidential</p>
    </div>
    """
    send_email(patient_email, subject, html)
