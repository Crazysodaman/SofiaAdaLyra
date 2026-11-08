"""Legacy Sofía response policy over the generic Ollama transport.

Existing import paths preserve their personal behavior. Neutral consumers use
``ollama_transport.GenericOllamaProvider`` explicitly.
"""
from ollama import Client

from sofia.sdk.cognition_model import CognitiveRequest, CognitiveResponse
from sofia.sdk.cognition_engine import LLMProviderError
from sofia.platform.core_worker.ollama_transport import (
    GenericOllamaProvider, OLLAMA_IO_TIMEOUT_SECONDS,
)
from sofia.core.cognition.repetition_guard import (
    naturalize_embodied_semantics,
    response_quality_issue,
    trim_generic_assistant_closer,
)
from sofia.core.cognition.quality_repair import (
    build_rephrase_request,
    grounded_quality_fallback,
)


class OllamaProvider(GenericOllamaProvider):
    """Compatibility adapter retaining existing personal response handling."""

    @staticmethod
    def _new_client(endpoint: str):
        # Preserve the existing injectable client construction boundary.
        return Client(host=endpoint, timeout=OLLAMA_IO_TIMEOUT_SECONDS)

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        response = self._respond_once(request)
        response = naturalize_embodied_semantics(request, response)
        response = trim_generic_assistant_closer(request, response)
        issue = response_quality_issue(request, response)
        if issue is None:
            return response

        # Quality retries must not execute or solicit tools. A model response
        # containing tool calls is returned to the authoritative dispatcher,
        # not retried by the text-only quality repair path.
        if response.tool_calls:
            return response
        # A single retry prevents latency spirals. Neither candidate is saved
        # or executed by this provider.
        try:
            alternate = self._respond_once(build_rephrase_request(request, issue=issue))
        except LLMProviderError:
            fallback = grounded_quality_fallback(request, issue=issue)
            return fallback if fallback is not None else response
        alternate = naturalize_embodied_semantics(request, alternate)
        alternate = trim_generic_assistant_closer(request, alternate)
        alternate_issue = None
        if alternate.content.strip() and not alternate.tool_calls:
            alternate_issue = response_quality_issue(request, alternate)
            if alternate_issue is None:
                return alternate
        fallback = grounded_quality_fallback(
            request,
            issue=alternate_issue or issue,
        )
        if fallback is not None:
            return fallback
        return response
