"""FastAPI application: WebSocket trainer endpoint and CORS (development)."""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from backend.schemas import PoseData

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
