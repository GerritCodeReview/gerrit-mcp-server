import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gerrit_mcp_server.extensions import ExtensionContext, ExtensionLoader


def _make_ctx(tmp_path: Path) -> ExtensionContext:
    return ExtensionContext(
        mcp=MagicMock(),
        get_base_url=MagicMock(return_value="https://example.com"),
        normalize_url=lambda u: u,
        run_curl=MagicMock(),
        load_config=MagicMock(return_value={}),
        log_path=tmp_path / "server.log",
    )


class TestExtensionLoader(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.mkdtemp()
        self.ctx = _make_ctx(Path(self._tmp))
        self.loader = ExtensionLoader(self.ctx)

    def test_no_extensions_returns_empty(self):
        with (
            patch.object(self.loader, "_discover_entry_point_modules", return_value=[]),
            patch.object(self.loader, "_discover_env_modules", return_value=[]),
        ):
            result = self.loader.load()
        self.assertEqual(result, [])

    def test_successful_registration(self):
        mod = types.ModuleType("fake_ext")
        mod.register = MagicMock()
        with (
            patch.object(
                self.loader,
                "_discover_entry_point_modules",
                return_value=["fake_ext"],
            ),
            patch.object(self.loader, "_discover_env_modules", return_value=[]),
            patch.dict(sys.modules, {"fake_ext": mod}),
        ):
            result = self.loader.load()
        self.assertEqual(result, ["fake_ext"])
        mod.register.assert_called_once_with(self.ctx)

    def test_import_failure_skipped(self):
        register_mock = MagicMock()
        with (
            patch.object(
                self.loader,
                "_discover_entry_point_modules",
                return_value=["nonexistent.module"],
            ),
            patch.object(self.loader, "_discover_env_modules", return_value=[]),
            patch(
                "gerrit_mcp_server.extensions.importlib.import_module",
                side_effect=ImportError("no module"),
            ),
        ):
            result = self.loader.load()
        self.assertEqual(result, [])
        register_mock.assert_not_called()

    def test_missing_register_skipped(self):
        mod = types.ModuleType("no_register_ext")
        # Use a NonCallableMagicMock so callable(mod.register) is False,
        # matching the real "missing register" guard, while still allowing
        # assert_not_called() to confirm register() was never invoked.
        from unittest.mock import NonCallableMagicMock

        mod.register = NonCallableMagicMock()
        with (
            patch.object(
                self.loader,
                "_discover_entry_point_modules",
                return_value=["no_register_ext"],
            ),
            patch.object(self.loader, "_discover_env_modules", return_value=[]),
            patch.dict(sys.modules, {"no_register_ext": mod}),
        ):
            result = self.loader.load()
        self.assertEqual(result, [])
        mod.register.assert_not_called()

    def test_register_raises_skipped(self):
        mod = types.ModuleType("bad_register_ext")
        mod.register = MagicMock(side_effect=RuntimeError("boom"))
        with (
            patch.object(
                self.loader,
                "_discover_entry_point_modules",
                return_value=["bad_register_ext"],
            ),
            patch.object(self.loader, "_discover_env_modules", return_value=[]),
            patch.dict(sys.modules, {"bad_register_ext": mod}),
        ):
            result = self.loader.load()
        self.assertEqual(result, [])

    def test_deduplication_loads_once(self):
        mod = types.ModuleType("dup_ext")
        mod.register = MagicMock()
        with (
            patch.object(
                self.loader,
                "_discover_entry_point_modules",
                return_value=["dup_ext", "dup_ext"],
            ),
            patch.object(self.loader, "_discover_env_modules", return_value=[]),
            patch.dict(sys.modules, {"dup_ext": mod}),
        ):
            result = self.loader.load()
        self.assertEqual(result, ["dup_ext"])
        mod.register.assert_called_once()

    def test_duplicate_logs_warning(self):
        mod = types.ModuleType("dup_warn_ext")
        mod.register = MagicMock()
        with (
            patch.object(
                self.loader,
                "_discover_entry_point_modules",
                return_value=["dup_warn_ext", "dup_warn_ext"],
            ),
            patch.object(self.loader, "_discover_env_modules", return_value=[]),
            patch.dict(sys.modules, {"dup_warn_ext": mod}),
        ):
            self.loader.load()
        log_content = (self.ctx.log_path).read_text()
        self.assertIn("WARNING", log_content)
        self.assertIn("dup_warn_ext", log_content)

    def test_entry_point_discovery_failure_does_not_abort(self):
        # A malformed entry point in the environment can make discovery
        # raise; startup must survive it (never-abort-startup contract).
        with (
            patch(
                "gerrit_mcp_server.extensions.entry_points",
                side_effect=RuntimeError("bad entry point"),
            ),
            patch.object(self.loader, "_discover_env_modules", return_value=[]),
        ):
            result = self.loader.load()
        self.assertEqual(result, [])
        log_content = (self.ctx.log_path).read_text()
        self.assertIn("discovery failed", log_content)


if __name__ == "__main__":
    unittest.main()
