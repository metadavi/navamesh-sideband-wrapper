"""
settings.py — farmui-local persistent settings (JSON in app_dir).
Never touches core/RNS config; stores gateway pinning and UI prefs only.
RNS interface discovery is handled automatically by Reticulum's AutoInterface.
"""
from __future__ import annotations

import json
import os
from typing import Optional


_DEFAULT = {
    "gateway_hash":         None,
    "gateway_display_name": None,
    "node_cache":           [],
    "peer_aliases":         {},
    "update_urls":          None,   # None → updater's DEFAULT_UPDATE_URLS
    "dev_mode":             False,
}


class FarmSettings:
    def __init__(self, app_dir: str):
        self._path = os.path.join(app_dir, "farmui_settings.json")
        self._data = dict(_DEFAULT)
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path) as f:
                    self._data.update(json.load(f))
            except Exception:
                pass

    def _save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2)

    @property
    def gateway_hash(self) -> Optional[str]:
        return self._data.get("gateway_hash")

    @gateway_hash.setter
    def gateway_hash(self, value: Optional[str]):
        self._data["gateway_hash"] = value
        self._save()

    @property
    def gateway_display_name(self) -> Optional[str]:
        return self._data.get("gateway_display_name")

    @gateway_display_name.setter
    def gateway_display_name(self, value: Optional[str]):
        self._data["gateway_display_name"] = value
        self._save()

    @property
    def node_cache(self) -> list[str]:
        return self._data.get("node_cache", [])

    @node_cache.setter
    def node_cache(self, value: list[str]):
        self._data["node_cache"] = list(value)
        self._save()

    # ── Local peer aliases (UI-only) ────────────────────────────────────────
    # Maps a peer's LXMF destination hash (hex) → the farmer's local name for
    # it. Purely a wrapper-side display preference stored in this JSON file; it
    # never alters LXMF app_data, Sideband contacts, identities, messages, or
    # the announce DB, and it changes nothing about what either device announces.
    @property
    def peer_aliases(self) -> dict:
        return dict(self._data.get("peer_aliases", {}))

    def get_peer_alias(self, dest_hex: str) -> Optional[str]:
        return self._data.get("peer_aliases", {}).get(dest_hex)

    def set_peer_alias(self, dest_hex: str, alias: str):
        a = dict(self._data.get("peer_aliases", {}))
        a[dest_hex] = str(alias)
        self._data["peer_aliases"] = a
        self._save()

    def clear_peer_alias(self, dest_hex: str):
        a = dict(self._data.get("peer_aliases", {}))
        if dest_hex in a:
            del a[dest_hex]
            self._data["peer_aliases"] = a
            self._save()

    def set_gateway(self, display_name: str, hash_hex: str):
        self._data["gateway_hash"]         = hash_hex
        self._data["gateway_display_name"] = display_name
        self._save()

    def clear_gateway(self):
        self._data["gateway_hash"]         = None
        self._data["gateway_display_name"] = None
        self._save()

    # ── Over-the-air update sources (wrapper-only) ──────────────────────────
    # Base URLs polled for version.json (see farmui/updater.py). None/empty
    # means "use the built-in default" (the farm Pi's conventional address),
    # so shipping a new default in an update takes effect without touching
    # phones that never customised the list.
    @property
    def update_urls(self) -> list[str]:
        urls = self._data.get("update_urls")
        if not urls:
            from .updater import DEFAULT_UPDATE_URLS
            return list(DEFAULT_UPDATE_URLS)
        return [str(u) for u in urls]

    @update_urls.setter
    def update_urls(self, value):
        self._data["update_urls"] = list(value) if value else None
        self._save()

    @property
    def dev_mode(self) -> bool:
        """Developer mode — surfaces the optional Debug diagnostics tab. Off by default."""
        return bool(self._data.get("dev_mode", False))

    @dev_mode.setter
    def dev_mode(self, value: bool):
        self._data["dev_mode"] = bool(value)
        self._save()
