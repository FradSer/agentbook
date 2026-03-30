import httpx
from agno.agent import Agent
from agno.models.openai.like import OpenAILike

from agent.src.config import settings
from agent.src.tools import get_reviewer_tools


class _StripAuthAsyncTransport(httpx.AsyncHTTPTransport):
    """Remove Authorization header so CF Gateway doesn't forward it to the upstream provider."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request.headers.pop("authorization", None)
        return await super().handle_async_request(request)


def _build_model() -> OpenAILike:
    if settings.cf_aig_url and settings.cf_aig_token:
        async_client = httpx.AsyncClient(transport=_StripAuthAsyncTransport())
        return OpenAILike(
            id=settings.agent_model_name,
            base_url=settings.cf_aig_url,
            api_key="not-needed",
            default_headers={"cf-aig-authorization": f"Bearer {settings.cf_aig_token}"},
            http_client=async_client,
        )
    from agno.models.openrouter import OpenRouter

    return OpenRouter(id=settings.agent_model_name, api_key=settings.openrouter_api_key)


REVIEWER_INSTRUCTIONS = """You are a binary spam detector for the agentbook platform.

Your only job is to decide: APPROVE or REJECT each piece of content.

Rules:
- APPROVE: genuine content, even if low quality or poorly written
- REJECT: spam, promotional content, gibberish, or malicious content

For each item, call exactly one tool: approve_content or reject_content.
Do not add commentary beyond calling the tool.
"""


def create_reviewer_agent(service) -> Agent:
    """
    Create ReviewerAgent instance with tools and configuration

    Args:
        service: AgentbookService instance for database operations

    Returns:
        Configured Agno Agent
    """
    agent = Agent(
        name="ReviewerAgent",
        model=_build_model(),
        tools=get_reviewer_tools(service),
        instructions=REVIEWER_INSTRUCTIONS,
        markdown=True,
    )

    return agent
