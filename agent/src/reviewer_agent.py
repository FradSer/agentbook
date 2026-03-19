from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from agent.src.config import settings
from agent.src.tools import get_reviewer_tools

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
        model=OpenRouter(
            id=settings.agent_model_name, api_key=settings.openrouter_api_key
        ),
        tools=get_reviewer_tools(service),
        instructions=REVIEWER_INSTRUCTIONS,
        markdown=True,
    )

    return agent
