"""tests/test_admin_and_webhook_security.py — superadmin access control and webhook signature verification."""

from fastapi import HTTPException
import pytest

from app.api.routes.admin_routes import require_superadmin


def test_regular_user_blocked_from_admin(make_user):
    user = make_user()
    user.is_superadmin = False
    with pytest.raises(HTTPException) as exc_info:
        require_superadmin(user)
    assert exc_info.value.status_code == 403


def test_superadmin_allowed(make_user):
    user = make_user()
    user.is_superadmin = True
    result = require_superadmin(user)
    assert result.is_superadmin is True


def test_webhook_signature_rejects_wrong_secret():
    from app.core.config import settings
    from app.api.routes.webhook_routes import _verify_vapi_signature
    from fastapi import HTTPException as HTTPExc
    from unittest.mock import MagicMock

    settings.VAPI_WEBHOOK_SECRET = "correct-secret"
    fake_request = MagicMock()
    fake_request.headers.get.return_value = "wrong-secret"

    with pytest.raises(HTTPExc) as exc_info:
        _verify_vapi_signature(fake_request)
    assert exc_info.value.status_code == 401
    settings.VAPI_WEBHOOK_SECRET = ""  # reset


def test_webhook_signature_accepts_correct_secret():
    from app.core.config import settings
    from app.api.routes.webhook_routes import _verify_vapi_signature
    from unittest.mock import MagicMock

    settings.VAPI_WEBHOOK_SECRET = "correct-secret"
    fake_request = MagicMock()
    fake_request.headers.get.return_value = "correct-secret"

    _verify_vapi_signature(fake_request)  # should not raise
    settings.VAPI_WEBHOOK_SECRET = ""  # reset


def test_webhook_signature_skipped_when_no_secret_configured():
    from app.core.config import settings
    from app.api.routes.webhook_routes import _verify_vapi_signature
    from unittest.mock import MagicMock

    settings.VAPI_WEBHOOK_SECRET = ""
    fake_request = MagicMock()
    fake_request.headers.get.return_value = None

    _verify_vapi_signature(fake_request)  # should not raise — no secret configured yet
