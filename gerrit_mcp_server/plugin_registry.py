"""Lazy per-host discovery and routing for Gerrit-plugin-backed tools.

Extensions wrapping a Gerrit plugin decorate their tools with
:func:`requires_plugin`. The decorator auto-routes to a host that has
the plugin installed, or returns a soft hint instead of raising when
the target host lacks it. :class:`PluginRegistry` queries
``/plugins/?all`` lazily per host, caches with a TTL, and filters
disabled entries.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

TTL_SECONDS = 3600.0


@dataclass
class _HostPluginCache:
    plugins: dict[str, dict[str, Any]] = field(default_factory=dict)
    fetched_at: float = 0.0
    error: str | None = None


class PluginRegistry:
    """Per-host cache of installed Gerrit plugins, populated lazily.

    Results live for ``ttl_seconds``; use :meth:`invalidate` to refresh.
    """

    def __init__(
        self,
        run_curl: Callable[[list[str], str], Awaitable[str]],
        normalize_url: Callable[[str], str],
        load_config: Callable[[], dict[str, Any]],
        ttl_seconds: float = TTL_SECONDS,
    ) -> None:
        self._run_curl = run_curl
        self._normalize_url = normalize_url
        self._load_config = load_config
        self._ttl = ttl_seconds
        self._cache: dict[str, _HostPluginCache] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def configured_hosts(self) -> list[str]:
        """Return every host declared in config as a normalized base URL."""
        config = self._load_config() or {}
        urls: list[str] = []
        for host in config.get("gerrit_hosts", []) or []:
            raw_url = host.get("external_url") or host.get("internal_url")
            if raw_url:
                urls.append(self._normalize_url(raw_url))
        return list(dict.fromkeys(urls))

    async def hosts_with_plugin(self, plugin_name: str) -> list[str]:
        """Configured hosts that currently have ``plugin_name`` installed."""
        out: list[str] = []
        for base_url in self.configured_hosts():
            entries = await self._get_host_plugins(base_url)
            if plugin_name in entries:
                out.append(base_url)
        return out

    async def host_has_plugin(self, base_url: str, plugin_name: str) -> bool:
        base_url = self._normalize_url(base_url)
        entries = await self._get_host_plugins(base_url)
        return plugin_name in entries

    async def plugin_version(self, base_url: str, plugin_name: str) -> str | None:
        base_url = self._normalize_url(base_url)
        entries = await self._get_host_plugins(base_url)
        entry = entries.get(plugin_name) or {}
        version = entry.get("version")
        return version if isinstance(version, str) else None

    def invalidate(self, base_url: str | None = None) -> None:
        """Drop the cache for one host, or all hosts when ``base_url`` is None."""
        if base_url is None:
            self._cache.clear()
            self._locks.clear()
            return
        normalized = self._normalize_url(base_url)
        self._cache.pop(normalized, None)
        self._locks.pop(normalized, None)

    async def _get_host_plugins(
        self, base_url: str, force_refresh: bool = False
    ) -> dict[str, dict[str, Any]]:
        now = time.monotonic()
        cache = self._cache.get(base_url)
        if (
            not force_refresh
            and cache is not None
            and cache.error is None
            and (now - cache.fetched_at) < self._ttl
        ):
            return cache.plugins

        lock = self._locks.setdefault(base_url, asyncio.Lock())
        async with lock:
            cache = self._cache.get(base_url)
            if (
                not force_refresh
                and cache is not None
                and cache.error is None
                and (time.monotonic() - cache.fetched_at) < self._ttl
            ):
                return cache.plugins

            try:
                raw = await self._run_curl([f"{base_url}/plugins/?all"], base_url)
                data = json.loads(raw) if raw else {}
            except Exception as exc:
                prev = self._cache.get(base_url)
                self._cache[base_url] = _HostPluginCache(
                    plugins=prev.plugins if prev else {},
                    fetched_at=time.monotonic(),
                    error=str(exc),
                )
                return prev.plugins if prev else {}

            plugins: dict[str, dict[str, Any]] = {}
            if isinstance(data, dict):
                for name, entry in data.items():
                    if not isinstance(entry, dict):
                        continue
                    if entry.get("disabled") is True:
                        continue
                    plugins[name] = entry

            self._cache[base_url] = _HostPluginCache(
                plugins=plugins, fetched_at=time.monotonic(), error=None
            )
            return plugins


def requires_plugin(
    plugin_name: str,
    registry: PluginRegistry,
    *,
    param_name: str = "gerrit_base_url",
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Route a tool through :class:`PluginRegistry` to the right host.

    The wrapped coroutine must accept a ``gerrit_base_url`` kwarg. If
    unset, the first host with ``plugin_name`` installed is used. If the
    caller-supplied host lacks the plugin, the cache is refreshed once,
    then a ``RuntimeError`` listing available hosts is raised. When no host
    has the plugin, the underlying tool is skipped and a ``RuntimeError``
    is raised instead.

    Raising (rather than returning a content-block list) keeps the wrapper
    compatible with tools that declare a structured ``TypedDict`` return
    type: the MCP SDK validates a tool's return value against its
    auto-generated output schema, so a content-block list would fail
    validation. The raised error propagates to the caller as a tool error.
    """

    def decorator(
        func: Callable[..., Awaitable[Any]],
    ) -> Callable[..., Awaitable[Any]]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            override = kwargs.get(param_name)
            if override:
                if not await registry.host_has_plugin(override, plugin_name):
                    registry.invalidate(override)
                    if not await registry.host_has_plugin(override, plugin_name):
                        available = await registry.hosts_with_plugin(plugin_name)
                        raise RuntimeError(_soft_hint(plugin_name, override, available))
                return await func(*args, **kwargs)

            available = await registry.hosts_with_plugin(plugin_name)
            if not available:
                raise RuntimeError(_soft_hint(plugin_name, None, []))
            kwargs[param_name] = available[0]
            return await func(*args, **kwargs)

        wrapper.__wrapped__ = func  # type: ignore[attr-defined]
        wrapper.__name__ = getattr(func, "__name__", "wrapped_tool")
        wrapper.__doc__ = func.__doc__
        wrapper._plugin_name = plugin_name  # type: ignore[attr-defined]
        return wrapper

    return decorator


def _soft_hint(
    plugin_name: str,
    target: str | None,
    available: list[str],
) -> str:
    if target and available:
        return (
            f"Plugin '{plugin_name}' is not installed on {target}. "
            f"Available on: {', '.join(available)}. "
            f"Retry with gerrit_base_url set to one of those hosts."
        )
    elif target:
        return (
            f"Plugin '{plugin_name}' is not installed on {target}, and no "
            f"other configured host has it either."
        )
    return f"Plugin '{plugin_name}' is not installed on any configured Gerrit host."
