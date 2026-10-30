import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, type=Type.ID)
# Used to equalize password verification work for unknown accounts.
_dummy_hash = hasher.hash(secrets.token_urlsafe(32))


def verify_password(stored: str | None, password: str) -> bool:
    try:
        result = hasher.verify(stored or _dummy_hash, password)
        return bool(stored) and result
    except (VerificationError, InvalidHashError):
        return False


def opaque_token() -> str:
    return secrets.token_urlsafe(48)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def private_key(secret: str, value: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()
