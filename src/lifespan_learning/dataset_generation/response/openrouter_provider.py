"""OpenRouter story provider (2026-09-23 decision: z-ai/glm-5.3 pinned to Baidu fp8).

Presents OpenRouter's chat endpoint to the pipeline as a batch provider.
OpenRouter has no batch API, so `submit_batch` runs the requests itself on
a thread pool and records every finished story in a cache file next to
--out (<out>.openrouter_cache.jsonl) as it arrives. Batch membership is
recorded there too, so a run killed mid-way resumes: the pipeline
re-supplies the prompts with `resume_items`, and the next `batch_status`
call finishes whatever is missing before reporting "ended". Nothing
already paid for is requested twice.

Provenance: the model id written into every story line is
"<model>@openrouter/<upstream>/<quantization>/reasoning=<effort>", and a
response served by any other upstream is a retryable failure, so a silent
routing change can never enter the corpus.

Reasoning: GLM 5.3 cannot run with reasoning disabled on any OpenRouter
provider (eight probed on 2026-09-23); at "low" effort it spends ~80
tokens a story, excluded from the response. max_tokens gets headroom.

Credentials come from OPEN_ROUTER_API_KEY in the environment; never read,
logged or passed as a literal here. Uses only the standard library.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Iterator

from .providers import BatchRequestItem, BatchResultItem, BatchStatus

URL = "https://openrouter.ai/api/v1/chat/completions"
REASONING_HEADROOM = 1500
RETRYABLE_STATUS = {0, 408, 409, 429}

# Generation artefacts found in the 2026-09-24 tier-0 review (1,000 stories):
# a leaked reasoning tag with the story written twice around it, a stray
# "</br>", and a story duplicated end to end. On that corpus these checks flag
# exactly those three stories and nothing else. The ending check was added
# after the r9 prompt A/B, where GLM stopped mid-word ("He put it on teddy.
# Tedd") with finish_reason "stop"; on those 1,300 stories it flags only that
# story and the "</br>" one.
# The run-together check came from the v5 tier-0 review, where two stories
# were glued to a second draft without a space ("white yard.Brielle woke up");
# on the 2,300 stories generated on 2026-09-24 it flags only such joins and one
# missing space after a closing quote.
_MARKUP_TAG = re.compile(r"</?\s*[a-zA-Z][^>]{0,20}>")
_SENTENCE_FINAL = re.compile(r"[.!?][\"'”’)]*$")
_RUN_TOGETHER = re.compile(r"[a-z][.!?][\"'”’]?[A-Z]")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s*")
_DUPLICATE_MIN_CHARS = 25
_DUPLICATE_MAX_REPEATS = 2


def story_defect(text: str) -> str:
    """Why a completion is not a usable story, or "" when it is."""
    if _MARKUP_TAG.search(text):
        return "markup tag in story"
    if not _SENTENCE_FINAL.search(text.strip()):
        return "story ends mid-sentence"
    if _RUN_TOGETHER.search(text):
        return "sentences run together"
    sentences = [s.strip() for s in _SENTENCE_END.split(text) if len(s.strip()) > _DUPLICATE_MIN_CHARS]
    if len(sentences) - len(set(sentences)) > _DUPLICATE_MAX_REPEATS:
        return "story text duplicated"
    return ""


class OpenRouterProvider:
    def __init__(
        self,
        cache_path: Path | str,
        model: str = "z-ai/glm-5.3",
        upstream: str = "Baidu",
        quantization: str = "fp8",
        reasoning_effort: str = "low",
        workers: int = 8,
        http_post: Callable[[dict], tuple[int, dict]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._model = model
        self._upstream = upstream
        self._quantization = quantization
        self._effort = reasoning_effort
        self._workers = workers
        self._cache_path = Path(cache_path)
        self._sleep = sleep
        if http_post is None:
            self._api_key = os.environ.get("OPEN_ROUTER_API_KEY", "")
            if not self._api_key:
                raise RuntimeError("OPEN_ROUTER_API_KEY is not set")
            self._http_post = self._default_http_post
        else:
            self._api_key = ""
            self._http_post = http_post
        self._results: dict[str, dict] = {}
        self._batches: dict[str, list[str]] = {}
        self._pending: dict[str, tuple[BatchRequestItem, int]] = {}
        self._load_cache()

    @property
    def model_id(self) -> str:
        return f"{self._model}@openrouter/{self._upstream}/{self._quantization}/reasoning={self._effort}"

    # -- cache -------------------------------------------------------------
    def _load_cache(self) -> None:
        if not self._cache_path.exists():
            return
        with self._cache_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if "batch_id" in row:
                    self._batches[row["batch_id"]] = row["custom_ids"]
                else:
                    self._results[row["custom_id"]] = row

    def _append_cache(self, row: dict) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self._cache_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()

    # -- HTTP --------------------------------------------------------------
    def _default_http_post(self, payload: dict) -> tuple[int, dict]:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:
                body = {"error": {"message": str(e)}}
            return e.code, body
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return 0, {"error": {"message": f"connection: {e}"}}

    @staticmethod
    def _error_message(body: dict) -> str:
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            return str(err.get("message", ""))[:200]
        return str(err or "")[:200]

    def _one(self, custom_id: str, prompt: str, max_tokens: int) -> dict:
        payload = {
            "model": self._model,
            "max_tokens": max_tokens + REASONING_HEADROOM,
            "messages": [{"role": "user", "content": prompt}],
            "reasoning": {"effort": self._effort, "exclude": True},
            "provider": {"order": [self._upstream], "allow_fallbacks": False},
        }
        last_error = ""
        for attempt in range(6):
            status, body = self._http_post(payload)
            if status in RETRYABLE_STATUS or status >= 500:
                last_error = f"{status}: {self._error_message(body)}"
                self._sleep(min(60, 2 ** attempt))
                continue
            if status != 200:
                return {"custom_id": custom_id, "outcome": "errored", "retryable": False,
                        "error": f"{status}: {self._error_message(body)}"}
            served_by = body.get("provider", "")
            if served_by != self._upstream:
                return {"custom_id": custom_id, "outcome": "errored", "retryable": True,
                        "error": f"routed to {served_by!r}, not {self._upstream!r}"}
            choice = body["choices"][0]
            text = (choice.get("message") or {}).get("content") or ""
            if choice.get("finish_reason") == "length":
                return {"custom_id": custom_id, "outcome": "errored", "retryable": True, "error": "truncated at max_tokens"}
            if not text.strip():
                return {"custom_id": custom_id, "outcome": "errored", "retryable": True, "error": "empty completion"}
            defect = story_defect(text)
            if defect:
                return {"custom_id": custom_id, "outcome": "errored", "retryable": True, "error": defect}
            usage = body.get("usage") or {}
            return {"custom_id": custom_id, "outcome": "succeeded", "text": text, "upstream": served_by,
                    "in_tokens": usage.get("prompt_tokens", 0), "out_tokens": usage.get("completion_tokens", 0)}
        return {"custom_id": custom_id, "outcome": "errored", "retryable": True, "error": f"gave up: {last_error}"}

    def _run(self, items: list[BatchRequestItem], max_tokens: int) -> None:
        # Successful and terminal-error results are final. Retryable errors are
        # deliberately re-issued when a later pipeline run resubmits their ids;
        # otherwise loading the cache makes a queued retry look complete and no
        # HTTP request is ever made.
        todo = [
            it
            for it in items
            if it.custom_id not in self._results
            or (
                self._results[it.custom_id].get("outcome") == "errored"
                and self._results[it.custom_id].get("retryable", False)
            )
        ]
        if not todo:
            return
        with ThreadPoolExecutor(max_workers=self._workers) as ex:
            futs = {ex.submit(self._one, it.custom_id, it.prompt, max_tokens): it for it in todo}
            for fut in as_completed(futs):
                row = fut.result()
                self._results[row["custom_id"]] = row
                self._append_cache(row)

    # -- StoryProvider -----------------------------------------------------
    def submit_batch(self, items: list[BatchRequestItem], max_tokens: int) -> str:
        batch_id = f"openrouter-{uuid.uuid4().hex[:12]}"
        custom_ids = [it.custom_id for it in items]
        self._batches[batch_id] = custom_ids
        self._pending = {it.custom_id: (it, max_tokens) for it in items}
        self._append_cache({"batch_id": batch_id, "custom_ids": custom_ids, "max_tokens": max_tokens})
        self._run(items, max_tokens)
        return batch_id

    def resume_items(self, items: list[BatchRequestItem], max_tokens: int) -> None:
        """Re-supply the prompts of a batch persisted by a previous run, so
        `batch_status` can finish it."""
        self._pending = {it.custom_id: (it, max_tokens) for it in items}

    def batch_status(self, batch_id: str) -> BatchStatus:
        custom_ids = self._batches.get(batch_id, [])
        missing = [c for c in custom_ids if c not in self._results]
        if missing:
            items = [self._pending[c][0] for c in missing if c in self._pending]
            if items:
                self._run(items, self._pending[items[0].custom_id][1])
        done = [self._results[c] for c in custom_ids if c in self._results]
        succeeded = sum(r["outcome"] == "succeeded" for r in done)
        errored = len(done) - succeeded
        processing = len(custom_ids) - len(done)
        return BatchStatus(
            processing_status="ended" if processing == 0 else "in_progress",
            succeeded=succeeded, errored=errored, processing=processing,
        )

    def batch_results(self, batch_id: str) -> Iterator[BatchResultItem]:
        for c in self._batches.get(batch_id, []):
            r = self._results.get(c)
            if r is None:
                yield BatchResultItem(custom_id=c, outcome="errored", retryable=True, error_message="not completed")
            elif r["outcome"] == "succeeded":
                yield BatchResultItem(custom_id=c, outcome="succeeded", text=r["text"])
            else:
                yield BatchResultItem(custom_id=c, outcome="errored", retryable=bool(r.get("retryable")), error_message=r.get("error", ""))
