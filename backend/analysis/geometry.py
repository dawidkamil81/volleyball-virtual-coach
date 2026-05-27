from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Vec3:
    x: float
    y: float
    z: float

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)


def norm(v: Vec3) -> float:
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


def dot(a: Vec3, b: Vec3) -> float:
    return a.x * b.x + a.y * b.y + a.z * b.z


def angle_degrees(a: Vec3, b: Vec3, c: Vec3) -> float:
    """
    Angle ABC in degrees, where the vertex is at B.
    Returns NaN if vectors are degenerate.
    """
    ba = a - b
    bc = c - b
    nba = norm(ba)
    nbc = norm(bc)
    if nba <= 1e-9 or nbc <= 1e-9:
        return float("nan")
    cosv = dot(ba, bc) / (nba * nbc)
    cosv = max(-1.0, min(1.0, cosv))
    return math.degrees(math.acos(cosv))


def distance(a: Vec3, b: Vec3) -> float:
    return norm(a - b)

