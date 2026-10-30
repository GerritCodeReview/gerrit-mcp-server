"""Docker-free tests for the E2E harness's configuration and lifecycle."""

import importlib
import importlib.util
import json
import os

import pytest


@pytest.fixture
def support():
    assert importlib.util.find_spec("tests.e2e.support") is not None, (
        "E2E support is missing"
    )
    return importlib.import_module("tests.e2e.support")


@pytest.fixture
def external_config(tmp_path):
    auth = tmp_path / "auth.json"
    auth.write_text("{}")
    path = tmp_path / "e2e.json"
    data = {
        "gerrit_base_url": "https://gerrit.example.com",
        "known_cl": "123",
        "known_user": "reader@example.com",
        "gerrit_config_path": "auth.json",
    }
    path.write_text(json.dumps(data))
    return path, data


def test_external_config_resolves_auth_path_and_defaults_branch(
    support, external_config
):
    path, _ = external_config
    result = support.load_external_config(path)
    assert result["gerrit_config_path"] == str(path.parent / "auth.json")
    assert result["test_branch"] == "main"
    assert not result.get("test_project")


@pytest.mark.parametrize(
    "missing", ["gerrit_base_url", "known_cl", "known_user", "gerrit_config_path"]
)
def test_external_config_requires_read_inputs(support, external_config, missing):
    path, data = external_config
    del data[missing]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=missing):
        support.load_external_config(path)


def test_external_config_rejects_missing_auth_file(support, external_config):
    path, _ = external_config
    (path.parent / "auth.json").unlink()
    with pytest.raises(ValueError, match="auth.json"):
        support.load_external_config(path)


def test_external_backend_never_constructs_container(
    support, external_config, tmp_path
):
    path, _ = external_config

    def forbidden():
        pytest.fail("external mode attempted to construct a container")

    with support.backend_config(
        "external", path, tmp_path, container_factory=forbidden
    ) as config:
        assert config["known_cl"] == "123"


def test_temporary_config_restores_environment_after_failure(
    support, monkeypatch, tmp_path
):
    monkeypatch.setenv("GERRIT_CONFIG_PATH", "original.json")
    with pytest.raises(RuntimeError):
        with support.temporary_config(
            {"gerrit_config_path": "temporary.json"}, tmp_path
        ):
            assert os.environ["GERRIT_CONFIG_PATH"] == "temporary.json"
            raise RuntimeError("test failed")
    assert os.environ["GERRIT_CONFIG_PATH"] == "original.json"


def test_temporary_config_restores_absent_environment(support, monkeypatch, tmp_path):
    monkeypatch.delenv("GERRIT_CONFIG_PATH", raising=False)
    with support.temporary_config({"gerrit_config_path": "temporary.json"}, tmp_path):
        assert os.environ["GERRIT_CONFIG_PATH"] == "temporary.json"
    assert "GERRIT_CONFIG_PATH" not in os.environ


def test_readiness_retries_then_returns(support, monkeypatch):
    responses = iter([OSError("starting"), {"_account_id": 1000000}])

    def probe():
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(support.time, "sleep", lambda _: None)
    assert support.wait_for_ready(probe, timeout=1)["_account_id"] == 1000000


def test_readiness_timeout_preserves_last_error(support, monkeypatch):
    ticks = iter([0, 0, 2])
    monkeypatch.setattr(support.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(support.time, "sleep", lambda _: None)

    def probe():
        raise OSError("connection refused")

    with pytest.raises(RuntimeError, match="connection refused"):
        support.wait_for_ready(probe, timeout=1)


class FakeContainer:
    def __init__(self, fail_start=False):
        self.stopped = False
        self.fail_start = fail_start

    def start(self):
        if self.fail_start:
            raise RuntimeError("startup failed")
        return self

    def stop(self):
        self.stopped = True

    def get_logs(self):
        return b"Gerrit startup log", b"diagnostic stderr"


@pytest.mark.parametrize("fail_start", [False, True])
def test_container_cleanup_and_logs_on_failure(support, tmp_path, fail_start):
    container = FakeContainer(fail_start)
    with pytest.raises(RuntimeError):
        with support.running_gerrit(lambda: container, tmp_path):
            raise RuntimeError("seeding failed")
    assert container.stopped
    assert "Gerrit startup log" in (tmp_path / "gerrit-container.log").read_text()


def test_container_cleanup_on_success(support, tmp_path):
    container = FakeContainer()
    with support.running_gerrit(lambda: container, tmp_path) as running:
        assert running is container
    assert container.stopped


@pytest.mark.parametrize("host", ["192.0.2.1", "docker.example.com", "0.0.0.0"])
def test_container_endpoint_rejects_non_loopback(support, host):
    with pytest.raises(ValueError, match="loopback"):
        support.container_url(host, "32768")


def test_container_endpoint_formats_ipv6(support):
    assert support.container_url("::1", "32768") == "http://[::1]:32768"


def test_container_factory_binds_http_to_loopback(support):
    from unittest.mock import patch

    # Only Docker client construction is mocked: inspect the real container config.
    with patch("testcontainers.core.container.DockerClient"):
        container = support.make_container()
    assert container.ports["8080/tcp"] == ("127.0.0.1", 0)


def test_start_failure_is_not_masked_by_unavailable_logs(support, tmp_path):
    class NoLogsContainer(FakeContainer):
        def get_logs(self):
            raise RuntimeError("container does not exist yet")

    container = NoLogsContainer(fail_start=True)
    with pytest.raises(RuntimeError, match="startup failed"):
        with support.running_gerrit(lambda: container, tmp_path):
            pytest.fail("startup unexpectedly succeeded")
    assert container.stopped
    assert (
        "container does not exist yet"
        in (tmp_path / "gerrit-container.log").read_text()
    )


@pytest.mark.parametrize(
    "arguments", [[], ["tests/e2e"], ["tests/e2e", "--e2e-backend=external"]]
)
def test_collection_does_not_import_testcontainers(tmp_path, arguments):
    import subprocess
    import sys
    from pathlib import Path

    # A real subprocess with an import guard catches eager Docker initialization.
    (tmp_path / "sitecustomize.py").write_text(
        "import sys\n"
        "class Guard:\n"
        "    def find_spec(self, fullname, path=None, target=None):\n"
        "        if fullname.split('.')[0] == 'testcontainers':\n"
        "            raise RuntimeError('Testcontainers imported during collection')\n"
        "sys.meta_path.insert(0, Guard())\n"
    )
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(tmp_path), "PYTEST_ADDOPTS": ""}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *arguments],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    if not arguments:
        assert "test_e2e_query_changes" not in result.stdout
    else:
        assert "test_e2e_query_changes" in result.stdout


