"""FastAPI application: WebSocket trainer endpoint, network voice processing, and DB persistence."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from backend.schemas import PoseData
from backend.coach_engine import OverheadPassCoach
from backend.db_query import save_session

# Integracja z Twoim plikiem voice_listener.py
from backend.voice_listener import VoiceEvent, RecognizedCommand, voice_event_to_ws_message, map_transcript_to_event

# Komponenty Vosk do rozpoznawania mowy na serwerze
from vosk import Model, KaldiRecognizer

logger = logging.getLogger(__name__)

app = FastAPI(title="Volleyball Personal Trainer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INICJALIZACJA MODELU VOSK ---
MODEL_PATH = Path(__file__).parent / "vosk-model-pl"

if not MODEL_PATH.exists():
    logger.error(f"Brak modelu językowego Vosk w ścieżce: {MODEL_PATH.resolve()}")
    raise FileNotFoundError(f"Pobierz model polski i wypakuj go do folderu: {MODEL_PATH}")

vosk_model = Model(str(MODEL_PATH))
network_recognizer = KaldiRecognizer(vosk_model, 16000)


@app.websocket("/ws/trainer")
async def trainer_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("WebSocket /ws/trainer accepted")

    coach = OverheadPassCoach()
    start_session_time = time.time()

    try:
        while True:
            # Reagujemy na typ wiadomości: binarna (mikrofon) lub tekstowa (wizja)
            message = await websocket.receive()

            # 1. OBSŁUGA STRUMIENIA AUDIO (Komendy głosowe z mikrofonu)
            if "bytes" in message:
                audio_data = message["bytes"]
                if network_recognizer.AcceptWaveform(audio_data):
                    result = json.loads(network_recognizer.Result())
                    transcript = result.get("text", "").strip()

                    if transcript:
                        logger.info(f"Vosk usłyszał komendę: '{transcript}'")

                        # Mapowanie tekstu przy użyciu funkcji z Twojego voice_listener.py
                        detected_event = map_transcript_to_event(transcript)

                        if detected_event != VoiceEvent.UNKNOWN:
                            cmd = RecognizedCommand(transcript=transcript, event=detected_event)

                            # Bezpieczne pobranie liczby powtórzeń (silnik ma sesję lub sprawdzamy bezpośrednio)
                            reps_done = 0
                            if hasattr(coach, 'session') and coach.session:
                                reps_done = coach.session.total_reps

                            # Budujemy pełny pakiet JSON z komunikatem głosowym
                            payload = voice_event_to_ws_message(cmd, rep_target=None, reps_done=reps_done)

                            logger.info(f"Wysyłam event głosowy do frontendu: {payload}")
                            await websocket.send_json(payload)

            # 2. OBSŁUGA KLATEK WIDEO / POSE LANDMARKS (Oryginalny tekst JSON)
            elif "text" in message:
                raw_text = message["text"]

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

                # Zachowana w 100% oryginalna, działająca metoda i kolejność parametrów z coach_engine.py
                result = coach.process_frame(_pose.camera, _pose.landmarks)

                if result:
                    await websocket.send_json(result)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception(f"Błąd pętli głównej serwera: {e}")
    finally:
        logger.info("WebSocket /ws/trainer handler exiting - Próba zapisu sesji...")

        # --- BEZPIECZNY ZAPIS DO BAZY DANYCH PO ZAKOŃCZENIU TRENINGU ---
        # Sprawdzamy statystyki sesji z obiektu coach (jeśli silnik rejestruje powtórzenia w coach.session)
        stats = getattr(coach, 'session', None)

        # Szybki fallback: jeśli silnik nie ma właściwości .session, ale zlicza repCount bezpośrednio w zmiennych
        if not stats and hasattr(coach, 'state'):
            logger.info("Zapis do bazy danych: Brak składowej .session w silniku, pomijam automatyczny eksport.")
        elif stats and stats.total_reps > 0:
            try:
                duration = int(time.time() - start_session_time)
                accuracy = round((stats.good_reps / stats.total_reps) * 100, 1) if stats.total_reps > 0 else 0.0

                avg_leg = round(sum(stats.leg_angles) / len(stats.leg_angles), 1) if stats.leg_angles else 0.0
                avg_body = round(sum(stats.shoulder_angles) / len(stats.shoulder_angles), 1) if stats.shoulder_angles else 0.0
                avg_arm = round(sum(stats.arm_angles) / len(stats.arm_angles), 1) if stats.arm_angles else 0.0

                training_id = save_session(
                    training_type="górne",
                    duration=duration,
                    overall_accuracy=accuracy,
                    leg_angle=avg_leg,
                    body_angle=avg_body,
                    arm_angle=avg_arm
                )
                logger.info(f"Sesja treningowa została pomyślnie zapisana w bazie pod ID: {training_id}")
            except Exception as db_exc:
                logger.error(f"Nie udało się zapisać danych sesji do bazy danych: {db_exc}")