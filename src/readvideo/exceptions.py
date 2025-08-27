"""Simple exceptions for ReadVideo application."""

from typing import Any, Optional


class ReadVideoError(Exception):
    """Base exception for ReadVideo application."""
    
    def __init__(self, message: str, error_code: str = "RV_ERROR", context: Optional[dict] = None):
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}


class ValidationError(ReadVideoError):
    """Exception for validation failures (URLs, file paths, etc)."""
    
    def __init__(self, message: str, validation_type: str = "unknown", invalid_value: Any = None):
        super().__init__(
            message, 
            error_code=f"RV_VALIDATION_{validation_type.upper()}", 
            context={"validation_type": validation_type, "invalid_value": str(invalid_value)}
        )


class NetworkError(ReadVideoError):
    """Exception for network-related failures."""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(
            message,
            error_code="RV_NETWORK_ERROR",
            context={"status_code": status_code} if status_code else {}
        )


class ProcessingError(ReadVideoError):
    """Exception for processing failures (transcription, audio, etc)."""
    
    def __init__(self, message: str, processing_type: str = "unknown"):
        super().__init__(
            message,
            error_code=f"RV_PROCESSING_{processing_type.upper()}",
            context={"processing_type": processing_type}
        )


# Backwards compatibility aliases
DependencyError = ProcessingError
ConfigurationError = ValidationError
ResourceError = ProcessingError
TranscriptFetchError = NetworkError
AudioProcessingError = ProcessingError
SupadataFetchError = NetworkError
RetryableTranscriptError = NetworkError