def test_external_missing_config_fails_without_docker(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/e2e",
            "--e2e-backend=external",
            f"--e2e-config={tmp_path / 'absent.json'}",
            "-q",
            "--tb=short",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert "Cannot load E2E configuration" in result.stdout
    assert "Container E2E failed" not in result.stdout


def test_container_config_bypasses_proxy_for_real_curl(support, monkeypatch, tmp_path):
    import subprocess
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"loopback reached")

        def log_message(self, *args):
            pass

    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "corporate.example")
    monkeypatch.delenv("no_proxy", raising=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with support.temporary_config({"mcp_config": {}}, tmp_path):
            result = subprocess.run(
                [
                    "curl",
                    "--silent",
                    "--show-error",
                    "--fail",
                    "--max-time",
                    "3",
                    f"http://127.0.0.1:{server.server_port}/",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert result.returncode == 0, result.stderr
            assert result.stdout == "loopback reached"
        assert os.environ["NO_PROXY"] == "corporate.example"
        assert "no_proxy" not in os.environ
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_external_config_preserves_proxy_settings(support, monkeypatch, tmp_path):
    monkeypatch.setenv("no_proxy", "lower.example")
    monkeypatch.setenv("NO_PROXY", "upper.example")
    with support.temporary_config({"gerrit_config_path": "external.json"}, tmp_path):
        assert os.environ["no_proxy"] == "lower.example"
        assert os.environ["NO_PROXY"] == "upper.example"


def test_external_read_only_fixture_skips_write_test():
    from tests.e2e.conftest import test_project

    with pytest.raises(pytest.skip.Exception, match="dedicated 'test_project'"):
        test_project.__wrapped__({})


@pytest.mark.asyncio
async def test_created_change_cleanup_abandons_owned_changes(monkeypatch):
    from tests.e2e import test_main

    status = {"123": "NEW"}

    async def create(**kwargs):
        return [{"type": "text", "text": "Successfully created new change 123."}]

    async def abandon(**kwargs):
        status[kwargs["change_id"]] = "ABANDONED"
        return [{"type": "text", "text": "Successfully abandoned CL 123."}]

    monkeypatch.setattr(test_main.main, "create_change", create)
    monkeypatch.setattr(test_main.main, "abandon_change", abandon)
    fixture = test_main.created_change.__wrapped__("https://gerrit.example.com")
    create_change, _ = await anext(fixture)
    await create_change("test", "subject")
    # pytest finalizes the fixture even if the consuming test failed.
    with pytest.raises(StopAsyncIteration):
        await anext(fixture)
    assert status["123"] == "ABANDONED"


@pytest.mark.asyncio
async def test_created_change_cleanup_reports_abandonment_failure(monkeypatch):
    from tests.e2e import test_main

    async def create(**kwargs):
        return [{"type": "text", "text": "Successfully created new change 123."}]

    async def abandon(**kwargs):
        raise RuntimeError("permission denied")

    monkeypatch.setattr(test_main.main, "create_change", create)
    monkeypatch.setattr(test_main.main, "abandon_change", abandon)
    fixture = test_main.created_change.__wrapped__("https://gerrit.example.com")
    create_change, _ = await anext(fixture)
    await create_change("test", "subject")
    with pytest.raises(pytest.fail.Exception, match="permission denied"):
        await anext(fixture)


@pytest.mark.asyncio
async def test_finished_change_is_not_abandoned_again(monkeypatch):
    from tests.e2e import test_main

    async def create(**kwargs):
        return [{"type": "text", "text": "Successfully created new change 123."}]

    async def forbidden(**kwargs):
        pytest.fail("already-abandoned change was abandoned again")

    monkeypatch.setattr(test_main.main, "create_change", create)
    monkeypatch.setattr(test_main.main, "abandon_change", forbidden)
    fixture = test_main.created_change.__wrapped__("https://gerrit.example.com")
    create_change, finished = await anext(fixture)
    _, number = await create_change("test", "subject")
    finished(number)
    with pytest.raises(StopAsyncIteration):
        await anext(fixture)
