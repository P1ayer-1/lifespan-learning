"""Provider interface for story generation, plus the Claude Batch API
implementation and a fake for tests.

The pipeline in `generate_responses.py` knows nothing about Anthropic
specifically: it only calls `StoryProvider.submit_batch`,
`.batch_status` and `.batch_results`. Swapping providers is writing one
new class here, not touching the pipeline.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator, Protocol


@dataclass(frozen=True)
class BatchRequestItem:
    """One story request. `custom_id` is always the prompt_hash."""
    custom_id: str
    prompt: str


@dataclass(frozen=True)
class BatchStatus:
    processing_status: str  # e.g. "in_progress", "ended"
    succeeded: int
    errored: int
    processing: int


@dataclass(frozen=True)
class BatchResultItem:
    custom_id: str
    outcome: str  # "succeeded" | "errored" | "canceled" | "expired"
    text: str | None = None
    retryable: bool = False  # only meaningful when outcome == "errored"
    error_message: str = ""


class StoryProvider(Protocol):
    """Everything the pipeline needs from a story-generation provider."""

    @property
    def model_id(self) -> str:
        """The resolved model id string, written verbatim into every output line."""
        ...

    def submit_batch(self, items: list[BatchRequestItem], max_tokens: int) -> str:
        """Submit a batch of requests; returns a provider batch id."""
        ...

    def batch_status(self, batch_id: str) -> BatchStatus:
        ...

    def batch_results(self, batch_id: str) -> Iterator[BatchResultItem]:
        """Yield one result per request, in ANY order. Callers must key by custom_id."""
        ...


class AnthropicBatchProvider:
    """Claude Message Batches API (https://docs.anthropic.com), async, ~half price.

    Credentials come from ANTHROPIC_API_KEY in the environment (the SDK's
    default `anthropic.Anthropic()` resolves it) -- never read, logged or
    passed as a literal here.
    """

    def __init__(self, model: str = "claude-haiku-4-5"):
        import anthropic  # imported lazily so tests never require the package

        self._anthropic = anthropic
        self._client = anthropic.Anthropic()
        self._model = model

    @property
    def model_id(self) -> str:
        return self._model

    def submit_batch(self, items: list[BatchRequestItem], max_tokens: int) -> str:
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request

        requests = [
            Request(
                custom_id=item.custom_id,
                params=MessageCreateParamsNonStreaming(
                    model=self._model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": item.prompt}],
                ),
            )
            for item in items
        ]
        batch = self._client.messages.batches.create(requests=requests)
        return batch.id

    def batch_status(self, batch_id: str) -> BatchStatus:
        batch = self._client.messages.batches.retrieve(batch_id)
        counts = batch.request_counts
        return BatchStatus(
            processing_status=batch.processing_status,
            succeeded=counts.succeeded,
            errored=counts.errored,
            processing=counts.processing,
        )

    def batch_results(self, batch_id: str) -> Iterator[BatchResultItem]:
        for result in self._client.messages.batches.results(batch_id):
            outcome = result.result.type
            if outcome == "succeeded":
                message = result.result.message
                text = next((b.text for b in message.content if b.type == "text"), "")
                if message.stop_reason == "max_tokens":
                    # A story cut off at max_tokens is a failure to retry, not a story.
                    yield BatchResultItem(
                        custom_id=result.custom_id,
                        outcome="errored",
                        retryable=True,
                        error_message="truncated at max_tokens",
                    )
                else:
                    yield BatchResultItem(custom_id=result.custom_id, outcome="succeeded", text=text)
            elif outcome == "errored":
                error_type = result.result.error.type
                # invalid_request errors are 4xx-shaped: never retry them.
                retryable = error_type != "invalid_request"
                yield BatchResultItem(
                    custom_id=result.custom_id,
                    outcome="errored",
                    retryable=retryable,
                    error_message=f"{error_type}: {getattr(result.result.error, 'message', '')}",
                )
            elif outcome == "expired":
                yield BatchResultItem(custom_id=result.custom_id, outcome="expired", retryable=True)
            else:  # "canceled"
                yield BatchResultItem(custom_id=result.custom_id, outcome="canceled", retryable=True)


class FakeBatchProvider:
    """In-memory provider for tests. No network calls.

    `script` maps custom_id -> a BatchResultItem to return (or a callable
    producing one), so tests can simulate successes, permanent 4xx-style
    errors, and retryable errors without touching the real API.
    """

    def __init__(self, model: str = "fake-model-1", results_by_custom_id: dict[str, BatchResultItem] | None = None):
        self._model = model
        self._results_by_custom_id = results_by_custom_id or {}
        self.submitted_batches: dict[str, list[BatchRequestItem]] = {}
        self._next_batch_id = 0

    @property
    def model_id(self) -> str:
        return self._model

    def submit_batch(self, items: list[BatchRequestItem], max_tokens: int) -> str:
        self._next_batch_id += 1
        batch_id = f"fake-batch-{self._next_batch_id}"
        self.submitted_batches[batch_id] = list(items)
        return batch_id

    def batch_status(self, batch_id: str) -> BatchStatus:
        items = self.submitted_batches[batch_id]
        return BatchStatus(processing_status="ended", succeeded=len(items), errored=0, processing=0)

    def batch_results(self, batch_id: str) -> Iterator[BatchResultItem]:
        for item in self.submitted_batches[batch_id]:
            if item.custom_id in self._results_by_custom_id:
                yield self._results_by_custom_id[item.custom_id]
            else:
                yield BatchResultItem(
                    custom_id=item.custom_id,
                    outcome="succeeded",
                    text=f"[fake story for {item.custom_id}]",
                )


def poll_until_ended(provider: StoryProvider, batch_id: str, poll_seconds: float = 20.0, timeout_seconds: float = 3600.0) -> BatchStatus:
    """Block until the batch ends, or return the last status after timeout_seconds.

    A caller that gets a non-"ended" status back should stop and let a later
    invocation resume polling (see `generate_responses.py`'s persisted batch
    state) rather than block indefinitely -- batches can take up to 24 hours.
    """
    start = time.monotonic()
    status = provider.batch_status(batch_id)
    while status.processing_status != "ended" and time.monotonic() - start < timeout_seconds:
        time.sleep(poll_seconds)
        status = provider.batch_status(batch_id)
    return status
