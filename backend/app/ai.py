"""Claude provider (§20.7): one structured-output call shape shared by the planner and the failure analyst."""
from pydantic import BaseModel

from app.config import settings


def enabled() -> bool:
    return bool(settings.anthropic_api_key)


def model_tag(prompt_version: str) -> str:
    return f"claude:{settings.ai_model}:{prompt_version}"


def structured[T: BaseModel](system: str, user: str, schema: type[T], max_tokens: int = 16000) -> T:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    resp = client.beta.messages.parse(
        model=settings.ai_model,
        max_tokens=max_tokens,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # on a safety-classifier refusal, the API retries on a fallback model
        output_config={"effort": settings.ai_effort},
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("model refused")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("model output truncated (max_tokens)")
    return resp.parsed_output
