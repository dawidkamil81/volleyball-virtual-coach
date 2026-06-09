"""FastAPI application: WebSocket trainer endpoint and CORS (development)."""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from backend.schemas import CoachFeedback, CoachIssue, PoseData
from backend.analysis.overhead_pass import detect_overhead_pass_issues, SessionState

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
    
    # NOWOŚĆ: Tworzymy pamięć na czas trwania tego konkretnego połączenia (treningu)
    session_state = SessionState()
    
    try:
        while True:
            try:
                raw_text = await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
                break

            try:
                pose = PoseData.model_validate_json(raw_text)
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

            # NOWOŚĆ: Przekazujemy naszą pamięć sesji (session_state) do silnika analitycznego
            detection = detect_overhead_pass_issues(
                pose.landmarks,
                pose.side_landmarks,
                state=session_state
            )
            feedback = CoachFeedback(
                status="ok",
                pass_type="overhead",
                issues=[CoachIssue(code=i.code, message=i.message) for i in detection.issues],
                peak_valid=detection.peak_valid,
                phase=detection.phase,
            )
            await websocket.send_json(feedback.model_dump())
    finally:
        logger.info("WebSocket /ws/trainer handler exiting")