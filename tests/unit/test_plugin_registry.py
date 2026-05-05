import asyncio
import json
import unittest

from gerrit_mcp_server.plugin_registry import PluginRegistry, requires_plugin


def _run(coro):
    return asyncio.run(coro)


def _make_registry(plugins_by_host: dict, ttl: float = 300.0) -> PluginRegistry:
    async def run_curl(args, base_url):
        return json.dumps(plugins_by_host.get(base_url, {}))

    config = {"gerrit_hosts": [{"external_url": url} for url in plugins_by_host]}
    return PluginRegistry(
        run_curl=run_curl,
        normalize_url=lambda u: u.rstrip("/"),
        load_config=lambda: config,
        ttl_seconds=ttl,
    )


class TestPluginRegistry(unittest.TestCase):
    def test_host_has_plugin_true(self):
        reg = _make_registry({"https://host-a": {"task": {"version": "1.0"}}})
        self.assertTrue(_run(reg.host_has_plugin("https://host-a", "task")))

    def test_host_has_plugin_false(self):
        reg = _make_registry({"https://host-a": {}})
        self.assertFalse(_run(reg.host_has_plugin("https://host-a", "task")))

    def test_disabled_plugin_excluded(self):
        reg = _make_registry({"https://host-a": {"task": {"disabled": True}}})
        self.assertFalse(_run(reg.host_has_plugin("https://host-a", "task")))

    def test_hosts_with_plugin(self):
        reg = _make_registry(
            {
                "https://host-a": {"task": {}},
                "https://host-b": {},
            }
        )
        hosts = _run(reg.hosts_with_plugin("task"))
        self.assertIn("https://host-a", hosts)
        self.assertNotIn("https://host-b", hosts)

    def test_ttl_cache_hit(self):
        call_count = 0

        async def run_curl(args, base_url):
            nonlocal call_count
            call_count += 1
            return json.dumps({"task": {}})

        reg = PluginRegistry(
            run_curl=run_curl,
            normalize_url=lambda u: u,
            load_config=lambda: {"gerrit_hosts": [{"external_url": "https://host-a"}]},
            ttl_seconds=300.0,
        )
        _run(reg.host_has_plugin("https://host-a", "task"))
        _run(reg.host_has_plugin("https://host-a", "task"))
        self.assertEqual(call_count, 1)

    def test_invalidate_single_host(self):
        call_count = 0

        async def run_curl(args, base_url):
            nonlocal call_count
            call_count += 1
            return json.dumps({"task": {}})

        reg = PluginRegistry(
            run_curl=run_curl,
            normalize_url=lambda u: u,
            load_config=lambda: {"gerrit_hosts": [{"external_url": "https://host-a"}]},
            ttl_seconds=300.0,
        )
        _run(reg.host_has_plugin("https://host-a", "task"))
        reg.invalidate("https://host-a")
        self.assertNotIn("https://host-a", reg._cache)
        self.assertNotIn("https://host-a", reg._locks)

    def test_invalidate_all(self):
        reg = _make_registry(
            {
                "https://host-a": {"task": {}},
                "https://host-b": {"task": {}},
            }
        )
        _run(reg.hosts_with_plugin("task"))
        reg.invalidate()
        self.assertEqual(reg._cache, {})
        self.assertEqual(reg._locks, {})

    def test_plugin_version(self):
        reg = _make_registry({"https://host-a": {"task": {"version": "2.3"}}})
        v = _run(reg.plugin_version("https://host-a", "task"))
        self.assertEqual(v, "2.3")

    def test_plugin_version_missing(self):
        reg = _make_registry({"https://host-a": {}})
        v = _run(reg.plugin_version("https://host-a", "task"))
        self.assertIsNone(v)


class TestRequiresPlugin(unittest.TestCase):
    def _make_reg(self, has_plugin: bool) -> PluginRegistry:
        async def run_curl(args, base_url):
            return json.dumps({"task": {}} if has_plugin else {})

        return PluginRegistry(
            run_curl=run_curl,
            normalize_url=lambda u: u,
            load_config=lambda: {"gerrit_hosts": [{"external_url": "https://host-a"}]},
        )

    def test_routes_to_available_host(self):
        reg = self._make_reg(has_plugin=True)
        received_url = []

        @requires_plugin("task", reg)
        async def my_tool(gerrit_base_url=None):
            received_url.append(gerrit_base_url)
            return "ok"

        result = _run(my_tool())
        self.assertEqual(result, "ok")
        self.assertEqual(received_url, ["https://host-a"])

    def test_soft_hint_when_no_host_has_plugin(self):
        reg = self._make_reg(has_plugin=False)

        @requires_plugin("task", reg)
        async def my_tool(gerrit_base_url=None):
            return "ok"

        with self.assertRaises(RuntimeError) as ctx:
            _run(my_tool())
        self.assertIn("task", str(ctx.exception))

    def test_soft_hint_when_explicit_host_lacks_plugin(self):
        reg = self._make_reg(has_plugin=False)

        @requires_plugin("task", reg)
        async def my_tool(gerrit_base_url=None):
            return "ok"

        with self.assertRaises(RuntimeError) as ctx:
            _run(my_tool(gerrit_base_url="https://host-a"))
        self.assertIn("not installed", str(ctx.exception))

    def test_passes_through_when_host_has_plugin(self):
        reg = self._make_reg(has_plugin=True)

        @requires_plugin("task", reg)
        async def my_tool(gerrit_base_url=None):
            return "done"

        result = _run(my_tool(gerrit_base_url="https://host-a"))
        self.assertEqual(result, "done")


if __name__ == "__main__":
    unittest.main()
