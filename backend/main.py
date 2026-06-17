"""FastAPI application: WebSocket trainer endpoint, network voice processing, and DB persistence."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from backend.schemas import PoseData
from backend.coach_engine import OverheadPassCoach
from backend.db_query import save_session
from backend.voice_listener import VoiceEvent, RecognizedCommand, voice_event_to_ws_message

# Importujemy oficjalne komponenty Voska bezpośrednio dla serwera
from vosk import Model, KaldiRecognizer

logger = logging.getLogger(__name__)

app = FastAPI(title="Volleyball Personal Trainer", version="0.1.0")

# --- INICJALIZACJA VOSKA BEZPOŚREDNIO NA SERWERZE ---
MODEL_PATH = Path(__file__).parent / "vosk-model-pl"

if not MODEL_PATH.exists():
    logger.error(f"Brak modelu językowego Vosk w ścieżce: {MODEL_PATH.resolve()}")
    raise FileNotFoundError(f"Pobierz model polski i wypakuj go do folderu: {MODEL_PATH}")

# Ładujemy model do pamięci RAM serwera tylko raz przy starcie aplikacji
vosk_model = Model(str(MODEL_PATH))
# Tworzymy rozpoznawacz dla dźwięku mono 16000Hz (taki wysyła nasz frontend)
network_recognizer = KaldiRecognizer(vosk_model, 16000)


# --- SŁOWNIK MAPOWANIA KOMEND GŁOSOWYCH NA SERWERZE ---
def map_transcript_to_event(transcript: str) -> VoiceEvent | None:
    """Mapuje rozpoznany tekst z sieci na odpowiednie zdarzenie treningowe."""
    text = transcript.lower().strip()

    if any(word in text for word in ["pauza", "czekaj", "stopuj"]):
        return VoiceEvent.PAUSE
    elif any(word in text for word in ["wznów", "dalej", "start", "dawaj", "wznow"]):
        return VoiceEvent.RESUME
    elif any(word in text for word in ["reset", "od nowa", "wyczyść", "wyczysc"]):
        return VoiceEvent.RESET
    elif any(word in text for word in ["koniec", "zakończ", "zakoncz", "stop"]):
        return VoiceEvent.STOP

    return None


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

                # Karmimy nasz sieciowy rozpoznawacz bajtami z pokoju treningowego
                if network_recognizer.AcceptWaveform(audio_bytes):
                    vosk_result = json.loads(network_recognizer.Result())
                    transcript = vosk_result.get("text", "").strip()

                    if transcript:
                        logger.info(f"Vosk rozpoznał tekst z sieci: '{transcript}'")

                        # Wywołujemy naszą lokalną funkcję mapującą zamiast helpera
                        matched_event = map_transcript_to_event(transcript)

                        if matched_event:
                            logger.info(f"Dopasowano komendę: {matched_event}")

                            # Logika zmiany stanu na serwerze
                            if matched_event == VoiceEvent.PAUSE:
                                is_paused = True
                            elif matched_event == VoiceEvent.RESUME:
                                is_paused = False
                            elif matched_event == VoiceEvent.RESET:
                                coach = OverheadPassCoach()
                            elif matched_event == VoiceEvent.STOP:
                                stop_requested = True

                            # Tworzymy obiekt komendy wymagany przez funkcję pomocniczą frontendu
                            cmd_obj = RecognizedCommand(event=matched_event, transcript=transcript)

                            # Odesłanie potwierdzenia komendy głosowej na frontend
                            ws_msg = voice_event_to_ws_message(
                                cmd=cmd_obj,
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
                except (json.JSONDecodeError, ValidationError):
                    # Ignoruj błędy pojedynczych uszkodzonych ramek sieciowych
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
                stats = coach.session
                duration = int(stats.get_duration())
                accuracy = stats.accuracy

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