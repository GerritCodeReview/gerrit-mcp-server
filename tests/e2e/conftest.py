"""Opt-in E2E fixtures. Nothing starts during collection."""

from pathlib import Path

import pytest

from tests.e2e.support import backend_config, temporary_config


def pytest_addoption(parser):
    group = parser.getgroup("gerrit-e2e")
    group.addoption(
        "--e2e-backend", choices=("container", "external"), default="container"
    )
    group.addoption(
        "--e2e-config", default=str(Path(__file__).with_name("e2e_config.json"))
    )
    group.addoption(
        "--e2e-artifacts", default=".pytest_cache/e2e", help="Directory for Gerrit logs"
    )


@pytest.fixture(scope="session")
def e2e_config(pytestconfig, tmp_path_factory):
    with backend_config(
        pytestconfig.getoption("--e2e-backend"),
        pytestconfig.getoption("--e2e-config"),
        pytestconfig.getoption("--e2e-artifacts"),
    ) as config:
        with temporary_config(config, tmp_path_factory.mktemp("gerrit-e2e")):
            yield config


@pytest.fixture
def gerrit_base_url(e2e_config):
    return e2e_config["gerrit_base_url"]


@pytest.fixture
def known_cl(e2e_config):
    return str(e2e_config["known_cl"])


@pytest.fixture
def known_user(e2e_config):
    return e2e_config["known_user"]


@pytest.fixture
def test_project(e2e_config):
    if not e2e_config.get("test_project"):
        pytest.skip("External write tests require a dedicated 'test_project'.")
    return e2e_config["test_project"]


@pytest.fixture
def test_branch(e2e_config):
    return e2e_config["test_branch"]
