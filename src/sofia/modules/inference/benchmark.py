"""Reviewed, non-installing Ollama benchmark adapter for HNF-06."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from time import perf_counter

from ollama import Client

from sofia.platform.config.model import ProviderConfiguration


_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class OllamaBenchmarkObservation:
    model_id: str
    model_digest: str
    time_to_first_token_ms: float
    total_duration_ms: float
    load_duration_ms: float
    prompt_tokens: int
    prompt_tokens_per_second: float
    generated_tokens: int
    generated_tokens_per_second: float
    response_sha256: str


class OllamaBenchmarkAdapter:
    """Measure one already-installed exact model; never install or dispatch tools."""

    SYNTHETIC_PROMPT = (
        "Return exactly the lowercase word benchmark. This is a synthetic "
        "performance probe and contains no user data."
    )

    def __init__(self, configuration: ProviderConfiguration, *, client: Client | None = None) -> None:
        if not isinstance(configuration, ProviderConfiguration):
            raise TypeError("configuration must be ProviderConfiguration")
        if configuration.provider != "ollama":
            raise ValueError("Ollama benchmark requires the Ollama provider")
        self.configuration = configuration
        self.client = client if client is not None else Client()

    @staticmethod
    def _field(value, name, default=None):
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)

    def _installed_digest(self) -> str:
        listing = self.client.list()
        models = self._field(listing, "models")
        if not isinstance(models, (list, tuple)):
            raise RuntimeError("Ollama model inventory is unavailable")
        for model in models:
            name = self._field(model, "model", self._field(model, "name"))
            if name != self.configuration.model:
                continue
            digest = self._field(model, "digest")
            if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
                raise RuntimeError("installed model digest is unavailable")
            return digest
        raise RuntimeError("selected model is not already installed")

    @staticmethod
    def _duration_ms(value, label: str) -> float:
        if type(value) not in (int, float) or value < 0:
            raise RuntimeError(f"Ollama {label} metric is unavailable")
        return float(value) / 1_000_000.0

    @staticmethod
    def _count(value, label: str) -> int:
        if type(value) is not int or value < 0:
            raise RuntimeError(f"Ollama {label} metric is unavailable")
        return value

    def run(self, *, expected_digest: str, cancel) -> OllamaBenchmarkObservation:
        if not isinstance(expected_digest, str) or _DIGEST.fullmatch(expected_digest) is None:
            raise ValueError("expected model digest must be SHA-256")
        if not hasattr(cancel, "is_set"):
            raise TypeError("cancellation event required")
        if cancel.is_set():
            raise InterruptedError("benchmark cancelled before inference")
        if self._installed_digest() != expected_digest:
            raise PermissionError("installed model digest differs from admitted inventory")
        options = {"temperature": 0, "num_predict": 32}
        if self.configuration.seed is not None:
            options["seed"] = self.configuration.seed
        if self.configuration.context_size is not None:
            options["num_ctx"] = self.configuration.context_size
        started = perf_counter(); first = None; final = None; content: list[str] = []
        stream = self.client.chat(
            model=self.configuration.model,
            messages=({"role": "user", "content": self.SYNTHETIC_PROMPT},),
            options=options, stream=True, tools=None,
        )
        try:
            for chunk in stream:
                if cancel.is_set():
                    raise InterruptedError("benchmark cancelled during inference")
                message = self._field(chunk, "message")
                text = "" if message is None else self._field(message, "content", "")
                if text:
                    if not isinstance(text, str):
                        raise RuntimeError("Ollama streamed non-text content")
                    if first is None:
                        first = perf_counter()
                    content.append(text)
                final = chunk
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()
        ended = perf_counter()
        if final is None or first is None:
            raise RuntimeError("Ollama benchmark returned no generated token")
        if self._installed_digest() != expected_digest:
            raise RuntimeError("installed model digest changed during benchmark")
        prompt_count = self._count(self._field(final, "prompt_eval_count"), "prompt token")
        generated_count = self._count(self._field(final, "eval_count"), "generated token")
        prompt_ms = self._duration_ms(self._field(final, "prompt_eval_duration"), "prompt duration")
        generated_ms = self._duration_ms(self._field(final, "eval_duration"), "generation duration")
        load_ms = self._duration_ms(self._field(final, "load_duration"), "load duration")
        total_ms = self._duration_ms(self._field(final, "total_duration"), "total duration")
        return OllamaBenchmarkObservation(
            self.configuration.model, expected_digest,
            max(0.0, (first - started) * 1000), total_ms, load_ms,
            prompt_count, 0.0 if prompt_ms == 0 else prompt_count / (prompt_ms / 1000),
            generated_count,
            0.0 if generated_ms == 0 else generated_count / (generated_ms / 1000),
            sha256("".join(content).encode("utf-8")).hexdigest(),
        )
