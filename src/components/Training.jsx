import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMediaPipe } from '../hooks/useMediaPipe';
import useSpeech from '../hooks/useSpeech';

const Training = () => {
    const navigate = useNavigate();
    const { speak } = useSpeech();
    
    // Stany dla kamer
    const [devices, setDevices] = useState([]);
    const [frontCameraId, setFrontCameraId] = useState('');
    const [sideCameraId, setSideCameraId] = useState('');

    const [repCount, setRepCount] = useState(0);
    const [isCalibrated, setIsCalibrated] = useState(false);
    const [passType, setPassType] = useState('górne');
    const [aiMessage, setAiMessage] = useState('Czekam na połączenie z serwerem...');
    const [currentPhase, setCurrentPhase] = useState('START');
    const [messageType, setMessageType] = useState('info');
    const [conditions, setConditions] = useState([]);

    // NOWY STAN: Obsługa pauzy wywołanej głosowo przez serwer
    const [isVoicePaused, setIsVoicePaused] = useState(false);

    // Referencje dla DWÓCH kamer
    const videoFrontRef = useRef(null);
    const canvasFrontRef = useRef(null);
    const videoSideRef = useRef(null);
    const canvasSideRef = useRef(null);

    // Zapobieganie "jąkaniu się" trenera AI
    const lastSpokenMessage = useRef('');

    // Referencje dla WebSocketu
    const socketRef = useRef(null);
    const cameraState = useRef({
        front: { lastSendTime: 0 },
        side: { lastSendTime: 0 }
    });

    // --- USUNIĘTO: useVoiceCommand(onStopCommand) ---
    // Nie dublujemy nasłuchu z przeglądarki. Całość idzie przez Vosk na backendzie!

    // 1. Wykrywanie urządzeń wideo (Twój oryginalny kod)
    useEffect(() => {
        const getDevices = async () => {
            try {
                const allDevices = await navigator.mediaDevices.enumerateDevices();
                const videoDevices = allDevices.filter(d => d.kind === 'videoinput');
                setDevices(videoDevices);

                if (videoDevices.length > 0) setFrontCameraId(videoDevices[0].deviceId);
                if (videoDevices.length > 1) setSideCameraId(videoDevices[1].deviceId);
                else if (videoDevices.length > 0) setSideCameraId(videoDevices[0].deviceId);
            } catch (err) {
                console.error("Błąd listowania kamer:", err);
            }
        };
        getDevices();
    }, []);

    // 2. Obsługa WebSocket & Logika Voice Commands z serwera
    useEffect(() => {
        const ws = new WebSocket("ws://localhost:8000/ws/trainer");
        socketRef.current = ws;

        ws.onopen = () => {
            console.log("WebSocket połączony z backendem trenera.");
            setAiMessage("Połączono. Serwer gotowy, nasłuchuję komend głosowych...");
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            // A. OBSŁUGA KOMEND GŁOSOWYCH (Voice Events z Voska)
            if (data.type === "voice_command") {
                console.log("Otrzymano komendę głosową:", data);

                // Odczytaj komunikat lektorem (np. "Pauza. Odpoczywaj.", "Resetuję licznik.")
                if (data.message) {
                    speak(data.message);
                    setAiMessage(data.message);
                }

                // Reakcja wizualna na zdarzenia systemowe
                switch (data.event) {
                    case "voice_pause":
                        setIsVoicePaused(true);
                        setMessageType("info");
                        break;
                    case "voice_resume":
                        setIsVoicePaused(false);
                        break;
                    case "voice_reset":
                        setRepCount(0);
                        setConditions([]);
                        setCurrentPhase("START");
                        setMessageType("info");
                        break;
                    case "voice_stop":
                        // Rozłączenie nastąpi automatycznie przy opuszczeniu strony
                        // Backend w bloku finally zapisze bazę danych
                        navigate('/stats');
                        break;
                    default:
                        break;
                }
                return; // Przerywamy przetwarzanie, to nie była klatka wideo
            }

            // B. STANDARDOWE PRZETWARZANIE KLATEK WIDEO (Coach Engine Feedback)
            if (data.status) {
                setCurrentPhase(data.status);

                if (data.message && data.message !== lastSpokenMessage.current) {
                    setAiMessage(data.message);
                    speak(data.message);
                    lastSpokenMessage.current = data.message;
                }

                if (data.type === 'feedback') {
                    setMessageType(data.rep_increment > 0 ? 'success' : 'error');
                } else if (data.type === 'state_change') {
                    setMessageType('info');
                }

                if (data.session) {
                    setRepCount(data.session.total_reps);
                }

                if (data.conditions) {
                    setConditions(data.conditions);
                    setIsCalibrated(true);
                }
            }
        };

        ws.onclose = () => {
            console.log("WebSocket zamknięty.");
        };

        return () => {
            if (ws) ws.close();
        };
    }, [navigate, speak]);

    // 3. Callbacki MediaPipe dla obu kamer (Zoptymalizowane)
    const handleFrontResults = (results) => {
        if (!results.poseLandmarks || !socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) return;
        if (isVoicePaused) return; // Ignoruj klatki, jeśli daliśmy "pauzę" głosową

        const now = performance.now();
        if (now - cameraState.current.front.lastSendTime < 100) return; // max 10fps
        cameraState.current.front.lastSendTime = now;

        const payload = {
            camera: "front",
            landmarks: results.poseLandmarks
        };
        socketRef.current.send(JSON.stringify(payload));
    };

    const handleSideResults = (results) => {
        if (!results.poseLandmarks || !socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) return;
        if (isVoicePaused) return; // Ignoruj klatki, jeśli daliśmy "pauzę" głosową

        const now = performance.now();
        if (now - cameraState.current.side.lastSendTime < 100) return; // max 10fps
        cameraState.current.side.lastSendTime = now;

        const payload = {
            camera: "side",
            landmarks: results.poseLandmarks
        };
        socketRef.current.send(JSON.stringify(payload));
    };

    // Aktywacja hooków MediaPipe
    useMediaPipe(videoFrontRef, canvasFrontRef, frontCameraId, handleFrontResults);
    useMediaPipe(videoSideRef, canvasSideRef, sideCameraId, handleSideResults);

    // Ręczne przerwanie treningu kliknięciem
    const handleStopClick = () => {
        if (socketRef.current) socketRef.current.close(); // Zamknięcie WebSocket wywoła finally w Pythonie i zapisze DB
        navigate('/stats');
    };

    return (
        <div className="min-h-screen bg-gray-900 text-gray-100 font-sans flex flex-col">
            {/* Pasek nawigacyjny */}
            <header className="bg-gray-800 border-b border-gray-700 px-6 py-4 flex items-center justify-between shadow-lg">
                <div className="flex items-center space-x-3">
                    <span className="text-2xl">🏐</span>
                    <h1 className="text-xl font-black tracking-tight text-white uppercase">
                        Trener AI <span className="text-blue-500 text-sm font-normal normal-case">v0.1</span>
                    </h1>
                </div>
                <button
                    onClick={handleStopClick}
                    className="bg-red-600 hover:bg-red-500 text-white px-5 py-2 rounded-xl font-bold text-sm tracking-wide transition-all shadow-md active:scale-95"
                >
                    ZAKOŃCZ TRENING (STOP)
                </button>
            </header>

            {/* Główny kontener */}
            <main className="flex-1 p-6 grid grid-cols-1 xl:grid-cols-4 gap-6 overflow-hidden">
                {/* Lewa kolumna: Kamery (3/4 szerokości na dużych ekranach) */}
                <section className="xl:col-span-3 grid grid-cols-1 md:grid-cols-2 gap-6 h-full">
                    {/* Kamera Frontowa */}
                    <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden relative shadow-md flex flex-col">
                        <div className="p-3 bg-gray-750 border-b border-gray-700 flex justify-between items-center">
                            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">Kamera Frontowa</span>
                            <select
                                value={frontCameraId}
                                onChange={(e) => setFrontCameraId(e.target.value)}
                                className="bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-gray-300 focus:outline-none focus:border-blue-500"
                            >
                                {devices.map(d => <option key={d.deviceId} value={d.deviceId}>{d.label || `Kamera ${d.deviceId.slice(0,5)}`}</option>)}
                            </select>
                        </div>
                        <div className="flex-1 bg-black relative flex items-center justify-center min-h-[300px]">
                            <video ref={videoFrontRef} className="absolute inset-0 w-full h-full object-cover opacity-0 pointer-events-none" playsInline muted />
                            <canvas ref={canvasFrontRef} className="absolute inset-0 w-full h-full object-contain" width={640} height={480} />
                        </div>
                    </div>

                    {/* Kamera Boczna */}
                    <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden relative shadow-md flex flex-col">
                        <div className="p-3 bg-gray-750 border-b border-gray-700 flex justify-between items-center">
                            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">Kamera Boczna</span>
                            <select
                                value={sideCameraId}
                                onChange={(e) => setSideCameraId(e.target.value)}
                                className="bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-gray-300 focus:outline-none focus:border-blue-500"
                            >
                                {devices.map(d => <option key={d.deviceId} value={d.deviceId}>{d.label || `Kamera ${d.deviceId.slice(0,5)}`}</option>)}
                            </select>
                        </div>
                        <div className="flex-1 bg-black relative flex items-center justify-center min-h-[300px]">
                            <video ref={videoSideRef} className="absolute inset-0 w-full h-full object-cover opacity-0 pointer-events-none" playsInline muted />
                            <canvas ref={canvasSideRef} className="absolute inset-0 w-full h-full object-contain" width={640} height={480} />
                        </div>
                    </div>
                </section>

                {/* Prawa kolumna: Panel AI & Licznik */}
                <section className="flex flex-col gap-6 h-full">
                    {/* Licznik powtórzeń */}
                    <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-3xl p-6 shadow-lg text-center relative overflow-hidden flex flex-col justify-center items-center py-8">
                        <div className="absolute top-0 right-0 p-6 opacity-10 text-7xl font-black select-none">REPS</div>
                        <h2 className="text-xs font-bold uppercase tracking-widest text-blue-200 mb-1">Poprawne Powtórzenia</h2>
                        <p className="text-7xl font-black text-white tracking-tight">{repCount}</p>
                        <span className="mt-2 inline-block bg-blue-500/3xl text-[10px] font-bold px-3 py-1 bg-blue-900/40 rounded-full text-blue-100 uppercase tracking-wider">
                            Tryb: Odbicie {passType}
                        </span>
                    </div>

                    {/* Status pętli maszyny stanów / Głosów */}
                    <div className="bg-gray-800 rounded-2xl border border-gray-700 p-5 shadow-md flex-1 flex flex-col justify-between">
                        <div>
                            <div className="flex justify-between items-center mb-4">
                                <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400">Analiza na żywo</h2>
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                    isVoicePaused ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                                }`}>
                                    {isVoicePaused ? "PAUZA GŁOSOWA" : currentPhase}
                                </span>
                            </div>

                            <p className={`text-sm text-center ${messageType === 'error' ? 'text-red-400 font-bold' : messageType === 'success' ? 'text-green-400 font-bold' : 'text-blue-400 font-medium'}`}>
                                {!isCalibrated ? "Czekam na start..." : aiMessage}
                            </p>

                            {conditions.length > 0 && !isVoicePaused && (
    <div className="w-full mt-2 bg-gray-900 rounded-lg p-3 border border-gray-700">
        <h3 className="text-[10px] text-gray-500 uppercase font-bold mb-2 tracking-wider">Warunki fazy:</h3>
        <ul className="space-y-1">
            {conditions.map((cond, idx) => (
                <li key={idx} className="flex items-center text-xs">
                    {cond.met ? <span className="text-green-500 mr-2">✔</span> : <span className="text-red-500 mr-2">✖</span>}
                    <span className={cond.met ? "text-gray-300" : "text-gray-500"}>{cond.name}</span>
                </li>
            ))}
        </ul>
    </div>
)}
                        </div>

                        {/* Wskaźnik nasłuchu głosowego */}
                        <div className="mt-4 pt-4 border-t border-gray-700 flex items-center justify-center space-x-2 text-xs text-gray-400">
                            <span className={`w-2 h-2 rounded-full ${isVoicePaused ? 'bg-amber-500 animate-pulse' : 'bg-green-500 animate-ping'}`} />
                            <span>Vosk STT Backend Aktywny (Powiedz "Stop" lub "Pauza")</span>
                        </div>
                    </div>
                </section>
            </main>
        </div>
    );
};

export default Training;