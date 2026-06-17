"""FastAPI application: WebSocket trainer endpoint and CORS (development)."""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from backend.schemas import PoseData, TrainingSummary
from backend.db_query import save_training_sessionfrom backend.db_query import save_training_session, get_trainings
from backend.coach_engine import OverheadPassCoach

logger = logging.getLogger(__name__)

app = FastAPI(title="Volleyball Personal Trainer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/training/save")
async def save_training_endpoint(summary: TrainingSummary):
    try:
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

@app.get("/api/training/stats")
async def get_training_stats_endpoint():
    try:
        trainings = get_trainings()
        return {"status": "success", "data": trainings}
    except Exception as e:
        logger.error(f"Błąd pobierania bazy: {e}")
        return {"status": "error", "message": str(e)}

@app.websocket("/ws/trainer")
async def trainer_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("WebSocket /ws/trainer accepted")
    
    coach = OverheadPassCoach()
    
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
                await websocket.send_json(
                    {
                        "status": "error",
                        "message": "Invalid JSON payload",
                        "detail": str(exc),
                    }
                )
                continue
            except ValidationError as exc:
                await websocket.send_json(
                    {
                        "status": "error",
                        "message": "Pose data validation failed",
                        "errors": exc.errors(
                            include_url=False,
                            include_context=False,
                        ),
                    }
                )
                continue

            # Process frame with Coach Engine
            result = coach.process_frame(_pose.camera, _pose.landmarks)
            
            if result:
                await websocket.send_json(result)
                
    finally:
        logger.info("WebSocket /ws/trainer handler exiting")
