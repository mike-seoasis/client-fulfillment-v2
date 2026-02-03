"""Email integration client for sending notifications via SMTP.

Features:
- Async SMTP client using aiosmtplib
- Circuit breaker for fault tolerance
- Retry logic with exponential backoff
- Request/response logging per requirements
- Handles timeouts and connection errors
- Masks credentials in all logs

ERROR LOGGING REQUIREMENTS:
- Log all outbound email sends with recipient, timing
- Log request/response at DEBUG level
- Log and handle: timeouts, connection errors, auth failures
- Include retry attempt number in logs
- Mask credentials in all logs
- Log circuit breaker state changes

RAILWAY DEPLOYMENT REQUIREMENTS:
- All credentials via environment variables
- Never log or expose credentials
- Handle cold-start latency
- Implement request timeouts
"""

import asyncio
import time
import traceback
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EmailResult:
    """Result of an email send operation."""

    success: bool
    recipient: str
    subject: str
    message_id: str | None = None
    error: str | None = None
    duration_ms: float = 0.0
    retry_attempt: int = 0


class EmailError(Exception):
    """Base exception for email errors."""

    pass


class EmailConnectionError(EmailError):
    """Raised when connection to SMTP server fails."""

    pass


class EmailAuthError(EmailError):
    """Raised when SMTP authentication fails."""

    pass


class EmailTimeoutError(EmailError):
    """Raised when email operation times out."""

    pass


class EmailCircuitOpenError(EmailError):
    """Raised when circuit breaker is open."""

    pass


