"""Encryption for stored target-app credentials (§22 auth_profiles, §29.5). Never store plaintext."""
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class CredentialError(Exception):
    pass


def _fernet() -> Fernet:
    if not settings.dragonfly_secret_key:
        raise CredentialError("DRAGONFLY_SECRET_KEY is not configured, so credentials cannot be stored or used")
    try:
        return Fernet(settings.dragonfly_secret_key.encode())
    except ValueError as e:
        raise CredentialError("DRAGONFLY_SECRET_KEY is not a valid Fernet key") from e


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise CredentialError("stored credential cannot be decrypted (was DRAGONFLY_SECRET_KEY changed?)") from e
