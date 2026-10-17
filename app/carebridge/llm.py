"""Thin wrapper around the Anthropic SDK: one call in, schema-checked JSON out."""

import base64
import json

import anthropic

from . import config


class LLMError(RuntimeError):
    pass


# Every prompt that writes something a person reads ends with this.
PLAIN = """
How to write: use a 4th-grade reading level. Short sentences. Everyday words. Say it straight.
Keep a medical term only when staff need it, and say what it means in plain words the first time.
No filler, no praise, no hedging words, no "I", no "as an AI", no "it's important to note", no emojis.
Rule IDs (like ADL-2) and page numbers stay exactly as they are."""


# USD per million tokens (input, output), first-party API list prices. Cost is one of IHH's two
# barriers to AI tools, so every review shows what it cost.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}


class Usage:
    """Token and cost tally for one job. Thread-safe enough for += on ints under the GIL."""

    def __init__(self):
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost = 0.0

    def add(self, model: str, usage) -> None:
        inp = (usage.input_tokens or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0) \
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        out = usage.output_tokens or 0
        pin, pout = PRICES.get(model, (0.0, 0.0))
        self.calls += 1
        self.input_tokens += inp
        self.output_tokens += out
        self.cost += inp / 1e6 * pin + out / 1e6 * pout

    def as_dict(self) -> dict:
        return {"calls": self.calls, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "usd": round(self.cost, 4)}


class NoKeyError(LLMError):
    pass


_client = None
_client_key = None


def client():
    """The one outside call. Which endpoint is a single setting (docs/closed-loop.md):
    Anthropic's API, or Claude in IHH's own Microsoft Azure (Foundry) under IHH's BAA."""
    global _client, _client_key
    key = config.get_api_key()
    if not key:
        raise NoKeyError("No Claude API key yet. Add one in Settings.")
    provider, resource = config.provider(), config.foundry_resource()
    ident = (key, provider, resource)
    if _client is None or ident != _client_key:
        if provider == "foundry":
            _client = anthropic.AnthropicFoundry(api_key=key, resource=resource, max_retries=3)
        else:
            _client = anthropic.Anthropic(api_key=key, max_retries=3)
        _client_key = ident
    return _client


def image_block(jpeg: bytes) -> dict:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(jpeg).decode()},
    }


def call_json(*, system: str, content: list, schema: dict, model: str | None = None,
              effort: str = "high", max_tokens: int = 32000, usage: Usage | None = None) -> dict:
    """Run one request with structured output and return the parsed JSON object."""
    params = dict(
        model=model or config.model(),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    if params["model"] != config.fast_model() and config.provider() == "anthropic":
        # Chart pages talk about infections and drugs; if a safety classifier misfires on
        # clinical text, the API re-runs the request on a fallback model instead of failing.
        params.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    try:
        with client().beta.messages.stream(**params) as stream:
            msg = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise LLMError("The Claude API key was rejected. Check it in Settings.") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Claude is rate limited right now. Try again in a minute.") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Could not reach the Claude API. Check the internet connection.") from e

    if usage is not None:
        usage.add(getattr(msg, "model", None) or params["model"], msg.usage)
    if msg.stop_reason == "refusal":
        raise LLMError("Claude declined this request.")
    if msg.stop_reason == "max_tokens":
        raise LLMError("Claude's answer was cut off (too long).")
    text = next((b.text for b in msg.content if b.type == "text"), None)
    if text is None:
        raise LLMError("Claude returned no answer.")
    try:
        return json.loads(text)
    except ValueError as e:
        raise LLMError("Claude's answer was not valid JSON.") from e


def strict(schema: dict) -> dict:
    """Close every object in a schema: structured outputs need additionalProperties false and
    every property required."""
    if schema.get("type") == "object":
        props = schema.get("properties", {})
        schema["additionalProperties"] = False
        schema["required"] = list(props)
        for v in props.values():
            strict(v)
    elif schema.get("type") == "array":
        strict(schema["items"])
    return schema