class EmailClient:
    """Async client for sending emails via SMTP.

    Provides email capabilities with:
    - Circuit breaker for fault tolerance
    - Retry logic with exponential backoff
    - Comprehensive logging
    """

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        use_tls: bool | None = None,
        use_ssl: bool | None = None,
        timeout: float | None = None,
        from_email: str | None = None,
        from_name: str | None = None,
    ) -> None:
        """Initialize email client."""
        settings = get_settings()

        self._host = smtp_host or settings.smtp_host
        self._port = smtp_port or settings.smtp_port
        self._username = smtp_username or settings.smtp_username
        self._password = smtp_password or settings.smtp_password
        self._use_tls = use_tls if use_tls is not None else settings.smtp_use_tls
        self._use_ssl = use_ssl if use_ssl is not None else settings.smtp_use_ssl
        self._timeout = timeout or settings.smtp_timeout
        self._from_email = from_email or settings.smtp_from_email
        self._from_name = from_name or settings.smtp_from_name

        # Circuit breaker
        self._circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=settings.email_circuit_failure_threshold,
                recovery_timeout=settings.email_circuit_recovery_timeout,
            ),
            name="email",
        )

        self._available = bool(self._host and self._from_email)

    @property
    def available(self) -> bool:
        """Check if email client is configured."""
        return self._available

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get circuit breaker instance."""
        return self._circuit_breaker

    async def send(
        self,
        recipient: str,
        subject: str,
        body_html: str,
        body_text: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> EmailResult:
        """Send an email.

        Args:
            recipient: Recipient email address
            subject: Email subject
            body_html: HTML body content
            body_text: Plain text body content
            max_retries: Maximum retry attempts
            retry_delay: Base delay between retries

        Returns:
            EmailResult with send status and metadata
        """
        if not self._available:
            logger.warning(
                "Email client not configured",
                extra={"recipient": recipient[:50]},
            )
            return EmailResult(
                success=False,
                recipient=recipient,
                subject=subject,
                error="Email client not configured (missing SMTP settings)",
            )

        if not await self._circuit_breaker.can_execute():
            logger.warning(
                "Email circuit breaker open, rejecting send",
                extra={"recipient": recipient[:50], "subject": subject[:50]},
            )
            return EmailResult(
                success=False,
                recipient=recipient,
                subject=subject,
                error="Circuit breaker is open",
            )

        start_time = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(max_retries):
            attempt_start = time.monotonic()

            try:
                logger.debug(
                    "Sending email",
                    extra={
                        "recipient": recipient[:50],
                        "subject": subject[:50],
                        "retry_attempt": attempt,
                    },
                )

                # Build message
                message = MIMEMultipart("alternative")
                message["From"] = f"{self._from_name} <{self._from_email}>"
                message["To"] = recipient
                message["Subject"] = subject

                # Attach plain text and HTML parts
                message.attach(MIMEText(body_text, "plain", "utf-8"))
                message.attach(MIMEText(body_html, "html", "utf-8"))

                # Send via SMTP
                async with aiosmtplib.SMTP(
                    hostname=self._host,
                    port=self._port,
                    use_tls=self._use_ssl,  # Use SSL on connect
                    start_tls=self._use_tls and not self._use_ssl,  # Upgrade to TLS
                    timeout=self._timeout,
                ) as smtp:
                    if self._username and self._password:
                        await smtp.login(self._username, self._password)

                    response = await smtp.send_message(message)

                duration_ms = (time.monotonic() - attempt_start) * 1000
                total_duration_ms = (time.monotonic() - start_time) * 1000

                # Extract message ID from response if available
                message_id = None
                if response:
                    # Response is a tuple of (code, message)
                    logger.debug(
                        "Email sent successfully",
                        extra={
                            "recipient": recipient[:50],
                            "subject": subject[:50],
                            "duration_ms": round(duration_ms, 2),
                            "total_duration_ms": round(total_duration_ms, 2),
                            "retry_attempt": attempt,
                        },
                    )

                await self._circuit_breaker.record_success()

                return EmailResult(
                    success=True,
                    recipient=recipient,
                    subject=subject,
                    message_id=message_id,
                    duration_ms=total_duration_ms,
                    retry_attempt=attempt,
                )

            except aiosmtplib.SMTPAuthenticationError as e:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                logger.error(
                    "Email authentication failed",
                    extra={
                        "recipient": recipient[:50],
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "duration_ms": round(duration_ms, 2),
                        "retry_attempt": attempt,
                    },
                )
                await self._circuit_breaker.record_failure()
                # Don't retry auth errors
                return EmailResult(
                    success=False,
                    recipient=recipient,
                    subject=subject,
                    error=f"Authentication failed: {e}",
                    duration_ms=(time.monotonic() - start_time) * 1000,
                    retry_attempt=attempt,
                )

            except TimeoutError:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                logger.warning(
                    "Email send timed out",
                    extra={
                        "recipient": recipient[:50],
                        "timeout": self._timeout,
                        "duration_ms": round(duration_ms, 2),
                        "retry_attempt": attempt,
                    },
                )
                await self._circuit_breaker.record_failure()
                last_error = EmailTimeoutError(f"Timeout after {self._timeout}s")

                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    logger.info(
                        f"Retrying email send in {delay}s",
                        extra={
                            "recipient": recipient[:50],
                            "retry_attempt": attempt + 1,
                            "max_retries": max_retries,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

            except (aiosmtplib.SMTPConnectError, aiosmtplib.SMTPServerDisconnected, OSError) as e:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                logger.warning(
                    "Email connection error",
                    extra={
                        "recipient": recipient[:50],
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "duration_ms": round(duration_ms, 2),
                        "retry_attempt": attempt,
                    },
                )
                await self._circuit_breaker.record_failure()
                last_error = EmailConnectionError(f"Connection error: {e}")

                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    logger.info(
                        f"Retrying email send in {delay}s",
                        extra={
                            "recipient": recipient[:50],
                            "retry_attempt": attempt + 1,
                            "max_retries": max_retries,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

            except Exception as e:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                logger.error(
                    "Email send failed",
                    extra={
                        "recipient": recipient[:50],
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "stack_trace": traceback.format_exc(),
                        "duration_ms": round(duration_ms, 2),
                        "retry_attempt": attempt,
                    },
                )
                await self._circuit_breaker.record_failure()
                last_error = e

                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    await asyncio.sleep(delay)
                    continue

        total_duration_ms = (time.monotonic() - start_time) * 1000
        return EmailResult(
            success=False,
            recipient=recipient,
            subject=subject,
            error=str(last_error) if last_error else "Send failed after all retries",
            duration_ms=total_duration_ms,
            retry_attempt=max_retries - 1,
        )


# Global email client instance
_email_client: EmailClient | None = None


def get_email_client() -> EmailClient:
    """Get or create the global email client."""
    global _email_client
    if _email_client is None:
        _email_client = EmailClient()
        if _email_client.available:
            logger.info("Email client initialized")
        else:
            logger.info("Email client not configured (missing SMTP settings)")
    return _email_client


async def close_email_client() -> None:
    """Close the global email client."""
    global _email_client
    if _email_client is not None:
        _email_client = None
        logger.info("Email client closed")
