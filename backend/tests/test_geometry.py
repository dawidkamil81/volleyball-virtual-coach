from __future__ import annotations

import math

from backend.analysis.geometry import Vec3, angle_degrees


def test_angle_degrees_right_angle() -> None:
    a = Vec3(1.0, 0.0, 0.0)
    b = Vec3(0.0, 0.0, 0.0)
    c = Vec3(0.0, 1.0, 0.0)
    ang = angle_degrees(a, b, c)
    assert math.isfinite(ang)
    assert 89.9 < ang < 90.1


def test_angle_degrees_degenerate() -> None:
    a = Vec3(0.0, 0.0, 0.0)
    b = Vec3(0.0, 0.0, 0.0)
    c = Vec3(1.0, 0.0, 0.0)
    ang = angle_degrees(a, b, c)
    assert math.isnan(ang)

