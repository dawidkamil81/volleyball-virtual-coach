"""
Task 4.4 – Integracja Vosk STT
Task 4.5 – Mapowanie komend głosowych na zdarzenia sterujące

Uruchamia wątek nasłuchujący mikrofon przez PyAudio + Vosk,
rozpoznaje polskie komendy i wysyła zdarzenia do callbacku
(podpinanego przez WebSocket w main.py).

Wymagania (requirements.txt):
    vosk
    pyaudio

Model polski do pobrania:
    https://alphacephei.com/vosk/models  →  vosk-model-small-pl-0.22
    Rozpakuj do katalogu:  backend/vosk-model-pl/
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Zdarzenia sterujące (task 4.5)
# ---------------------------------------------------------------------------

class VoiceEvent(str, Enum):
    """Zdarzenia generowane przez komendy głosowe."""
    START         = "voice_start"       # "Start" / "Zacznij" / "Raz"
    STOP          = "voice_stop"        # "Stop" / "Koniec" / "Zakończ"
    HOW_MANY_LEFT = "voice_how_many"    # "Ile jeszcze?" / "Ile zostało?"
    PAUSE         = "voice_pause"       # "Pauza" / "Czekaj"
    RESUME        = "voice_resume"      # "Wznów" / "Kontynuuj" / "Dalej"
    RESET         = "voice_reset"       # "Reset" / "Od nowa"
    NEXT_EXERCISE = "voice_next"        # "Następne" / "Dalej"
    UNKNOWN       = "voice_unknown"     # Nie rozpoznano


@dataclass(frozen=True)
class RecognizedCommand:
    """Wynik rozpoznania komendy głosowej."""
    transcript: str          # surowy tekst z Vosk
    event: VoiceEvent        # zmapowane zdarzenie
    confidence: float = 1.0  # Vosk nie daje confidence w trybie finalnym, zostawiamy 1.0


# ---------------------------------------------------------------------------
# Słownik fraz → zdarzenie (task 4.5)
# ---------------------------------------------------------------------------

# Każda fraza to ciąg tokenów który musi pojawić się w transkrypcie.
# Porządek decyduje o priorytecie (bardziej szczegółowe pierwsze).

_PHRASE_MAP: list[tuple[list[str], VoiceEvent]] = [
    # Pytania o postęp
    (["ile", "zostało"],    VoiceEvent.HOW_MANY_LEFT),
    (["ile", "jeszcze"],    VoiceEvent.HOW_MANY_LEFT),
    (["ile", "razy"],       VoiceEvent.HOW_MANY_LEFT),
    (["ile"],               VoiceEvent.HOW_MANY_LEFT),

    # Pauza / wznowienie
    (["pauza"],             VoiceEvent.PAUSE),
    (["czekaj"],            VoiceEvent.PAUSE),
    (["wznów"],             VoiceEvent.RESUME),
    (["kontynuuj"],         VoiceEvent.RESUME),
    (["dalej"],             VoiceEvent.RESUME),

    # Reset
    (["reset"],             VoiceEvent.RESET),
    (["od", "nowa"],        VoiceEvent.RESET),
    (["zacznij", "od"],     VoiceEvent.RESET),

    # Następne ćwiczenie
    (["następne"],          VoiceEvent.NEXT_EXERCISE),
    (["następne", "ćwiczenie"], VoiceEvent.NEXT_EXERCISE),

    # Stop / zakończenie (przed "start" żeby "stop" nie matchował "zacznij stop")
    (["stop"],              VoiceEvent.STOP),
    (["koniec"],            VoiceEvent.STOP),
    (["zakończ"],           VoiceEvent.STOP),
    (["skończ"],            VoiceEvent.STOP),

    # Start
    (["start"],             VoiceEvent.START),
    (["zacznij"],           VoiceEvent.START),
    (["raz"],               VoiceEvent.START),
    (["go"],                VoiceEvent.START),
]


def map_transcript_to_event(transcript: str) -> VoiceEvent:
    """
    Task 4.5 – mapuje surowy tekst na VoiceEvent.

    Algorytm: sprawdza czy WSZYSTKIE tokeny frazy występują
    w transkrypcie (w dowolnej kolejności). Pierwsza pasująca
    fraza wygrywa (priorytety ustawione w _PHRASE_MAP).
    """
    words = transcript.lower().split()
    for tokens, event in _PHRASE_MAP:
        if all(tok in words for tok in tokens):
            return event
    return VoiceEvent.UNKNOWN


# ---------------------------------------------------------------------------
# Listener (task 4.4)
# ---------------------------------------------------------------------------

class VoskSpeechListener:
    """
    Task 4.4 – Nasłuchuje mikrofonu przez PyAudio + Vosk (offline STT).

    Użycie:
        def on_command(cmd: RecognizedCommand):
            print(cmd.event, cmd.transcript)

        listener = VoskSpeechListener(callback=on_command)
        listener.start()
        # ... trening trwa ...
        listener.stop()
    """

    MODEL_PATH  = "backend/vosk-model-pl"
    SAMPLE_RATE = 16000
    CHUNK_SIZE  = 8000     # porcja audio ~0.5s przy 16kHz

    def __init__(
        self,
        callback: Callable[[RecognizedCommand], None],
        model_path: str = MODEL_PATH,
        device_index: int | None = None,
    ) -> None:
        self._callback     = callback
        self._model_path   = model_path
        self._device_index = device_index
        self._audio_queue: queue.Queue[bytes] = queue.Queue()
        self._running      = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------

    def start(self) -> None:
        """Uruchamia wątek nasłuchu w tle."""
        if self._running:
            logger.warning("VoskSpeechListener already running")
            return

        # Leniwy import – żeby aplikacja startowała nawet bez Vosk/PyAudio
        try:
            import vosk      # noqa: F401
            import pyaudio   # noqa: F401
        except ImportError as exc:
            logger.error(
                "Brak bibliotek STT: %s. "
                "Zainstaluj: pip install vosk pyaudio  "
                "i pobierz model: https://alphacephei.com/vosk/models",
                exc,
            )
            return

        self._running = True
        self._thread  = threading.Thread(target=self._listen_loop, daemon=True, name="vosk-stt")
        self._thread.start()
        logger.info("VoskSpeechListener started (model=%s)", self._model_path)

    def stop(self) -> None:
        """Zatrzymuje wątek nasłuchu."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("VoskSpeechListener stopped")

    # ------------------------------------------------------------------

    def _listen_loop(self) -> None:
        """Główna pętla: pobiera audio z mikrofonu i rozpoznaje mowę."""
        import vosk
        import pyaudio

        # Ładowanie modelu
        try:
            model = vosk.Model(self._model_path)
        except Exception:
            logger.exception(
                "Nie można załadować modelu Vosk z '%s'. "
                "Pobierz model ze strony: https://alphacephei.com/vosk/models "
                "i rozpakuj do backend/vosk-model-pl/",
                self._model_path,
            )
            self._running = False
            return

        recognizer = vosk.KaldiRecognizer(model, self.SAMPLE_RATE)
        pa         = pyaudio.PyAudio()

        stream_kwargs: dict = dict(
            format           = pyaudio.paInt16,
            channels         = 1,
            rate             = self.SAMPLE_RATE,
            input            = True,
            frames_per_buffer= self.CHUNK_SIZE,
        )
        if self._device_index is not None:
            stream_kwargs["input_device_index"] = self._device_index

        try:
            stream = pa.open(**stream_kwargs)
            logger.info("Mikrofon STT otwarty (rate=%d, chunk=%d)", self.SAMPLE_RATE, self.CHUNK_SIZE)

            while self._running:
                try:
                    data = stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
                except OSError as exc:
                    logger.warning("Błąd odczytu mikrofonu: %s", exc)
                    continue

                if recognizer.AcceptWaveform(data):
                    result_json = recognizer.Result()
                    self._handle_result(result_json)
                else:
                    # Partial result – ignorujemy, chcemy tylko finalne wyniki
                    pass

        except Exception:
            logger.exception("Błąd w pętli nasłuchu Vosk")
        finally:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
            pa.terminate()
            logger.info("Mikrofon STT zamknięty")

    def _handle_result(self, result_json: str) -> None:
        """Parsuje JSON z Vosk i wywołuje callback."""
        try:
            data = json.loads(result_json)
        except json.JSONDecodeError:
            return

        transcript = data.get("text", "").strip()
        if not transcript:
            return

        event   = map_transcript_to_event(transcript)
        command = RecognizedCommand(transcript=transcript, event=event)

        logger.debug("STT rozpoznano: '%s' → %s", transcript, event)
        self._callback(command)


