"""FastAPI application: WebSocket trainer endpoint and CORS (development)."""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from backend.schemas import PoseData, TrainingSummary
from backend.db_query import save_training_session, get_trainings
from backend.coach_engine import OverheadPassCoach, BumpPassCoach

# Inicjalizacja loggera dla potrzeb debugowania i rejestrowania zdarzeń aplikacji
logger = logging.getLogger(__name__)

# Instancja głównej aplikacji FastAPI
app = FastAPI(title="Volleyball Personal Trainer", version="0.1.0")

# Konfiguracja polityki CORS umożliwiającej aplikacjom klienckim (np. frontendowi w React/Vue) odpytywanie API z innych adresów
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Punkt końcowy (POST) służący do zapisu podsumowania zakończonej sesji treningowej w bazie danych
@app.post("/api/training/save")
async def save_training_endpoint(summary: TrainingSummary):
    try:
        # Przekazanie zwalidowanych danych z obiektu Pydantic bezpośrednio do funkcji bazodanowej
        training_id = save_training_session(
            training_type=summary.training_type,
            start_time=summary.start_time,
            end_time=summary.end_time,
            duration=summary.duration,
            successful_reps=summary.successful_reps,
            total_attempts=summary.total_attempts,
            overall_accuracy=summary.overall_accuracy
        )
        return {"status": "success", "training_id": training_id}
    except Exception as e:
        logger.error(f"Błąd zapisu w bazie: {e}")
        return {"status": "error", "message": str(e)}

# Punkt końcowy (GET) zwracający listę wszystkich treningów historycznych dla widoku statystyk
@app.get("/api/training/stats")
async def get_training_stats_endpoint():
    try:
        trainings = get_trainings()
        return {"status": "success", "data": trainings}
    except Exception as e:
        logger.error(f"Błąd pobierania bazy: {e}")
        return {"status": "error", "message": str(e)}

# Komunikacja dwukierunkowa w czasie rzeczywistym (WebSocket) służąca do ciągłej analizy wideo użytkownika
@app.websocket("/ws/trainer")
async def trainer_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("WebSocket /ws/trainer accepted")
    
    # Inicjalizujemy obu trenerów na starcie połączenia
    coach_overhead = OverheadPassCoach()
    coach_bump = BumpPassCoach()
    
    current_exercise_type = None
    
    try:
        while True:
            try:
                raw_text = await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
                break

            try:
                _pose = PoseData.model_validate_json(raw_text)
            except json.JSONDecodeError as exc:
                await websocket.send_json({"status": "error", "message": "Invalid JSON payload"})
                continue
            except ValidationError as exc:
                await websocket.send_json({"status": "error", "message": "Pose data validation failed", "errors": exc.errors()})
                continue

            # Resetujemy stan trenerów, jeśli użytkownik zmieni ćwiczenie w trakcie treningu
            if current_exercise_type != _pose.exerciseType:
                current_exercise_type = _pose.exerciseType
                coach_overhead = OverheadPassCoach()
                coach_bump = BumpPassCoach()

            # Wybór odpowiedniego silnika
            active_coach = coach_bump if _pose.exerciseType == "dolne" else coach_overhead

            # Process frame with active Coach Engine
            result = active_coach.process_frame(_pose.camera, _pose.landmarks)
            
            if result:
                await websocket.send_json(result)
                
    finally:
        logger.info("WebSocket /ws/trainer handler exiting")