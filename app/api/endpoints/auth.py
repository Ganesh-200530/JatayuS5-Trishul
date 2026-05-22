from __future__ import annotations

import time as _time
from flask import Blueprint, request, jsonify
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.schemas.auth import (
    UserCreate, UserRead, LoginRequest, Token,
    RefreshTokenRequest, TOTPSetupResponse, TOTPVerifyRequest,
)
from app.core.security import (
    hash_password, verify_password, create_access_token, get_current_user,
    get_current_user_cached,
    create_refresh_token, hash_refresh_token,
    generate_totp_secret, verify_totp, get_totp_provisioning_uri,
    _user_cache, _USER_CACHE_TTL,
)
from app.core.exceptions import DuplicateEntity, Unauthorized

bp = Blueprint('auth', __name__)


@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    payload = UserCreate(**data)
    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
        if existing:
            raise DuplicateEntity('User', 'email', payload.email)
        user = User(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            role=payload.role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return jsonify(UserRead.model_validate(user, from_attributes=True).model_dump(mode='json')), 201
    finally:
        db.close()


@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    payload = LoginRequest(**data)
    db = SessionLocal()
    try:
        result = db.execute(select(User).where(User.email == payload.email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(payload.password, user.hashed_password):
            raise Unauthorized('Invalid email or password')
        if not user.is_active:
            raise Unauthorized('Account is disabled')
        if user.totp_enabled:
            if not payload.totp_code:
                raise Unauthorized('TOTP code required')
            if not verify_totp(user.totp_secret, payload.totp_code):
                raise Unauthorized('Invalid TOTP code')

        access_token = create_access_token(user.id, user.role)
        uid = str(user.id)
        refresh = create_refresh_token()

        try:
            user.refresh_token_hash = hash_refresh_token(refresh)
            db.commit()
        except Exception:
            db.rollback()
            refresh = ''

        _user_cache[uid] = (user, _time.time() + _USER_CACHE_TTL)
        return jsonify({'access_token': access_token, 'refresh_token': refresh, 'token_type': 'bearer'})
    finally:
        db.close()


@bp.route('/refresh', methods=['POST'])
def refresh_token():
    data = request.get_json()
    payload = RefreshTokenRequest(**data)
    db = SessionLocal()
    try:
        token_hash = hash_refresh_token(payload.refresh_token)
        result = db.execute(select(User).where(User.refresh_token_hash == token_hash))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise Unauthorized('Invalid refresh token')
        new_access = create_access_token(user.id, user.role)
        new_refresh = create_refresh_token()
        user.refresh_token_hash = hash_refresh_token(new_refresh)
        db.commit()
        return jsonify({'access_token': new_access, 'refresh_token': new_refresh, 'token_type': 'bearer'})
    finally:
        db.close()


@bp.route('/logout', methods=['POST'])
def logout():
    db = SessionLocal()
    try:
        user = get_current_user(db)
        user.refresh_token_hash = None
        db.commit()
        return jsonify({'message': 'Logged out'})
    finally:
        db.close()


@bp.route('/me', methods=['GET'])
def me():
    user = get_current_user_cached()
    return jsonify(UserRead.model_validate(user, from_attributes=True).model_dump(mode='json'))


@bp.route('/2fa/setup', methods=['POST'])
def setup_2fa():
    db = SessionLocal()
    try:
        user = get_current_user(db)
        secret = generate_totp_secret()
        user.totp_secret = secret
        db.commit()
        uri = get_totp_provisioning_uri(secret, user.email)
        return jsonify({'secret': secret, 'provisioning_uri': uri})
    finally:
        db.close()


@bp.route('/2fa/verify', methods=['POST'])
def verify_2fa():
    data = request.get_json()
    payload = TOTPVerifyRequest(**data)
    db = SessionLocal()
    try:
        user = get_current_user(db)
        if not user.totp_secret:
            raise Unauthorized('2FA not set up. Call /auth/2fa/setup first.')
        if not verify_totp(user.totp_secret, payload.code):
            raise Unauthorized('Invalid TOTP code')
        user.totp_enabled = True
        db.commit()
        return jsonify({'message': '2FA enabled successfully'})
    finally:
        db.close()


@bp.route('/2fa/disable', methods=['POST'])
def disable_2fa():
    data = request.get_json()
    payload = TOTPVerifyRequest(**data)
    db = SessionLocal()
    try:
        user = get_current_user(db)
        if not user.totp_enabled:
            return jsonify({'message': '2FA is not enabled'})
        if not verify_totp(user.totp_secret, payload.code):
            raise Unauthorized('Invalid TOTP code')
        user.totp_enabled = False
        user.totp_secret = None
        db.commit()
        return jsonify({'message': '2FA disabled'})
    finally:
        db.close()
