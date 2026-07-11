"""
test_map_viewer.py — the full-screen zoom/pan viewer for gateway map replies.

Source guards (repo convention: Kivy widgets can't be instantiated headless
here, and a real pinch gesture needs a device). The contract: tapping the
inline map opens build_map_viewer(), which gives pinch-zoom/pan via a Scatter
with rotation off, an explicit close control, and never dismisses on an image
tap — while the inline display path (CoreImage / image_ext) stays unchanged.
"""
from __future__ import annotations

import inspect
import os

os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""


def test_viewer_is_scatter_with_pinch_zoom_no_rotation():
    from sbapp.farmui import widgets
    src = inspect.getsource(widgets.build_map_viewer)
    assert "ScatterLayout" in src or "Scatter" in src
    assert "do_rotation=False" in src
    assert "scale_min" in src and "scale_max" in src
    assert "auto_dismiss=True" in src  # Android back / ESC still closes it


def test_viewer_has_explicit_close_that_dismisses():
    from sbapp.farmui import widgets
    src = inspect.getsource(widgets.build_map_viewer)
    assert "close" in src
    assert "modal.dismiss" in src


def test_viewer_close_glyph_is_renderable():
    """× (U+00D7) has a glyph in the bundled fonts; ✕/● render as boxes."""
    from sbapp.farmui import widgets
    src = inspect.getsource(widgets.build_map_viewer)
    assert "✕" not in src and "●" not in src


def test_outside_tap_dismisses_only_at_base_zoom():
    """A tap on the letterbox (outside the drawn image) closes the viewer,
    but only while not zoomed in — zoomed touches must keep panning."""
    from sbapp.farmui import widgets
    src = inspect.getsource(widgets.build_map_viewer)
    assert "scatter.scale <=" in src   # gated on base zoom
    assert "to_local" in src           # letterbox test in scatter-local coords
    assert "_drawn_rect" in src


def test_backdrop_is_translucent_dim():
    """The app must stay visible behind the viewer (no near-opaque black)."""
    from sbapp.farmui import widgets
    src = inspect.getsource(widgets.build_map_viewer)
    assert "0.92" not in src
    assert "0.45" in src


def test_image_tap_opens_builder_and_no_longer_dismisses():
    from sbapp.farmui import widgets
    src = inspect.getsource(widgets.ResultCard._on_image_up)
    assert "build_map_viewer" in src
    assert "modal.dismiss" not in src  # old tap-anywhere-dismiss lambda is gone
    assert "_map_press" in src         # tap-vs-scroll guard preserved


def test_inline_image_path_unchanged():
    """The inline card image still decodes via CoreImage with the wire ext."""
    from sbapp.farmui import widgets
    src = inspect.getsource(widgets.ResultCard._attach_image)
    assert "CoreImage" in src
    assert "self._image_ext" in src


def test_back_key_dismisses_open_modal_first():
    """The app-level back handler must close an open modal (map viewer, node
    picker) instead of navigating home underneath it."""
    from sbapp.farmui import app as app_mod
    src = inspect.getsource(app_mod.FarmApp._on_keyboard)
    assert "ModalView" in src
    assert "dismiss" in src
