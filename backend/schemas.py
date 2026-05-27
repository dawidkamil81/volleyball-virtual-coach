
from pydantic import BaseModel, field_validator


class Landmark(BaseModel):
    #konkretny punkt na ciele

    x: float
    y: float
    z: float
    visibility: float


class PoseData(BaseModel):
    #media pipe wymaga 33 punktow dla klatki (kamera front)

    landmarks: list[Landmark]
    # opcjonalnie: kamera boczna (kolana / praca nóg)
    side_landmarks: list[Landmark] | None = None

    @field_validator("landmarks")
    @classmethod
    def exactly_33_landmarks(cls, value: list[Landmark]) -> list[Landmark]:
        if len(value) != 33:
            msg = "Landmarks musi zawierać dokładnie 33 elementy"
            raise ValueError(msg)
        return value

    @field_validator("side_landmarks")
    @classmethod
    def side_exactly_33_when_present(
        cls, value: list[Landmark] | None
    ) -> list[Landmark] | None:
        if value is None:
            return value
        if len(value) != 33:
            msg = "side_landmarks musi zawierać dokładnie 33 elementy"
            raise ValueError(msg)
        return value


class CoachIssue(BaseModel):
    code: str
    message: str


class CoachFeedback(BaseModel):
    status: str  # "ok" | "error"
    pass_type: str  # e.g. "overhead"
    issues: list[CoachIssue]
    peak_valid: bool = False  # klatka kwalifikująca się do zaliczenia powtórzenia