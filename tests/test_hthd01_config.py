"""
test_hthd01_config.py — HT-HD01 UDP interface via Sideband config template,
plus client-side LXMF address derivation.

The interface must live in config["config_template"] (Sideband regenerates the
RNS config file from it on every service start), NOT in the generated file.
"""
from __future__ import annotations

import os

os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""

import pytest


# ── Template builder ─────────────────────────────────────────────────────────

def test_template_has_hthd01_udp_interface():
    from sbapp.farmui.rns_config_writer import build_config_template
    t = build_config_template()
    assert "[[Navamesh HT-HD01]]" in t
    assert "type = UDPInterface" in t
    assert "listen_ip = 0.0.0.0" in t
    assert "listen_port = 4242" in t
    assert "forward_ip = 192.168.10.255" in t
    assert "forward_port = 4242" in t
    assert "name = HTHD01_UDP" in t


def test_template_keeps_sideband_reticulum_block_and_placeholder():
    from sbapp.farmui.rns_config_writer import build_config_template
    t = build_config_template()
    # enable_transport stays a placeholder Sideband fills from connect_transport
    assert "enable_transport = TRANSPORT_IS_ENABLED" in t
    # Android-correct reticulum settings (NOT Linux/Docker pieces)
    assert "share_instance = Yes" in t
    assert "shared_instance_port = 37428" in t
    assert "instance_control_port = 37429" in t
    assert "panic_on_interface_error = No" in t
    # no Linux/Docker-only AutoInterface
    assert "AutoInterface" not in t


def test_template_params_are_overridable():
    from sbapp.farmui.rns_config_writer import build_config_template
    t = build_config_template(forward_ip="10.0.0.255", listen_port=5252)
    assert "forward_ip = 10.0.0.255" in t
    assert "listen_port = 5252" in t


# ── _ensure_hthd01_config: writes template + transport, idempotent ───────────

class FakeCore:
    def __init__(self, config=None):
        self.config = config if config is not None else {}
        self.saved = 0
        self.identity = None

    def save_configuration(self):
        self.saved += 1


def _app(core):
    from sbapp.farmui.app import FarmApp
    app = FarmApp.__new__(FarmApp)
    app.sideband = core
    return app


def test_ensure_sets_template_and_transport_then_saves():
    from sbapp.farmui.rns_config_writer import build_config_template
    core = FakeCore({"config_template": None, "connect_transport": False})
    app = _app(core)
    changed = app._ensure_hthd01_config()
    assert changed is True
    assert core.config["config_template"] == build_config_template()
    assert core.config["connect_transport"] is True
    assert core.saved == 1


def test_ensure_is_idempotent():
    from sbapp.farmui.rns_config_writer import build_config_template
    core = FakeCore({"config_template": build_config_template(),
                     "connect_transport": True})
    app = _app(core)
    assert app._ensure_hthd01_config() is False
    assert core.saved == 0  # nothing to write


def test_ensure_no_core_is_safe():
    app = _app(None)
    assert app._ensure_hthd01_config() is False


# ── Address derived from the shared identity (client has no lxmf_destination) ─

def test_local_address_from_identity_matches_lxmf_delivery():
    import RNS
    identity = RNS.Identity()  # generate a throwaway identity
    expected = RNS.Destination(
        identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery"
    ).hexhash

    core = FakeCore()
    core.identity = identity            # lxmf_destination intentionally absent
    app = _app(core)
    assert app.local_address() == expected
    # sanity: a real, fixed-length hex address
    assert len(expected) == RNS.Reticulum.TRUNCATED_HASHLENGTH // 8 * 2
    assert all(c in "0123456789abcdef" for c in app.local_address())


def test_local_address_unavailable_without_identity_or_core():
    assert _app(None).local_address() == "unavailable"
    core = FakeCore()
    core.identity = None
    assert _app(core).local_address() == "unavailable"
