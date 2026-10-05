"""Connect the Vercel frontend to a protected temporary Cloudflare backend."""
import argparse
import base64
import json
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def verify_backend(origin: str) -> None:
    """Verify authentication and database readiness without changing files.

    Args: origin: Local or public backend origin.
    Returns: None. Raises: ValueError, OSError or network errors on failed checks.
    """
    values = dotenv_values(ROOT / ".env")
    username = values.get("PRESENTATION_USERNAME", "presenter")
    password = values.get("PRESENTATION_PASSWORD")
    if not password:
        raise ValueError("Set PRESENTATION_PASSWORD in the private root .env first.")
    try:
        with urlopen(origin + "/api/documents/stats", timeout=30):
            raise ValueError("Backend is unprotected; refusing to connect it.")
    except HTTPError as error:
        if error.code != 401:
            raise ValueError(f"Expected HTTP 401, received HTTP {error.code}.") from None
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    with urlopen(Request(origin + "/health/ready", headers={"Authorization": "Basic " + token}), timeout=30) as response:
        if json.load(response).get("status") != "ready":
            raise ValueError("The backend is not ready.")


def connect(origin: str) -> None:
    """Verify protection and update the public frontend proxy configuration.

    Args: origin: HTTPS trycloudflare.com origin without credentials or path.
    Returns: None. Raises: ValueError, OSError or network errors on invalid/unprotected backends.
    """
    origin = origin.rstrip("/")
    if not re.fullmatch(r"https://[a-z0-9-]+\.trycloudflare\.com", origin):
        raise ValueError("Provide the HTTPS trycloudflare.com origin printed by the tunnel.")
    values = dotenv_values(ROOT / ".env")
    username = values.get("PRESENTATION_USERNAME", "presenter")
    password = values.get("PRESENTATION_PASSWORD")
    if not password:
        raise ValueError("Set PRESENTATION_PASSWORD in the private root .env first.")
    verify_backend(origin)
    config_path = ROOT / "frontend" / "vercel.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["rewrites"] = [
        {"source": "/api/:path*", "destination": origin + "/api/:path*"},
        {"source": "/health", "destination": origin + "/health"},
        {"source": "/((?!api(?:/|$)|health(?:/|$)|ws(?:/|$)).*)", "destination": "/index.html"},
    ]
    config["headers"] = [rule for rule in config.get("headers", []) if rule.get("source") != "/api/:path*"]
    config["headers"].append({"source": "/api/:path*", "headers": [{"key": "Cache-Control", "value": "private, no-store"}]})
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    credentials_path = ROOT / ".validation" / "presentation-login.txt"
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    credentials_path.write_text(f"Username: {username}\nPassword: {password}\n\nKeep this file private. Do not commit or share it.\n", encoding="utf-8")
    print("Protected backend verified; Vercel proxy configuration updated.")
    print("Login credentials: .validation/presentation-login.txt (ignored by Git)")
    print("Push frontend/vercel.json to redeploy, then visit /signin on the Vercel site.")


def main() -> None:
    """Parse the tunnel origin. Returns: None. Raises: Validation or network errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    connect(parser.parse_args().origin)


if __name__ == "__main__":
    main()
