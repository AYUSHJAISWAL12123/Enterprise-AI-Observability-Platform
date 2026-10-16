# obs_sdk

Client SDK for AI apps to emit GenAI telemetry to the obs-platform ingestion gateway.

## Quick start

```python
from obs_core.schemas import GenAIMessage, MessageRole, ModelInfo, TokenUsage
from obs_sdk import HttpGatewayClient, Span

async with HttpGatewayClient(
    gateway_url="https://obs-gateway.internal",
    api_key="...",  # from Workload Identity / Secret Manager
) as client:
    async with Span(
        client=client,
        trace_id=otel_context.trace_id,
        model=ModelInfo(provider="google", name="gemini-2.0-flash-001"),
        application_name="my-rag-app",
    ) as span:
        span.add_message(GenAIMessage(role=MessageRole.USER, content=user_prompt))
        response = await llm.generate(user_prompt)
        span.add_message(GenAIMessage(role=MessageRole.ASSISTANT, content=response.text))
        span.set_token_usage(TokenUsage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
        ))
# Event is POSTed to the gateway on Span exit.
```

## Testing your app (inject a fake)

```python
from obs_sdk import GatewayClientProtocol

class FakeClient:
    def __init__(self): self.sent = []
    async def send_event(self, event): self.sent.append(event)

# FakeClient satisfies GatewayClientProtocol structurally — no subclassing needed.
```

## Configuration

| Parameter | Default | Notes |
|---|---|---|
| `gateway_url` | required | Base URL, no trailing slash |
| `api_key` | required | Bearer token |
| `timeout` | `10.0` | Per-request timeout (seconds) |
| `max_retries` | `3` | Retries on 5xx / network errors |

## Running tests

```bash
uv sync --all-extras
uv run pytest packages/obs_sdk/tests -v
```
