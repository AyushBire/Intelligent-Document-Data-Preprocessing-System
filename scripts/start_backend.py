"""Start the laptop backend and reconnect the live website from one terminal."""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from connect_presentation import ROOT, connect, verify_backend

LIVE_URL = "https://intelligent-document-data-preproces.vercel.app"
RUNTIME = ROOT / ".validation"


def run_command(arguments: list[str], cwd: Path = ROOT) -> str:
    """Run a command without shell interpolation.

    Args: arguments: Executable and arguments; cwd: Working directory.
    Returns: Captured stdout. Raises: RuntimeError if the command fails.
    """
    result = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(f"Command failed: {arguments[0]}\n{result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def health_ok(origin: str) -> bool:
    """Check the expected API liveness response.

    Args: origin: HTTP(S) backend origin. Returns: Whether IDPS is reachable.
    Raises: None; network and malformed-response errors return False.
    """
    try:
        with urlopen(origin + "/health", timeout=5) as response:
            return json.load(response).get("status") == "ok"
    except (OSError, ValueError):
        return False


def start_process(arguments: list[str], cwd: Path, log_name: str, owned: list) -> subprocess.Popen:
    """Start a hidden service with output in an ignored log file.

    Args: arguments: Command; cwd: Directory; log_name: Log filename; owned: Cleanup list.
    Returns: Running child process. Raises: OSError on launch failures.
    """
    with (RUNTIME / log_name).open("w", encoding="utf-8") as log:
        process = subprocess.Popen(arguments, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    owned.append(process)
    return process


def wait_for_backend(process: subprocess.Popen) -> None:
    """Wait for model initialization and API startup.

    Args: process: Backend process. Returns: None.
    Raises: RuntimeError if startup fails or takes longer than three minutes.
    """
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Backend exited. See .validation/presentation-backend.log.")
        if health_ok("http://127.0.0.1:8000"):
            return
        time.sleep(2)
    raise RuntimeError("Backend startup timed out. See .validation/presentation-backend.log.")


def current_origin() -> str | None:
    """Read the configured temporary tunnel.

    Returns: Valid Cloudflare origin or None. Raises: OSError on file read failure.
    """
    config = json.loads((ROOT / "frontend/vercel.json").read_text(encoding="utf-8"))
    for rule in config.get("rewrites", []):
        if rule.get("source") == "/api/:path*":
            match = re.fullmatch(r"(https://[a-z0-9-]+\.trycloudflare\.com)/api/:path\*", rule.get("destination", ""))
            return match.group(1) if match else None
    return None


def wait_for_tunnel(process: subprocess.Popen) -> str:
    """Read the new origin from cloudflared and wait for connectivity.

    Args: process: Tunnel process. Returns: Working HTTPS origin.
    Raises: RuntimeError if tunnel startup fails or exceeds two minutes.
    """
    deadline = time.monotonic() + 120
    log_path = RUNTIME / "presentation-tunnel.log"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Tunnel exited. See .validation/presentation-tunnel.log.")
        text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", text)
        if match and health_ok(match.group()):
            return match.group()
        time.sleep(2)
    raise RuntimeError("Tunnel startup timed out. See .validation/presentation-tunnel.log.")


def validate_files() -> None:
    """Check the existing private runtime prerequisites.

    Returns: None. Raises: RuntimeError when the laptop runtime is incomplete.
    """
    required = [ROOT / ".env", RUNTIME / "cloudflared.exe",
                RUNTIME / "pg-runtime/pgsql/bin/pg_ctl.exe", RUNTIME / "postgres-data/PG_VERSION"]
    for path in required:
        if not path.exists():
            raise RuntimeError(f"Required local file is missing: {path}")


def prepare_git() -> None:
    """Check deployment branch and protect unrelated proxy edits.

    Returns: None. Raises: RuntimeError for an unsafe deployment checkout.
    """
    if run_command(["git", "branch", "--show-current"]) != "main":
        raise RuntimeError("Switch to main before starting a deployment, or use --no-deploy.")
    if run_command(["git", "status", "--porcelain", "--", "frontend/vercel.json"]):
        raise RuntimeError("frontend/vercel.json has uncommitted edits. Commit them first, or use --no-deploy.")


def wait_for_deployment() -> bool:
    """Wait for the live frontend to use the new tunnel.

    Returns: Whether deployment is ready.
    Raises: None; timeout leaves the services running and reports pending status.
    """
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            with urlopen(LIVE_URL + "/api/auth/session", timeout=10) as response:
                status = json.load(response)
                if status.get("required") is True and isinstance(status.get("authenticated"), bool):
                    # The previous expired tunnel cannot return a valid session response.
                    return True
        except (OSError, ValueError):
            pass
        time.sleep(5)
    return False


def start(no_deploy: bool) -> None:
    """Start or reuse services, verify protection, and optionally deploy.

    Args: no_deploy: Skip Git commit/push. Returns: None when interrupted.
    Raises: RuntimeError, OSError or subprocess errors on startup/deployment failures.
    """
    if os.name != "nt":
        raise RuntimeError("This launcher uses the project's Windows presentation runtime.")
    validate_files()
    if not no_deploy:
        prepare_git()
    RUNTIME.mkdir(exist_ok=True)
    owned: list[subprocess.Popen] = []
    try:
        pg_ctl = str(RUNTIME / "pg-runtime/pgsql/bin/pg_ctl.exe")
        pg_data = str(RUNTIME / "postgres-data")
        status = subprocess.run([pg_ctl, "-D", pg_data, "status"], capture_output=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if status.returncode:
            print("Starting PostgreSQL...", flush=True)
            run_command([pg_ctl, "-D", pg_data, "-l", str(RUNTIME / "postgres.log"),
                         "-o", "-h 127.0.0.1 -p 55432", "start"])
        else:
            print("PostgreSQL is already running.", flush=True)

        if not health_ok("http://127.0.0.1:8000"):
            print("Starting backend and loading OCR models...", flush=True)
            process = start_process([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
                                    ROOT / "backend", "presentation-backend.log", owned)
            wait_for_backend(process)
        else:
            print("Backend is already running.", flush=True)

        verify_backend("http://127.0.0.1:8000")
        origin = current_origin()
        if origin and health_ok(origin):
            print("Reusing the existing tunnel.", flush=True)
        else:
            print("Starting a new secure tunnel...", flush=True)
            process = start_process([str(RUNTIME / "cloudflared.exe"), "tunnel", "--url", "http://127.0.0.1:8000",
                                     "--no-autoupdate", "--protocol", "http2"], ROOT, "presentation-tunnel.log", owned)
            origin = wait_for_tunnel(process)

        connect(origin)
        changed = bool(run_command(["git", "diff", "HEAD", "--", "frontend/vercel.json"]))
        if changed and not no_deploy:
            print("Updating the Vercel connection through GitHub...", flush=True)
            run_command(["git", "commit", "--only", "-m", "Connect presentation backend tunnel", "--", "frontend/vercel.json"])
            run_command(["git", "push", "origin", "main"])
            print("Waiting for Vercel deployment...", flush=True)
            if not wait_for_deployment():
                print("Vercel is still deploying. Keep this terminal open and try the site shortly.", flush=True)
        elif changed:
            print("Proxy updated locally. --no-deploy skips Git commit and push; the live site has not been updated.", flush=True)
        else:
            print("The Vercel connection is already configured.", flush=True)

        print(f"\nSign in: {LIVE_URL}/signin", flush=True)
        print("Credentials: .validation/presentation-login.txt (private)", flush=True)
        print("Keep this terminal open and the laptop awake. Press Ctrl+C to stop services started here.", flush=True)
        while True:
            for process in owned:
                if process.poll() is not None:
                    raise RuntimeError("A presentation service stopped. Check the logs in .validation and rerun this command.")
            time.sleep(2)
    finally:
        for process in reversed(owned):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
        print("Launcher stopped. PostgreSQL and previously running services were left running.", flush=True)


def main() -> int:
    """Parse launcher options and report failures without printing credentials.

    Returns: Exit status. Raises: None; expected failures are printed to stderr.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-deploy", action="store_true", help="Skip automatic Git commit and push.")
    args = parser.parse_args()
    try:
        start(args.no_deploy)
        return 0
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, OSError, ValueError) as error:
        print(f"Startup failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
