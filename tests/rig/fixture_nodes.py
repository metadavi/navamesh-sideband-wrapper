"""
Fixture node data for the stub gateway.
3 nodes with GPS (one dry, one ok, one wet) + 1 node without GPS.
Mirrors the NodeSnapshot dataclass from reticulum_bridge.py.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class NodeSnapshot:
    node_id: str
    ts: Optional[int] = None
    soil_raw: Optional[float] = None
    soil_percent: Optional[float] = None
    battery_level: Optional[float] = None
    battery_usb: Optional[bool] = None
    voltage: Optional[float] = None
    uptime_seconds: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    alt: Optional[float] = None
    rx_rssi: Optional[float] = None
    rx_snr: Optional[float] = None


FIXTURE_NODES = {
    "!drynode001": NodeSnapshot(
        node_id="!drynode001",
        ts=1700000000,
        soil_percent=20.0,
        battery_level=45.0,
        voltage=3.65,
        uptime_seconds=3661,
        lat=26.123456,
        lon=-80.234567,
        rx_rssi=-95.0,
        rx_snr=3.5,
    ),
    "!oknode0002": NodeSnapshot(
        node_id="!oknode0002",
        ts=1700000100,
        soil_percent=55.0,
        battery_level=78.0,
        voltage=3.85,
        uptime_seconds=7200,
        lat=26.124567,
        lon=-80.235678,
        rx_rssi=-82.0,
        rx_snr=7.2,
    ),
    "!wetnode003": NodeSnapshot(
        node_id="!wetnode003",
        ts=1700000200,
        soil_percent=75.0,
        battery_usb=True,
        lat=26.125678,
        lon=-80.236789,
        rx_rssi=-71.0,
        rx_snr=9.1,
    ),
    "!nogpsnode4": NodeSnapshot(
        node_id="!nogpsnode4",
        ts=1700000300,
        soil_percent=40.0,
        battery_level=60.0,
        voltage=3.75,
        rx_rssi=-88.0,
        rx_snr=5.0,
    ),
}
