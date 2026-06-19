from pydantic import BaseModel, field_validator
from typing import Optional

class Landmark(BaseModel):
    x: float
    y: float
    z: float
    visibility: float

class PoseData(BaseModel):
    camera: str  # "front" lub "side"
    exerciseType: str # "górne" lub "dolne"
    timestamp: Optional[int] = 0
    framesAveraged: Optional[int] = 1
    landmarks: list[Landmark]

    @field_validator("landmarks")
    @classmethod
    def exactly_33_landmarks(cls, value: list[Landmark]) -> list[Landmark]:
        if len(value) != 33:
            msg = "Landmarks musi zawierać dokładnie 33 elementy"
            raise ValueError(msg)
        return value

class TrainingSummary(BaseModel):
    training_type: str
    start_time: str
    end_time: str
    duration: int
    successful_reps: int
    total_attempts: int
    overall_accuracy: float