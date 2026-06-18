from pydantic import BaseModel, field_validator


class Landmark(BaseModel):
    # Konkretny trójwymiarowy punkt na ciele (zwracany m.in. przez MediaPipe) wraz ze współczynnikiem pewności detekcji
    x: float
    y: float
    z: float
    visibility: float


class PoseData(BaseModel):
    # MediaPipe wymaga dokładnie 33 punktów do poprawnej reprezentacji sylwetki w danej klatce wideo
    camera: str  # "front" (widok z przodu) lub "side" (widok z profilu)
    landmarks: list[Landmark]

    # Walidator sprawdzający, czy lista punktów przesłana z frontendu posiada wymaganą długość
    @field_validator("landmarks")
    @classmethod
    def exactly_33_landmarks(cls, value: list[Landmark]) -> list[Landmark]:
        if len(value) != 33:
            msg = "Landmarks musi zawierać dokładnie 33 elementy"
            raise ValueError(msg)
        return value

class TrainingSummary(BaseModel):
    # Struktura danych przesyłana na koniec sesji treningowej w celu archiwizacji w bazie danych
    training_type: str
    start_time: str
    end_time: str
    duration: int
    successful_reps: int
    total_attempts: int
    overall_accuracy: float