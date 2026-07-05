import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

KNOWLEDGE_DIR = Path(os.environ.get("KNOWLEDGE_DIR", BASE_DIR / "knowledge"))
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
STATIC_DIR = Path(os.environ.get("STATIC_DIR", BASE_DIR / "frontend" / "dist" / "frontend" / "browser"))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")

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
    return bool(ANTHROPIC_API_KEY)
