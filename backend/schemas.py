from pydantic import BaseModel, field_validator


class Landmark(BaseModel):
    # konkretny punkt na ciele
    x: float
    y: float
    z: float
    visibility: float


class PoseData(BaseModel):
    # media pipe wymaga 33 punktow dla klatki
    camera: str  # "front" lub "side"
    landmarks: list[Landmark]

    @field_validator("landmarks")
    @classmethod
    def exactly_33_landmarks(cls, value: list[Landmark]) -> list[Landmark]:
        if len(value) != 33:
            msg = "Landmarks musi zawierać dokładnie 33 elementy"
            raise ValueError(msg)
        return value