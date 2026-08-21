"""Structured, provider-neutral Understanding Adapter v1 experiment."""

from .structured_adapter import (
    StructuredUnderstandingAdapter,
    TranscriptTransport,
    Transport,
)
from .remote_transport import (
    OpenAICompatibleRemoteTransport,
    RemoteTransportConfig,
    load_remote_transport_config,
    sha256_file,
)
from .env_file import load_env_file

__all__ = [
    "StructuredUnderstandingAdapter",
    "TranscriptTransport",
    "Transport",
    "OpenAICompatibleRemoteTransport",
    "RemoteTransportConfig",
    "load_remote_transport_config",
    "load_env_file",
    "sha256_file",
]
