from __future__ import annotations

"""Custom exception classes for consistent error handling."""

from flask import jsonify


class AppError(Exception):
    """Base application error with HTTP status code."""
    status_code = 500

    def __init__(self, detail: str, status_code: int | None = None):
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail)

    def to_response(self):
        return jsonify({"detail": self.detail}), self.status_code


class EntityNotFound(AppError):
    status_code = 404

    def __init__(self, entity: str, entity_id: str):
        super().__init__(f"{entity} with id '{entity_id}' not found.", 404)


class DuplicateEntity(AppError):
    status_code = 409

    def __init__(self, entity: str, field: str, value: str):
        super().__init__(f"{entity} with {field} '{value}' already exists.", 409)


class PipelineError(AppError):
    status_code = 500

    def __init__(self, detail: str):
        super().__init__(f"Pipeline error: {detail}", 500)


class Unauthorized(AppError):
    status_code = 401

    def __init__(self, detail: str = "Invalid credentials"):
        super().__init__(detail, 401)


class Forbidden(AppError):
    status_code = 403

    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(detail, 403)


def register_error_handlers(app):
    """Register Flask error handlers for custom exceptions."""

    @app.errorhandler(AppError)
    def handle_app_error(error):
        return error.to_response()

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"detail": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"detail": "Internal server error"}), 500
