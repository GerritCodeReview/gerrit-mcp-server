import json

import pytest

from gerrit_mcp_server.main import check_config_main


def test_check_config_exits_0_with_valid_config():
    # pytest-env sets GERRIT_CONFIG_PATH=tests/test_config.json globally.
    # A successful call returns normally without raising SystemExit.
    check_config_main()


def test_check_config_exits_1_when_config_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("GERRIT_CONFIG_PATH", False)
    # Pin the fallback path to a guaranteed-missing file so this test does not
    # depend on whether the dev happens to have a local gerrit_config.json.
    monkeypatch.setattr(
        "gerrit_mcp_server.main.CONFIG_FILE_PATH", tmp_path / "nonexistent.json"
    )
    with pytest.raises(SystemExit) as exc_info:
        check_config_main()
    assert exc_info.value.code == 1


def test_check_config_exits_1_when_config_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("GERRIT_CONFIG_PATH", str(tmp_path / "nonexistent.json"))
    with pytest.raises(SystemExit) as exc_info:
        check_config_main()
    assert exc_info.value.code == 1


def test_check_config_exits_2_when_config_invalid_json(monkeypatch, tmp_path):
    bad_config = tmp_path / "bad.json"
    bad_config.write_text("{ not valid json }")
    monkeypatch.setenv("GERRIT_CONFIG_PATH", str(bad_config))
    with pytest.raises(SystemExit) as exc_info:
        check_config_main()
    assert exc_info.value.code == 2


def test_check_config_exits_2_when_default_url_mismatch(monkeypatch, tmp_path):
    config = {
        "default_gerrit_base_url": "https://other-gerrit.example.com",
        "gerrit_hosts": [
            {
                "name": "Test",
                "external_url": "https://gerrit.example.com",
                "authentication": {
                    "type": "git_cookies",
                    "gitcookies_path": "~/.gitcookies",
                },
            }
        ],
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))
    monkeypatch.setenv("GERRIT_CONFIG_PATH", str(config_file))
    with pytest.raises(SystemExit) as exc_info:
        check_config_main()
    assert exc_info.value.code == 2
