from __future__ import annotations

import time
from flask import Flask, request, g


def register_logging_middleware(app: Flask) -> None:

    @app.before_request
    def before_request():
        g.request_start = time.monotonic()

    @app.after_request
    def after_request(response):
        ms = round((time.monotonic() - g.get("request_start", time.monotonic())) * 1000)
        print(f"  {request.method} {request.path} -> {response.status_code} ({ms}ms)")
        return response
        return response
