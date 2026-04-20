"""deploy_cml_app.py — one-command Cloudera AI Application deployment via CML API.

Creates (or updates) the RAG demo Application in a CML workspace without
clicking through the UI.  Supports both deployment paths:

  Path A — Docker image (recommended):
    python deployment/deploy_cml_app.py \\
        --cml-url https://ml-xxxx.cloudera.com \\
        --project-id abc123 \\
        --image ghcr.io/your-org/cloudera-ai-id-rag-demo:latest \\
        --llm-provider azure \\
        --llm-base-url https://... \\
        --llm-api-key sk-...

  Path B — Git source (SQLite mode):
    python deployment/deploy_cml_app.py \\
        --cml-url https://ml-xxxx.cloudera.com \\
        --project-id abc123 \\
        --git-source \\
        --llm-provider openai \\
        --llm-api-key sk-...

  Find your project ID:
    python deployment/deploy_cml_app.py --cml-url https://... --list-projects

  API key: generate at <cml-url>/user/<username>/api-keys
  Pass via --api-key or set CDSW_API_KEY / CMLAPI_KEY environment variable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: pip install requests")
    sys.exit(1)


# ── CML API client ────────────────────────────────────────────────────────────

class CMLClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def _url(self, path: str) -> str:
        return f"{self.base}/api/v1/{path.lstrip('/')}"

    def get(self, path: str, **kwargs) -> Any:
        r = self.session.get(self._url(path), **kwargs)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict, **kwargs) -> Any:
        r = self.session.post(self._url(path), json=body, **kwargs)
        if not r.ok:
            print(f"  API error {r.status_code}: {r.text[:400]}")
            r.raise_for_status()
        return r.json()

    def patch(self, path: str, body: dict, **kwargs) -> Any:
        r = self.session.patch(self._url(path), json=body, **kwargs)
        if not r.ok:
            print(f"  API error {r.status_code}: {r.text[:400]}")
            r.raise_for_status()
        return r.json()

    def list_projects(self) -> list[dict]:
        return self.get("projects").get("projects", [])

    def list_applications(self, project_id: str) -> list[dict]:
        return self.get(f"projects/{project_id}/applications").get("applications", [])

    def create_application(self, project_id: str, payload: dict) -> dict:
        return self.post(f"projects/{project_id}/applications", payload)

    def update_application(self, project_id: str, app_id: str, payload: dict) -> dict:
        return self.patch(f"projects/{project_id}/applications/{app_id}", payload)

    def restart_application(self, project_id: str, app_id: str) -> dict:
        return self.post(f"projects/{project_id}/applications/{app_id}/restart", {})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_existing(client: CMLClient, project_id: str, subdomain: str) -> dict | None:
    for app in client.list_applications(project_id):
        if app.get("subdomain") == subdomain:
            return app
    return None


def _poll_status(client: CMLClient, project_id: str, app_id: str, timeout: int = 900) -> str:
    """Poll application status until running/failed or timeout."""
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            apps = client.list_applications(project_id)
            app = next((a for a in apps if a["id"] == app_id), None)
            if not app:
                break
            status = app.get("status", "unknown")
            if status != last:
                print(f"  Status: {status}")
                last = status
            if status in ("running", "stopped", "failed"):
                return status
        except Exception:
            pass
        time.sleep(10)
    return "timeout"


# ── Build payload ─────────────────────────────────────────────────────────────

def _build_payload(args: argparse.Namespace) -> dict:
    env: dict[str, str] = {}

    # LLM configuration
    if args.llm_provider:
        env["LLM_PROVIDER"] = args.llm_provider
    if args.llm_base_url:
        env["LLM_BASE_URL"] = args.llm_base_url
    if args.llm_api_key:
        env["LLM_API_KEY"] = args.llm_api_key
    if args.llm_model_id:
        env["LLM_MODEL_ID"] = args.llm_model_id
    # Azure-specific
    if args.azure_endpoint:
        env["AZURE_OPENAI_ENDPOINT"] = args.azure_endpoint
    if args.azure_api_key:
        env["AZURE_OPENAI_API_KEY"] = args.azure_api_key
    if args.azure_deployment:
        env["AZURE_OPENAI_DEPLOYMENT"] = args.azure_deployment
    if args.azure_api_version:
        env["AZURE_OPENAI_API_VERSION"] = args.azure_api_version

    payload: dict[str, Any] = {
        "name": args.name,
        "description": "Bilingual enterprise RAG demo — banking, telco, government",
        "subdomain": args.subdomain,
        "cpu": args.cpu,
        "memory": args.memory,
        "nvidia_gpu": args.gpu,
        "bypass_authentication": args.unauthenticated,
        "environment": env,
    }

    if args.image:
        # Docker image path — entrypoint.sh starts MinIO/Nessie/Trino
        payload["image_identifier"] = args.image
        # Docker images use the CMD defined in the Dockerfile; no script needed
    else:
        # Git source path — SQLite + local filesystem
        payload["script"] = "bash deployment/launch_app.sh"
        payload["kernel"] = "python3"

    return payload


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy cloudera-ai-id-rag-demo as a CML Application.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Connection
    parser.add_argument("--cml-url", required=True,
                        help="CML workspace URL, e.g. https://ml-xxxx.cloudera.com")
    parser.add_argument("--project-id",
                        help="CML project ID (use --list-projects to find it)")
    parser.add_argument("--api-key",
                        default=os.environ.get("CDSW_API_KEY") or os.environ.get("CMLAPI_KEY"),
                        help="CML API key (or set CDSW_API_KEY / CMLAPI_KEY env var)")

    # Utilities
    parser.add_argument("--list-projects", action="store_true",
                        help="List all accessible projects and exit")

    # Deployment source (mutually exclusive)
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--image",
                     help="Docker image URL (Path A — full Cloudera stack)")
    src.add_argument("--git-source", action="store_true",
                     help="Deploy from Git source (Path B — SQLite mode)")

    # Application settings
    parser.add_argument("--name", default="Asisten Enterprise ID",
                        help="Application display name (default: 'Asisten Enterprise ID')")
    parser.add_argument("--subdomain", default="asisten-enterprise",
                        help="URL subdomain slug (default: 'asisten-enterprise')")
    parser.add_argument("--cpu", type=float, default=4.0,
                        help="vCPU allocation (default: 4)")
    parser.add_argument("--memory", type=float, default=8.0,
                        help="RAM in GB (default: 8)")
    parser.add_argument("--gpu", type=int, default=0,
                        help="GPU count (default: 0)")
    parser.add_argument("--unauthenticated", action="store_true",
                        help="Disable authentication (use for open demos only)")

    # LLM credentials
    llm = parser.add_argument_group("LLM credentials")
    llm.add_argument("--llm-provider",
                     choices=["cloudera", "openai", "azure", "bedrock", "anthropic", "local"],
                     help="LLM provider")
    llm.add_argument("--llm-base-url", help="LLM endpoint base URL")
    llm.add_argument("--llm-api-key", help="LLM API key")
    llm.add_argument("--llm-model-id", help="Model ID / deployment name")
    llm.add_argument("--azure-endpoint", help="Azure OpenAI endpoint URL")
    llm.add_argument("--azure-api-key", help="Azure OpenAI API key")
    llm.add_argument("--azure-deployment", help="Azure OpenAI deployment name")
    llm.add_argument("--azure-api-version", default="2024-12-01-preview",
                     help="Azure OpenAI API version")

    # Behaviour
    parser.add_argument("--update-existing", action="store_true",
                        help="Update env vars on an existing application and restart")
    parser.add_argument("--no-wait", action="store_true",
                        help="Do not poll for Running status after deploy")

    args = parser.parse_args()

    # Validate API key
    if not args.api_key:
        print("ERROR: CML API key required. Pass --api-key or set CDSW_API_KEY.")
        sys.exit(1)

    client = CMLClient(args.cml_url, args.api_key)

    # ── List projects mode ────────────────────────────────────────────────────
    if args.list_projects:
        print(f"Projects accessible at {args.cml_url}:\n")
        for p in client.list_projects():
            print(f"  {p['id']:30s}  {p.get('name', '')}")
        return

    # ── Deploy mode ───────────────────────────────────────────────────────────
    if not args.project_id:
        print("ERROR: --project-id required. Use --list-projects to find it.")
        sys.exit(1)

    if not args.image and not args.git_source:
        print("ERROR: specify --image <url> (Docker) or --git-source (Git/SQLite).")
        sys.exit(1)

    payload = _build_payload(args)

    print(f"\nTarget workspace : {args.cml_url}")
    print(f"Project ID       : {args.project_id}")
    print(f"Application name : {args.name}")
    print(f"Subdomain        : {args.subdomain}")
    print(f"Source           : {'Docker — ' + args.image if args.image else 'Git source (SQLite)'}")
    print(f"Resources        : {args.cpu} vCPU / {args.memory} GB RAM")
    print(f"Environment vars : {list(payload['environment'].keys())}")
    print()

    existing = _find_existing(client, args.project_id, args.subdomain)

    if existing and args.update_existing:
        app_id = existing["id"]
        print(f"Updating existing application {app_id}...")
        client.update_application(args.project_id, app_id, {"environment": payload["environment"]})
        print("Restarting...")
        client.restart_application(args.project_id, app_id)
    elif existing:
        print(f"Application '{args.subdomain}' already exists (id={existing['id']}).")
        print("Use --update-existing to update env vars and restart.")
        return
    else:
        print("Creating new application...")
        result = client.create_application(args.project_id, payload)
        app_id = result["id"]
        print(f"Created: id={app_id}")

    app_url = f"{args.cml_url.rstrip('/')}/{args.subdomain}"
    print(f"\nApplication URL  : {app_url}")

    if args.no_wait:
        print("Skipping status poll (--no-wait). Check the CML UI for status.")
        return

    print("\nPolling for Running status (timeout 15 min)...")
    status = _poll_status(client, args.project_id, app_id)
    if status == "running":
        print(f"\nApplication is running.")
        print(f"  Chat interface : {app_url}/")
        print(f"  Health         : {app_url}/setup")
        print(f"  Configure LLM  : {app_url}/configure")
    else:
        print(f"\nApplication status: {status}. Check CML logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
