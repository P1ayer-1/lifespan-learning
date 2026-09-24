"""Tests for the OpenRouter provider: no network; HTTP is injected."""
import json

from lifespan_learning.dataset_generation.response.openrouter_provider import OpenRouterProvider
from lifespan_learning.dataset_generation.response.providers import BatchRequestItem


def ok_body(text, upstream="Baidu", finish="stop"):
    return 200, {"provider": upstream, "choices": [{"finish_reason": finish, "message": {"content": text}}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 20}}


def make_provider(tmp_path, responder, **kw):
    calls = []

    def http_post(payload):
        calls.append(payload)
        return responder(payload)

    p = OpenRouterProvider(cache_path=tmp_path / "stories.jsonl.openrouter_cache.jsonl", http_post=http_post, sleep=lambda s: None, **kw)
    return p, calls


def test_model_id_carries_upstream_quantization_and_effort(tmp_path):
    p, _ = make_provider(tmp_path, lambda payload: ok_body("x"))
    assert p.model_id == "z-ai/glm-5.3@openrouter/Baidu/fp8/reasoning=low"


def test_request_pins_upstream_and_low_reasoning(tmp_path):
    p, calls = make_provider(tmp_path, lambda payload: ok_body("The story."))
    p.submit_batch([BatchRequestItem("h1", "Write.")], max_tokens=2500)
    payload = calls[0]
    assert payload["model"] == "z-ai/glm-5.3"
    assert payload["provider"] == {"order": ["Baidu"], "allow_fallbacks": False}
    assert payload["reasoning"] == {"effort": "low", "exclude": True}
    assert payload["max_tokens"] > 2500  # headroom for the reasoning tokens
    assert payload["messages"] == [{"role": "user", "content": "Write."}]


def test_roundtrip_and_cache_resume(tmp_path):
    p, calls = make_provider(tmp_path, lambda payload: ok_body("Story for " + payload["messages"][0]["content"] + "."))
    items = [BatchRequestItem("h1", "one"), BatchRequestItem("h2", "two")]
    bid = p.submit_batch(items, 2500)
    assert p.batch_status(bid).processing_status == "ended"
    got = {r.custom_id: r for r in p.batch_results(bid)}
    assert got["h1"].outcome == "succeeded" and got["h1"].text == "Story for one."
    assert len(calls) == 2

    # a new provider instance on the same cache knows the batch and re-requests nothing
    p2, calls2 = make_provider(tmp_path, lambda payload: ok_body("SHOULD NOT BE CALLED"))
    assert p2.batch_status(bid).processing_status == "ended"
    assert {r.custom_id: r.text for r in p2.batch_results(bid)}["h2"] == "Story for two."
    assert calls2 == []


def test_killed_mid_batch_resumes_only_the_missing(tmp_path):
    # simulate a batch record with two ids but only one cached result
    cache = tmp_path / "stories.jsonl.openrouter_cache.jsonl"
    cache.write_text(json.dumps({"batch_id": "openrouter-abc", "custom_ids": ["h1", "h2"], "max_tokens": 2500}) + "\n"
                     + json.dumps({"custom_id": "h1", "outcome": "succeeded", "text": "done already"}) + "\n", encoding="utf-8")
    p, calls = make_provider(tmp_path, lambda payload: ok_body("fresh."))
    p.resume_items([BatchRequestItem("h1", "one"), BatchRequestItem("h2", "two")], 2500)
    status = p.batch_status("openrouter-abc")
    assert status.processing_status == "ended" and status.succeeded == 2
    assert [c["messages"][0]["content"] for c in calls] == ["two"]
    got = {r.custom_id: r.text for r in p.batch_results("openrouter-abc")}
    assert got == {"h1": "done already", "h2": "fresh."}


