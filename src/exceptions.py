"""
Custom exceptions for audiobook generator.
"""


class AudiobookGeneratorError(Exception):
    """Base exception for audiobook generator."""
    
    def __init__(self, message: str, error_code: str = "UNKNOWN", details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            return f"[{self.error_code}] {self.message} - Details: {self.details}"
        return f"[{self.error_code}] {self.message}"


class ConfigurationError(AudiobookGeneratorError):
    """Configuration related errors."""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, error_code="CONFIG_ERROR", details=details)


class TTSError(AudiobookGeneratorError):
    """TTS generation errors."""
    
    def __init__(self, message: str, backend: str = None, details: dict = None):
        super().__init__(message, error_code="TTS_ERROR", details=details)
        self.backend = backend


class VoiceCloneError(AudiobookGeneratorError):
    """Voice cloning errors."""
    
    def __init__(self, message: str, sample_path: str = None, details: dict = None):
        super().__init__(message, error_code="VOICE_CLONE_ERROR", details=details)
        self.sample_path = sample_path


class TextProcessingError(AudiobookGeneratorError):
    """Text processing errors."""
    
    def __init__(self, message: str, file_path: str = None, details: dict = None):
        super().__init__(message, error_code="TEXT_PROCESS_ERROR", details=details)
        self.file_path = file_path


class AudioProcessingError(AudiobookGeneratorError):
    """Audio processing errors."""
    
    def __init__(self, message: str, file_path: str = None, details: dict = None):
        super().__init__(message, error_code="AUDIO_PROCESS_ERROR", details=details)
        self.file_path = file_path


class FileFormatError(AudiobookGeneratorError):
    """Unsupported file format errors."""
    
    def __init__(self, message: str, file_path: str = None, supported_formats: list = None):
        super().__init__(message, error_code="FILE_FORMAT_ERROR")
        self.file_path = file_path
        self.supported_formats = supported_formats or []


class APIError(AudiobookGeneratorError):
    """API related errors."""
    
    def __init__(self, message: str, status_code: int = None, response: str = None):
        super().__init__(message, error_code="API_ERROR")
        self.status_code = status_code
        self.response = response


class RateLimitError(APIError):
    """Rate limit exceeded errors."""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        super().__init__(message, status_code=429)
        self.error_code = "RATE_LIMIT_ERROR"
        self.retry_after = retry_after


class ValidationError(AudiobookGeneratorError):
    """Input validation errors."""
    
    def __init__(self, message: str, field: str = None, value: Any = None):
        super().__init__(message, error_code="VALIDATION_ERROR")
        self.field = field
        self.value = value


class ResourceNotFoundError(AudiobookGeneratorError):
    """Resource not found errors."""
    
    def __init__(self, message: str, resource_type: str = None, resource_id: str = None):
        super().__init__(message, error_code="NOT_FOUND")
        self.resource_type = resource_type
        self.resource_id = resource_id


def get_user_friendly_message(error: Exception) -> str:
    """
    Get a user-friendly error message.
    
    Args:
        error: The exception that occurred
        
    Returns:
        User-friendly error message with suggestions
    """
    if isinstance(error, ConfigurationError):
        return (
            f"❌ Configuration Error: {error.message}\n"
            f"\nPlease check your configuration file or environment variables.\n"
            f"Run with --help for more information."
        )
    
    elif isinstance(error, TTSError):
        suggestions = []
        if error.backend == "elevenlabs":
            suggestions.append("• Check your ElevenLabs API key")
            suggestions.append("• Verify you have sufficient credits")
        elif error.backend == "doubao":
            suggestions.append("• Check your Doubao App ID and Access Token")
            suggestions.append("• Verify your account has TTS access")
        elif error.backend == "xtts":
            suggestions.append("• Ensure you have sufficient GPU memory")
            suggestions.append("• Try reducing chunk size")
        
        return (
            f"❌ TTS Error ({error.backend}): {error.message}\n"
            f"\nSuggestions:\n" + "\n".join(suggestions)
        )
    
    elif isinstance(error, VoiceCloneError):
        return (
            f"❌ Voice Cloning Error: {error.message}\n"
            f"\nPlease ensure:\n"
            f"• The audio file exists and is readable\n"
            f"• The sample is 10-20 seconds of clear speech\n"
            f"• The file format is supported (WAV, MP3)"
        )
    
    elif isinstance(error, FileFormatError):
        formats = ", ".join(error.supported_formats) if error.supported_formats else "TXT, EPUB, PDF"
        return (
            f"❌ File Format Error: {error.message}\n"
            f"\nSupported formats: {formats}\n"
            f"Please convert your file to a supported format."
        )
    
    elif isinstance(error, RateLimitError):
        retry_msg = f" Retry after {error.retry_after} seconds." if error.retry_after else ""
        return (
            f"⏳ Rate Limit Exceeded: {error.message}{retry_msg}\n"
            f"\nSuggestions:\n"
            f"• Reduce the number of concurrent workers (--workers)\n"
            f"• Wait a moment and try again\n"
            f"• Consider upgrading your API plan"
        )
    
    elif isinstance(error, ResourceNotFoundError):
        return (
            f"❌ Not Found: {error.message}\n"
            f"\nPlease check:\n"
            f"• The file path is correct\n"
            f"• The file exists and is readable"
        )
    
    else:
        return (
            f"❌ An unexpected error occurred: {str(error)}\n"
            f"\nPlease check the logs for more details.\n"
            f"If the problem persists, please report this issue."
        )
