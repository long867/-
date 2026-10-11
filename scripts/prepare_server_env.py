"""Prepare a private ECS environment from the configured local LLM credentials."""

import secrets
from pathlib import Path

from app.core.config import get_settings


def main() -> None:
    """Generate separate server database/signing passwords; never print their values."""
    root = Path(__file__).resolve().parents[1]
    settings = get_settings()
    target = root / "artifacts/server.env"
    if target.exists():
        print("Private server environment already exists; retaining generated secrets")
        return
    text = (root / ".env.production.example").read_text(encoding="utf-8")
    replacements = {
        "POSTGRES_PASSWORD": secrets.token_hex(24),
        "SECRET_KEY": secrets.token_hex(32),
        "GRAFANA_ADMIN_PASSWORD": secrets.token_hex(20),
        "LLM_API_KEY": settings.LLM_API_KEY.get_secret_value(),
        "LLM_BASE_URL": settings.LLM_BASE_URL,
        "LLM_MODEL": settings.LLM_MODEL,
        "AUTO_PUBLISH": str(settings.AUTO_PUBLISH).lower(),
        "USER_AGENT": settings.USER_AGENT,
    }
    lines = [
        line.split("=", 1)[0] + "=" + replacements[line.split("=", 1)[0]]
        if "=" in line and line.split("=", 1)[0] in replacements
        else line
        for line in text.splitlines()
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    target.chmod(0o600)
    print("Prepared artifacts/server.env; values withheld")


if __name__ == "__main__":
    main()
