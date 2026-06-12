"""
settings.py — farmui-local persistent settings (JSON in app_dir).
Never touches core/RNS config; stores gateway pinning and UI prefs only.
"""
from __future__ import annotations

import json
import os
from typing import Optional


_DEFAULT = {
    "gateway_hash":         None,
    "gateway_display_name": None,
    "node_cache":           [],
    "large_text":           False,
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

    def set_gateway(self, display_name: str, hash_hex: str):
        self._data["gateway_hash"]         = hash_hex
        self._data["gateway_display_name"] = display_name
        self._save()

    def clear_gateway(self):
        self._data["gateway_hash"]         = None
        self._data["gateway_display_name"] = None
        self._save()
