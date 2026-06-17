"""FastAPI application: WebSocket trainer endpoint, Voice commands, and DB persistence."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from backend.schemas import PoseData
from backend.coach_engine import OverheadPassCoach
from backend.db_query import save_session_from_stats
from backend.voice_listener import VoskSpeechListener, RecognizedCommand, VoiceEvent, voice_event_to_ws_message

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

    # Inicjalizacja silnika trenera
    coach = OverheadPassCoach()

    # Kolejka do przekazywania komend głosowych z wątku Vosk do asynchronicznej pętli FastAPI
    loop = asyncio.get_running_loop()
    voice_queue: asyncio.Queue[RecognizedCommand] = asyncio.Queue()

    # Callback wywoływany w wątku tła przez Vosk
    def on_voice_command(cmd: RecognizedCommand) -> None:
        # Wrzucamy bezpiecznie do asynchronicznej kolejki głównego wątku
        loop.call_soon_threadsafe(voice_queue.put_nowait, cmd)

    # Uruchomienie nasłuchu Vosk
    listener = VoskSpeechListener(callback=on_voice_command)
    listener.start()

    # Flaga sterująca aktywnością treningu (wykorzystywana przez komendy głosowe)
    is_paused = False
    stop_requested = False

    try:
        while not stop_requested:
            # 1. Obsługa komend głosowych z kolejki (jeśli jakieś czekają)
            while not voice_queue.empty():
                cmd = voice_queue.get_nowait()
                logger.info(f"Przetwarzanie komendy głosowej: {cmd.event}")

                # Reakcja na komendy głosowe po stronie backendu
                if cmd.event == VoiceEvent.PAUSE:
                    is_paused = True
                elif cmd.event == VoiceEvent.RESUME:
                    is_paused = False
                elif cmd.event == VoiceEvent.RESET:
                    # Resetujemy instancję trenera (tworzymy nowe statystyki)
                    coach = OverheadPassCoach()
                elif cmd.event == VoiceEvent.STOP:
                    stop_requested = True

                # Konwersja na format wiadomości dla frontendu
                ws_msg = voice_event_to_ws_message(
                    cmd=cmd,
                    rep_target=None,  # Możesz tu przekazać docelową liczbę, jeśli aplikacja ją wspiera
                    reps_done=coach.session.total_reps
                )
                await websocket.send_json(ws_msg)

                if stop_requested:
                    break

            if stop_requested:
                break

            # 2. Oczekiwanie na ramkę wideo z timeoutem, aby pętla mogła sprawdzać komendy głosowe
            try:
                # Czekamy max 0.01 sekundy na dane z sieci, żeby nie blokować pętli
                raw_text = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
            except asyncio.TimeoutError:
                # Brak nowych ramek wideo w tej iteracji – idziemy dalej sprawdzić głos
                continue
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
                break

            # Jeśli trening jest zapauzowany głosowo, ignorujemy przetwarzanie obrazu
            if is_paused:
                continue

            # 3. Walidacja danych Pose
            try:
                _pose = PoseData.model_validate_json(raw_text)
            except json.JSONDecodeError as exc:
                await websocket.send_json(
                    {"status": "error", "message": "Invalid JSON payload", "detail": str(exc)}
                )
                continue
            except ValidationError as exc:
                await websocket.send_json(
                    {
                        "status": "error",
                        "message": "Pose data validation failed",
                        "errors": exc.errors(include_url=False, include_context=False),
                    }
                )
                continue

            # 4. Przetwarzanie klatki przez Coach Engine
            result = coach.process_frame(_pose.camera, _pose.landmarks)
            if result:
                await websocket.send_json(result)

    except Exception as e:
        logger.exception(f"Błąd w pętli głównej WebSocket: {e}")
    finally:
        # Zatrzymanie wątku mikrofonu
        listener.stop()

        # --- ZAPIS DO BAZY DANYCH ---
        # Zapisujemy tylko wtedy, gdy użytkownik wykonał chociaż próbę (żeby nie śmiecić w DB pustymi sesjami)
        if coach.session.total_reps > 0:
            try:
                logger.info("Koniec treningu. Zapisywanie statystyk sesji do bazy danych...")
                training_id = save_session_from_stats(training_type="górne", stats=coach.session)
                logger.info(f"Sesja pomyślnie zapisana pod ID: {training_id}")
            except Exception as db_exc:
                logger.error(f"Nie udało się zapisać sesji do bazy danych: {db_exc}")
        else:
            logger.info("Sesja zakończona bez wykonanych powtórzeń - pomijam zapis w DB.")

        logger.info("WebSocket /ws/trainer handler exiting")