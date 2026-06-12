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
    "hthd01_ip":            "",
    "hthd01_port":          4242,
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

    @property
    def hthd01_ip(self) -> str:
        return self._data.get("hthd01_ip", "")

    @hthd01_ip.setter
    def hthd01_ip(self, value: str):
        self._data["hthd01_ip"] = value.strip()
        self._save()

    @property
    def hthd01_port(self) -> int:
        return int(self._data.get("hthd01_port", 4242))

    @hthd01_port.setter
    def hthd01_port(self, value: int):
        self._data["hthd01_port"] = int(value)
        self._save()

    def write_hthd01_to_rns_config(self, rns_config_path: str) -> None:
        """Write the HT-HD01 UDP interface block into the RNS config file."""
        if not self.hthd01_ip:
            raise ValueError("HT-HD01 IP not configured")
        from .rns_config_writer import write_hthd01_interface
        write_hthd01_interface(
            rns_config_path,
            listen_ip="0.0.0.0",
            listen_port=self.hthd01_port,
            forward_ip=self.hthd01_ip,
            forward_port=self.hthd01_port,
        )