def test_resubmission_reissues_retryable_cached_error(tmp_path):
    cache = tmp_path / "stories.jsonl.openrouter_cache.jsonl"
    cache.write_text(
        json.dumps({
            "custom_id": "h1",
            "outcome": "errored",
            "retryable": True,
            "error": "gave up: 429: Provider returned error",
        }) + "\n",
        encoding="utf-8",
    )

    provider, calls = make_provider(tmp_path, lambda payload: ok_body("retried successfully."))
    batch_id = provider.submit_batch([BatchRequestItem("h1", "one")], 2500)

    assert len(calls) == 1
    result = next(provider.batch_results(batch_id))
    assert result.outcome == "succeeded"
    assert result.text == "retried successfully."


def test_wrong_upstream_truncation_and_empty_are_retryable(tmp_path):
    def responder(payload):
        text = payload["messages"][0]["content"]
        if text == "routed":
            return ok_body("x", upstream="DeepInfra")
        if text == "long":
            return ok_body("x", finish="length")
        return ok_body("   ")

    p, _ = make_provider(tmp_path, responder)
    bid = p.submit_batch([BatchRequestItem("a", "routed"), BatchRequestItem("b", "long"), BatchRequestItem("c", "empty")], 2500)
    got = {r.custom_id: r for r in p.batch_results(bid)}
    assert all(r.outcome == "errored" and r.retryable for r in got.values())
    assert "DeepInfra" in got["a"].error_message
    assert "truncated" in got["b"].error_message
    assert "empty" in got["c"].error_message


def test_4xx_is_not_retried_and_5xx_is(tmp_path):
    attempts = {"n": 0}

    def responder(payload):
        text = payload["messages"][0]["content"]
        if text == "bad":
            return 400, {"error": {"message": "nope"}}
        attempts["n"] += 1
        if attempts["n"] < 3:
            return 503, {"error": {"message": "busy"}}
        return ok_body("finally.")

    p, calls = make_provider(tmp_path, responder)
    bid = p.submit_batch([BatchRequestItem("a", "bad"), BatchRequestItem("b", "flaky")], 2500)
    got = {r.custom_id: r for r in p.batch_results(bid)}
    assert got["a"].outcome == "errored" and not got["a"].retryable and "400" in got["a"].error_message
    assert got["b"].outcome == "succeeded" and got["b"].text == "finally."
    assert sum(c["messages"][0]["content"] == "bad" for c in calls) == 1


# story_defect: generation artefacts are retryable failures, never corpus lines
import pytest

from lifespan_learning.dataset_generation.response.openrouter_provider import story_defect

DUPLICATED = ("Victor wanted to build a big tower in the room. He put one red block on the floor today. "
              "Then he added a blue block on top of it slowly. The tower fell down with a loud crash. ") * 2


@pytest.mark.parametrize("text, defect", [
    ("Mia ran to the park. She saw a duck.", ""),
    ('"Drip, drip, drip," said Mia. "Drip, drip, drip," said Dad.', ""),
    ("Mia ran.</think>Mia ran to the park.", "markup tag in story"),
    ("Mia ran.</br>She saw a duck.", "markup tag in story"),
    (DUPLICATED, "story text duplicated"),
    ('"Sleep, baby," she said. "Sleep."\n', ""),
    ("He found a blanket. He put it on teddy. Tedd", "story ends mid-sentence"),
])
def test_story_defect(text, defect):
    assert story_defect(text) == defect


def test_defective_story_is_a_retryable_error_and_is_reissued(tmp_path):
    p, calls = make_provider(tmp_path, lambda payload: ok_body("Mia ran.</think>Mia ran to the park."))
    bid = p.submit_batch([BatchRequestItem("h1", "one")], 2500)
    result = next(p.batch_results(bid))
    assert result.outcome == "errored" and result.retryable and result.error_message == "markup tag in story"

    p2, calls2 = make_provider(tmp_path, lambda payload: ok_body("Mia ran to the park."))
    bid2 = p2.submit_batch([BatchRequestItem("h1", "one")], 2500)
    assert len(calls2) == 1 and next(p2.batch_results(bid2)).text == "Mia ran to the park."
