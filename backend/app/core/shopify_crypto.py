"""Fernet symmetric encryption for Shopify access tokens.

The encryption key is loaded from the SHOPIFY_TOKEN_ENCRYPTION_KEY env var.
Tokens are encrypted before DB storage and decrypted when needed for API calls.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ShopifyCryptoError(Exception):
    """Raised when encryption/decryption fails."""


def _get_fernet() -> Fernet:
    """Get a Fernet instance using the configured encryption key."""
    settings = get_settings()
    key = settings.shopify_token_encryption_key
    if not key:
        raise ShopifyCryptoError("SHOPIFY_TOKEN_ENCRYPTION_KEY is not configured")
    return Fernet(key.encode())


def encrypt_token(token: str) -> str:
    """Encrypt a Shopify access token for database storage.

    Args:
        token: The plaintext access token from Shopify OAuth.

    Returns:
        Base64-encoded encrypted token string.
    """
    f = _get_fernet()
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored Shopify access token for API calls.

    Args:
        encrypted_token: The encrypted token from the database.

    Returns:
        The plaintext access token.

    Raises:
        ShopifyCryptoError: If decryption fails (wrong key, corrupted data).
    """
    f = _get_fernet()
    try:
        return f.decrypt(encrypted_token.encode()).decode()
    except InvalidToken as e:
        logger.error("Failed to decrypt Shopify token — key mismatch or corrupted data")
        raise ShopifyCryptoError("Failed to decrypt Shopify access token") from e
