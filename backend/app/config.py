import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

KNOWLEDGE_DIR = Path(os.environ.get("KNOWLEDGE_DIR", BASE_DIR / "knowledge"))
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
STATIC_DIR = Path(os.environ.get("STATIC_DIR", BASE_DIR / "frontend" / "dist" / "frontend" / "browser"))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
AWS_BEARER_TOKEN_BEDROCK = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")

# Provider selection:
#   CLAUDE_PROVIDER=anthropic  -> first-party Claude API (needs ANTHROPIC_API_KEY)
#   CLAUDE_PROVIDER=bedrock    -> Claude on Amazon Bedrock via the Mantle client
#                                 (needs AWS_BEARER_TOKEN_BEDROCK + AWS_REGION,
#                                  or standard AWS SigV4 credentials)
# If unset, the provider is inferred from which credentials are present.
_explicit_provider = os.environ.get("CLAUDE_PROVIDER", "").strip().lower()
if _explicit_provider in ("anthropic", "bedrock"):
    CLAUDE_PROVIDER = _explicit_provider
elif ANTHROPIC_API_KEY:
    CLAUDE_PROVIDER = "anthropic"
elif AWS_BEARER_TOKEN_BEDROCK:
    CLAUDE_PROVIDER = "bedrock"
else:
    CLAUDE_PROVIDER = "none"

# Model id. ANTHROPIC_MODEL is accepted as an alias for CLAUDE_MODEL.
# Bedrock model ids carry a provider/inference-profile prefix,
# e.g. "eu.anthropic.claude-opus-4-8"; first-party ids are bare, e.g. "claude-opus-4-8".
_DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-8",
    "bedrock": "eu.anthropic.claude-opus-4-8",
}
CLAUDE_MODEL = (
    os.environ.get("CLAUDE_MODEL")
    or os.environ.get("ANTHROPIC_MODEL")
    or _DEFAULT_MODELS.get(CLAUDE_PROVIDER, "claude-opus-4-8")
)

# Max tokens per agent response. Findings are structured JSON so this is generous.
AGENT_MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "8000"))
# Max tool-use round trips per regulation agent before it is forced to conclude.
AGENT_MAX_TURNS = int(os.environ.get("AGENT_MAX_TURNS", "8"))

REGULATIONS = ["AI_ACT", "GDPR", "DSA", "UCPD"]

REGULATION_LABELS = {
    "AI_ACT": "AI Act (Regulation (EU) 2024/1689)",
    "GDPR": "GDPR (Regulation (EU) 2016/679)",
    "DSA": "Digital Services Act (Regulation (EU) 2022/2065)",
    "UCPD": "Unfair Commercial Practices Directive (2005/29/EC)",
}


def llm_available() -> bool:
    return CLAUDE_PROVIDER != "none"


def make_async_client():
    """Build the async Claude client for the configured provider.

    Both clients expose the identical `messages.create` surface, so the agent
    code is provider-agnostic.
    """
    if CLAUDE_PROVIDER == "anthropic":
        from anthropic import AsyncAnthropic
        return AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    if CLAUDE_PROVIDER == "bedrock":
        from anthropic import AsyncAnthropicBedrockMantle
        # Credentials and region resolve from the environment:
        # AWS_BEARER_TOKEN_BEDROCK (Bedrock API key) or SigV4 credentials,
        # plus AWS_REGION / AWS_DEFAULT_REGION.
        return AsyncAnthropicBedrockMantle()
    return None
