"""E2E-only Gerrit provisioning; importing this module does not require Docker."""

import base64
import ipaddress
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request

GERRIT_IMAGE = "gerritcodereview/gerrit:3.13.10"
ADMIN_USER = "admin"
ADMIN_PASSWORD = "secret"  # Developer initializer's disposable, loopback-only account.
STARTUP_TIMEOUT = 180
BOOTSTRAP = """
set -eu
site=/tmp/gerrit-e2e
war=/var/gerrit/bin/gerrit.war
java -jar "$war" init --batch --dev --no-auto-start -d "$site"
git config -f "$site/etc/gerrit.config" httpd.listenUrl 'http://*:8080/'
git config -f "$site/etc/gerrit.config" gerrit.canonicalWebUrl 'http://localhost:8080/'
git config -f "$site/etc/gerrit.config" sshd.listenAddress off
exec java -Xmx512m -jar "$war" daemon -d "$site" --console-log
"""


def load_external_config(path):
    path = Path(path).expanduser().resolve()
    try:
        config = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load E2E configuration {path}: {error}") from error
    if not isinstance(config, dict):
        raise ValueError(f"E2E configuration {path} must be a JSON object")
    for key in ("gerrit_base_url", "known_cl", "known_user", "gerrit_config_path"):
        if not config.get(key):
            raise ValueError(f"External E2E configuration requires '{key}'")
    auth = Path(config["gerrit_config_path"]).expanduser()
    if not auth.is_absolute():
        auth = path.parent / auth
    if not auth.is_file():
        raise ValueError(f"MCP authentication configuration not found: {auth}")
    config["gerrit_config_path"] = str(auth.resolve())
    config.setdefault("test_branch", "main")
    return config


@contextmanager
def temporary_config(config, directory):
    """Restore pytest-env's original configuration even when a test fails."""
    original = {
        name: os.environ.get(name)
        for name in ("GERRIT_CONFIG_PATH", "NO_PROXY", "no_proxy")
    }
    try:
        if "mcp_config" in config:
            path = Path(directory) / "gerrit_config.json"
            path.write_text(json.dumps(config["mcp_config"]))
            path.chmod(0o600)
            exemptions = ",".join(
                value for value in (original["no_proxy"], original["NO_PROXY"]) if value
            )
            exemptions = ",".join(filter(None, (exemptions, "127.0.0.1,localhost,::1")))
            os.environ["NO_PROXY"] = os.environ["no_proxy"] = exemptions
        else:
            path = config["gerrit_config_path"]
        os.environ["GERRIT_CONFIG_PATH"] = str(path)
        yield
    finally:
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def container_url(host, port):
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback:
        raise ValueError(
            "Container E2E requires a local Docker daemon and loopback endpoint"
        )
    if ":" in host:
        host = f"[{host}]"
    return f"http://{host}:{port}"


def make_container():
    # Lazy import: unit tests and external-server E2E do not need Testcontainers.
    from testcontainers.core.container import DockerContainer

    container = (
        DockerContainer(GERRIT_IMAGE)
        .with_kwargs(entrypoint=["/bin/bash", "-ec"])
        .with_command([BOOTSTRAP])
    )
    # The helper accepts only host port numbers; Docker's port map also supports
    # a bind address. Port zero asks Docker to allocate an unused host port.
    container.ports["8080/tcp"] = ("127.0.0.1", 0)
    return container


@contextmanager
def running_gerrit(factory, artifacts):
    container = factory()
    artifacts = Path(artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    try:
        container.start()
        yield container
    finally:
        try:
            try:
                stdout, stderr = container.get_logs()
            except Exception as error:
                stdout, stderr = b"", f"No container logs available: {error}".encode()
            (artifacts / "gerrit-container.log").write_bytes(stdout + b"\n" + stderr)
        finally:
            # stop() removes the container and anonymous volumes (v=True).
            container.stop()


def rest(base_url, path, method="GET", payload=None, content_type="application/json"):
    """Seed through Gerrit's REST API, not through the functions under test."""
    credentials = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()).decode()
    data = None
    if payload is not None:
        data = (
            json.dumps(payload) if content_type == "application/json" else payload
        ).encode()
    request = Request(
        f"{base_url}/a/{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Basic {credentials}", "Content-Type": content_type},
    )
    # A local fixture must not inherit a corporate HTTP proxy.
    from urllib.request import ProxyHandler, build_opener

    with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
        text = response.read().decode()
    if text.startswith(")]}'"):
        text = text.split("\n", 1)[1]
    return json.loads(text) if text.strip() else None


def wait_for_ready(probe, timeout=STARTUP_TIMEOUT):
    deadline = time.monotonic() + timeout
    last_error = "no response"
    while time.monotonic() < deadline:
        try:
            account = probe()
            if isinstance(account, dict) and account.get("_account_id"):
                return account
            last_error = "authenticated account response is missing _account_id"
        except (OSError, HTTPError, URLError, ValueError) as error:
            last_error = str(error)
        time.sleep(1)
    raise RuntimeError(f"Gerrit did not become ready within {timeout}s: {last_error}")


def seed_gerrit(base_url):
    project = "e2e-test"
    rest(
        base_url,
        f"projects/{project}",
        "PUT",
        {"create_empty_commit": True, "branches": ["main"]},
    )
    change = rest(
        base_url,
        "changes/",
        "POST",
        {"project": project, "branch": "main", "subject": "E2E seeded change"},
    )
    number = str(change["_number"])
    rest(
        base_url,
        f"changes/{number}/edit/{quote('README.txt', safe='')}",
        "PUT",
        "E2E fixture\n",
        "text/plain",
    )
    rest(base_url, f"changes/{number}/edit:publish", "POST", {})
    # Publishing updates the search index; verify visibility before running tests.
    deadline = time.monotonic() + 30
    while not rest(base_url, f"changes/?q=change:{number}"):
        if time.monotonic() >= deadline:
            raise RuntimeError("Seeded Gerrit change did not become searchable")
        time.sleep(0.5)
    return {
        "gerrit_base_url": base_url,
        "known_cl": number,
        "known_user": "admin@example.com",
        "test_project": project,
        "test_branch": "main",
        "mcp_config": {
            "default_gerrit_base_url": base_url,
            "gerrit_hosts": [
                {
                    "name": "E2E Gerrit",
                    "external_url": base_url,
                    "authentication": {
                        "type": "http_basic",
                        "username": ADMIN_USER,
                        "auth_token": ADMIN_PASSWORD,
                    },
                }
            ],
        },
    }


@contextmanager
def backend_config(backend, path, artifacts, container_factory=None):
    if backend == "external":
        yield load_external_config(path)
        return
    if backend != "container":
        raise ValueError(f"Unknown E2E backend: {backend}")
    try:
        with running_gerrit(
            container_factory or make_container, artifacts
        ) as container:
            base_url = container_url(
                container.get_container_host_ip(), container.get_exposed_port(8080)
            )
            wait_for_ready(lambda: rest(base_url, "accounts/self"))
            yield seed_gerrit(base_url)
    except Exception as error:
        raise RuntimeError(
            f"Container E2E failed: {error}. "
            "Check Docker/socket access and image pull access; "
            f"Gerrit logs: {Path(artifacts) / 'gerrit-container.log'}"
        ) from error
