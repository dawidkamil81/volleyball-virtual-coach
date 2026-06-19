import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMediaPipe } from '../hooks/useMediaPipe';
import useSpeech from '../hooks/useSpeech';
import useVoiceCommand from '../hooks/useVoiceCommand';

const Training = () => {
    const navigate = useNavigate();
    const { speak } = useSpeech();
    
    // Stany dla konfiguracji sprzętowej kamer przechwytujących obraz
    const [devices, setDevices] = useState([]);
    const [frontCameraId, setFrontCameraId] = useState('');
    const [sideCameraId, setSideCameraId] = useState('');

    // Stany przechowujące metryki zliczane na bieżąco przez silnik decyzyjny AI
    const [repCount, setRepCount] = useState(0);
    const [isCalibrated, setIsCalibrated] = useState(false);
    const [passType, setPassType] = useState('górne');
    const [aiMessage, setAiMessage] = useState('Czekam na połączenie z serwerem...');
    const [currentPhase, setCurrentPhase] = useState('START');
    const [messageType, setMessageType] = useState('info');
    const [conditions, setConditions] = useState([]);

    // --- NOWE STANY DO BAZY DANYCH ---
    // Statystyki sesji niezbędne do zapisania ostatecznego podsumowania treningu
    const [totalAttempts, setTotalAttempts] = useState(0);
    const [trainingStartTime, setTrainingStartTime] = useState(null);

    // Referencje React HTML5 dla strumieni wideo z obu podłączonych urządzeń oraz płócien rysujących szkielet
    const videoFrontRef = useRef(null);
    const canvasFrontRef = useRef(null);
    const videoSideRef = useRef(null);
    const canvasSideRef = useRef(null);

    // Zapobieganie wielokrotnemu wywołaniu procedury zapisu sesji w bazie
    const isSavingRef = useRef(false);

    // Pobranie listy dostępnych urządzeń wideo (kamery internetowe USB/wbudowane) po załadowaniu okna
    useEffect(() => {
        navigator.mediaDevices.enumerateDevices()
            .then(deviceInfos => {
                const videoDevices = deviceInfos.filter(d => d.kind === 'videoinput');
                setDevices(videoDevices);
                // Automatyczne mapowanie pierwszych dwóch znalezionych kamer
                if (videoDevices.length >= 1) setFrontCameraId(videoDevices[0].deviceId);
                if (videoDevices.length >= 2) setSideCameraId(videoDevices[1].deviceId);
            })
            .catch(err => console.error("Błąd listowania kamer:", err));

        // Ustawienie znacznika czasu rozpoczęcia bieżącej sesji treningowej
        setTrainingStartTime(new Date().toISOString());
    }, []);

    // Definicja funkcji typu callback przetwarzającej wiadomości zwrotne odbierane z backendowego WebSocketu
    const onVoiceFeedback = (data) => {
        if (!data) return;

        // Aktualizacja stanu fazy ruchu oraz wiadomości na ekranie
        if (data.status) setCurrentPhase(data.status);
        if (data.message) setAiMessage(data.message);
        if (data.type) setMessageType(data.type);
        if (data.conditions) setConditions(data.conditions);

        // Obsługa komunikatów dźwiękowych (cooldown kontrolowany jest przez backend)
        if (data.type === 'feedback' && data.message) {
            speak(data.message);
        }

        // Rejestrowanie prób oraz przyrostu poprawnie wykonanych powtórzeń (Repetition Counter)
        if (data.status === 'RESET' && data.conditions) {
            setTotalAttempts(prev => prev + 1);
            if (data.rep_increment > 0) {
                setRepCount(prev => prev + data.rep_increment);
            }
        }
    };

    // Custom hook integrujący MediaPipe (detekcja punktów ciała) z WebSocketem przesyłającym dane w czasie rzeczywistym
    const { isConnected, errorMsg } = useMediaPipe(
        frontCameraId,
        sideCameraId,
        videoFrontRef,
        canvasFrontRef,
        videoSideRef,
        canvasSideRef,
        onVoiceFeedback
    );

    // Funkcja wywoływana przy chęci zakończenia i zapisu treningu przez użytkownika
    async function handleStopTraining() {
        if (!trainingStartTime) {
            navigate('/');
            return;
        }
        if (isSavingRef.current) return;
        isSavingRef.current = true;

        const endTime = new Date().toISOString();
        const durationSec = trainingStartTime ? Math.floor((new Date() - new Date(trainingStartTime)) / 1000) : 0;

        // Obliczanie procentowej celności (zapobieganie dzieleniu przez zero)
        const accuracy = totalAttempts > 0 ? Math.round((repCount / totalAttempts) * 100) : 0;

        const summaryPayload = {
            training_type: `Odbicia ${passType}`,
            start_time: trainingStartTime || endTime,
            end_time: endTime,
            duration: durationSec,
            successful_reps: repCount,
            total_attempts: totalAttempts,
            overall_accuracy: accuracy
        };

        try {
            // Przesłanie paczki podsumowującej metodą POST do API bazodanowego
            const res = await fetch('http://localhost:8000/api/training/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(summaryPayload)
            });
            const data = await res.json();
            console.log("Zapisano trening:", data);
        } catch (e) {
            console.error("Błąd podczas zapisu treningu:", e);
        } finally {
            // Bezwarunkowe odesłanie użytkownika do pulpitu głównego po zakończeniu operacji
            navigate('/');
        }
    };

    // Integracja rozpoznawania komend głosowych użytkownika (np. słowo "stop" kończy sesję)
    useVoiceCommand({
        'stop': handleStopTraining,
        'zakończ': handleStopTraining,
    });

    // 4. Uruchomienie DWÓCH instancji hooka MediaPipe
    useMediaPipe(videoFrontRef, canvasFrontRef, frontCameraId, (results) => {
        if (results.poseLandmarks) sendLandmarksToAPI(results.poseLandmarks, 'front');
    });

    useMediaPipe(videoSideRef, canvasSideRef, sideCameraId, (results) => {
        if (results.poseLandmarks) sendLandmarksToAPI(results.poseLandmarks, 'side');
    });

    return (
        <div className="min-h-screen bg-gray-900 text-white flex flex-col p-4 md:p-6 font-sans">

            {/* --- NAGŁÓWEK --- */}
            <header className="flex flex-col lg:flex-row justify-between items-start lg:items-center mb-6 gap-4">
                <div>
                    <h1 className="text-2xl md:text-3xl font-bold text-gray-100 tracking-tight">Trening Siatkarski</h1>
                    <p className="text-gray-400 text-sm mt-1">Zapis statystyk do Bazy Danych</p>
                </div>

                <div className="flex flex-wrap gap-4 bg-gray-800 p-3 rounded-xl border border-gray-700">
                    <div className="flex flex-col border-r border-gray-600 pr-4">
                        <label className="text-xs text-purple-400 font-bold mb-1 uppercase">Ćwiczenie</label>
                        <select
                            value={passType}
                            onChange={(e) => setPassType(e.target.value)}
                            className="bg-gray-700 text-white text-sm rounded-lg border-none focus:ring-2 focus:ring-purple-500 max-w-[150px]"
                        >
                            <option value="górne">Odbicie Górne</option>
                            <option value="dolne">Odbicie Dolne</option>
                        </select>
                    </div>

                    <div className="flex flex-col">
                        <label className="text-xs text-blue-400 font-bold mb-1 uppercase">Kamera: Front</label>
                        <select value={frontCameraId} onChange={(e) => setFrontCameraId(e.target.value)} className="bg-gray-700 text-white text-sm rounded-lg border-none">
                            <option value="">Wybierz kamerę...</option>
                            {devices.map(device => <option key={device.deviceId} value={device.deviceId}>{device.label || `Kamera ${device.deviceId.substring(0,5)}`}</option>)}
                        </select>
                    </div>

                    <div className="flex flex-col">
                        <label className="text-xs text-green-400 font-bold mb-1 uppercase">Kamera: Bok</label>
                        <select value={sideCameraId} onChange={(e) => setSideCameraId(e.target.value)} className="bg-gray-700 text-white text-sm rounded-lg border-none">
                            <option value="">Wybierz kamerę...</option>
                            {devices.map(device => <option key={device.deviceId} value={device.deviceId}>{device.label || `Kamera ${device.deviceId.substring(0,5)}`}</option>)}
                        </select>
                    </div>
                </div>

                {/* ZMIANA: Przycisk Zakończ wywołuje teraz zapis do API */}
                <button onClick={handleStopTraining} className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-xl font-bold">ZAKOŃCZ</button>
            </header>

            {/* --- GŁÓWNA TREŚĆ --- */}
            <main className="flex-1 flex flex-col lg:flex-row gap-6">
                <section className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="bg-black rounded-3xl relative overflow-hidden border border-blue-500/50 min-h-[400px]">
                        <div className="absolute top-4 left-4 z-10 bg-blue-600/80 px-3 py-1 rounded-lg text-sm font-bold">Front</div>
                        <video ref={videoFrontRef} className="hidden" playsInline></video>
                        <canvas ref={canvasFrontRef} className="absolute inset-0 w-full h-full object-cover z-0" width="640" height="480"></canvas>

                        {!isCalibrated && (
                            <div className="absolute inset-0 bg-black/60 z-20 flex items-center justify-center">
                                <p className="text-blue-400 font-bold text-center px-4">
                                    Wybierz sprzęt i ustaw się przodem do wybranej kamery.
                                </p>
                            </div>
                        )}
                    </div>
                    <div className="bg-black rounded-3xl relative overflow-hidden border border-green-500/50 min-h-[400px]">
                        <div className="absolute top-4 left-4 z-10 bg-green-600/80 px-3 py-1 rounded-lg text-sm font-bold">Bok</div>
                        <video ref={videoSideRef} className="hidden" playsInline></video>
                        <canvas ref={canvasSideRef} className="absolute inset-0 w-full h-full object-cover z-0" width="640" height="480"></canvas>
                        {!isCalibrated && (
                            <div className="absolute inset-0 bg-black/60 z-20 flex flex-col items-center justify-center p-4 text-center">
                                <p className="text-green-400 font-bold mb-4">Ustaw się bokiem do kamery, aby analizować postawę.</p>
                                <button
                                    onClick={() => {
                                        setIsCalibrated(true);
                                        setTrainingStartTime(new Date()); // START ZEGARA TRENINGOWEGO
                                    }}
                                    className="bg-green-600 hover:bg-green-500 px-6 py-3 rounded-full font-bold shadow-[0_0_15px_rgba(34,197,94,0.4)] transition-transform hover:scale-105"
                                >
                                    SKALIBRUJ I START
                                </button>
                            </div>
                        )}
                    </div>
                </section>

                <section className="w-full lg:w-64 flex flex-row lg:flex-col gap-4">
                    <div className="bg-gray-800 rounded-3xl p-4 flex-1 flex flex-col items-center justify-center border border-gray-700 shadow-lg">
                        <h2 className="text-gray-400 text-xs uppercase font-bold mb-2">Poprawne Odbicia</h2>
                        {/* ZMIANA: Pokazujemy liczbę poprawnych do ilości wszystkich prób */}
                        <div className="text-5xl font-black text-blue-500 drop-shadow-[0_0_10px_rgba(59,130,246,0.3)]">
                            {repCount} <span className="text-xl text-gray-500">/ {totalAttempts}</span>
                        </div>
                    </div>

                    <div className="bg-gray-800 rounded-3xl p-6 flex-1 flex flex-col justify-start border border-gray-700 shadow-lg relative overflow-hidden">
                        <div className="flex justify-between items-center mb-4 border-b border-gray-700 pb-2">
                            <h2 className="text-gray-400 text-xs uppercase font-bold flex items-center gap-2">
                                <span className={`w-2 h-2 rounded-full ${isCalibrated ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`}></span>
                                AI Trener
                            </h2>
                            <span className="bg-gray-700 text-yellow-400 text-[10px] px-2 py-1 rounded-full font-bold">{currentPhase}</span>
                        </div>

                        <div className="flex-1 flex flex-col items-center justify-center space-y-3">
                            <p className={`text-sm text-center ${messageType === 'error' ? 'text-red-400 font-bold' : messageType === 'success' ? 'text-green-400 font-bold' : 'text-blue-400 font-medium'}`}>
                                {!isCalibrated
                                    ? "Czekam na kalibrację..."
                                    : aiMessage || "Rozpocznij trening, analizuję postawę..."}
                            </p>

                            {/* UI Ptaszków i Krzyżyków przesyłanych z Pythona */}
                            {conditions.length > 0 && (
                                <div className="w-full mt-2 bg-gray-900 rounded-lg p-3 border border-gray-700">
                                    <h3 className="text-[10px] text-gray-500 uppercase font-bold mb-2 tracking-wider">Warunki fazy:</h3>
                                    <ul className="space-y-1">
                                        {conditions.map((cond, idx) => (
                                            <li key={idx} className="flex items-center text-xs">
                                                {cond.met ? (
                                                    <span className="text-green-500 mr-2">✔</span>
                                                ) : (
                                                    <span className="text-red-500 mr-2">✖</span>
                                                )}
                                                <span className={cond.met ? "text-gray-300" : "text-gray-500"}>
                                                    {cond.name}
                                                </span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    </div>
                </section>
            </main>
        </div>
    );
};

export default Training;