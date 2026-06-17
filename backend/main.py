"""FastAPI application: WebSocket trainer endpoint, network voice processing, and DB persistence."""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from backend.schemas import PoseData
from backend.coach_engine import OverheadPassCoach
from backend.db_query import save_session
from backend.voice_listener import VoskSpeechListener, VoiceEvent, RecognizedCommand, voice_event_to_ws_message

logger = logging.getLogger(__name__)

app = FastAPI(title="Volleyball Personal Trainer", version="0.1.0")

# Inicjalizacja komponentu Vosk bez uruchamiania lokalnego nagrywania PyAudio
# Używamy atrapy callbacku, bo i tak będziemy karmić Voska ręcznie bajtami z sieci
listener = VoskSpeechListener(callback=lambda x: None)

@app.websocket("/ws/trainer")
async def trainer_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("WebSocket /ws/trainer accepted (Microphone stream from frontend allowed)")

    coach = OverheadPassCoach()
    is_paused = False
    stop_requested = False

    try:
        while not stop_requested:
            # Odbieramy dowolną wiadomość (tekstową lub binarną) z sieci
            message = await websocket.receive()

            # --- OPCJA A: Przesłano dźwięk z mikrofonu w przeglądarce (Dane binarne) ---
            if "bytes" in message:
                audio_bytes = message["bytes"]

                # Przekazujemy bajty bezpośrednio do instancji Voska na serwerze
                if listener.rec.AcceptWaveform(audio_bytes):
                    vosk_result = json.loads(listener.rec.Result())
                    transcript = vosk_result.get("text", "").strip()

                    if transcript:
                        logger.info(f"Vosk rozpoznał tekst z sieci: '{transcript}'")
                        cmd = listener.match_command(transcript)

                        if cmd:
                            logger.info(f"Dopasowano komendę: {cmd.event}")
                            # Logika zmiany stanu na serwerze
                            if cmd.event == VoiceEvent.PAUSE:
                                is_paused = True
                            elif cmd.event == VoiceEvent.RESUME:
                                is_paused = False
                            elif cmd.event == VoiceEvent.RESET:
                                coach = OverheadPassCoach()
                            elif cmd.event == VoiceEvent.STOP:
                                stop_requested = True

                            # Odesłanie potwierdzenia komendy głosowej na frontend
                            ws_msg = voice_event_to_ws_message(
                                cmd=cmd,
                                rep_target=None,
                                reps_done=coach.session.total_reps
                            )
                            await websocket.send_json(ws_msg)

                            if stop_requested:
                                break

            # --- OPCJA B: Przesłano współrzędne ciała z MediaPipe (Tekst JSON) ---
            elif "text" in message:
                if is_paused:
                    continue  # Ignoruj klatki wideo podczas pauzy

                raw_text = message["text"]
                try:
                    _pose = PoseData.model_validate_json(raw_text)
                except (json.JSONDecodeError, ValidationError) as exc:
                    # Ignoruj pojedyncze błędy walidacji ramek sieciowych
                    continue

                # Przetwarzanie klatki przez Coach Engine
                result = coach.process_frame(_pose.camera, _pose.landmarks)
                if result:
                    await websocket.send_json(result)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception(f"Błąd w pętli głównej serwera: {e}")
    finally:
        # --- ZAPIS DO BAZY DANYCH PO ZAKOŃCZENIU ---
        if coach.session.total_reps > 0:
            try:
                logger.info("Zapisywanie ukończonej sesji treningowej do SQLite...")
                # Wyciągamy statystyki z silnika
                stats = coach.session
                duration = int(stats.get_duration())
                accuracy = stats.accuracy

                # Obliczanie średnich kątów
                avg_leg = sum(stats.leg_angles) / len(stats.leg_angles) if stats.leg_angles else 0.0
                avg_body = sum(stats.shoulder_angles) / len(stats.shoulder_angles) if stats.shoulder_angles else 0.0
                avg_arm = sum(stats.arm_angles) / len(stats.arm_angles) if stats.arm_angles else 0.0

                training_id = save_session(
                    training_type="górne",
                    duration=duration,
                    overall_accuracy=accuracy,
                    leg_angle=avg_leg,
                    body_angle=avg_body,
                    arm_angle=avg_arm
                )
                logger.info(f"Sesja pomyślnie zapisana w DB pod ID: {training_id}")
            except Exception as db_exc:
                logger.error(f"Nie udało się zapisać danych do bazy: {db_exc}")
        else:
            logger.info("Brak powtórzeń w tej sesji – pomijam zapis w DB.")

        logger.info("WebSocket /ws/trainer handler exiting")