# ---------------------------------------------------------------------------
# Fabryka wiadomości WebSocket dla frontendu (task 4.5)
# ---------------------------------------------------------------------------

def voice_event_to_ws_message(
    cmd: RecognizedCommand,
    rep_target: int | None = None,
    reps_done: int = 0,
) -> dict:
    """
    Task 4.5 – konwertuje komendę głosową na słownik gotowy do wysłania
    przez WebSocket do przeglądarki.

    Args:
        cmd:        Rozpoznana komenda.
        rep_target: Docelowa liczba powtórzeń (jeśli ustawiona przez użytkownika).
        reps_done:  Liczba dotychczasowych powtórzeń.
    """
    base = {
        "type":       "voice_command",
        "event":      cmd.event.value,
        "transcript": cmd.transcript,
    }

    match cmd.event:
        case VoiceEvent.START:
            base["message"] = "Start! Unieś ręce."

        case VoiceEvent.STOP:
            base["message"] = "Trening zakończony na Twoje polecenie."

        case VoiceEvent.HOW_MANY_LEFT:
            if rep_target is not None:
                left = max(rep_target - reps_done, 0)
                base["message"] = f"Zrobiłeś {reps_done} z {rep_target} powtórzeń. Zostało {left}."
            else:
                base["message"] = f"Masz już {reps_done} powtórzeń. Tak trzymaj!"

        case VoiceEvent.PAUSE:
            base["message"] = "Pauza. Odpoczywaj."

        case VoiceEvent.RESUME:
            base["message"] = "Wznawiam. Gotowy?"

        case VoiceEvent.RESET:
            base["message"] = "Resetuję licznik. Zacznij od nowa."

        case VoiceEvent.NEXT_EXERCISE:
            base["message"] = "Przechodzimy do następnego ćwiczenia."

        case VoiceEvent.UNKNOWN:
            base["message"] = f"Nie rozpoznałem komendy: '{cmd.transcript}'"

        case _:
            base["message"] = ""

    return base
