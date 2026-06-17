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

    // Stany treningu
    const [repCount, setRepCount] = useState(0);
    const [isCalibrated, setIsCalibrated] = useState(false);
    
    // Stan wyboru ćwiczenia
    const [passType, setPassType] = useState('górne');
    const [aiMessage, setAiMessage] = useState('Czekam na połączenie z serwerem...');
    const [currentPhase, setCurrentPhase] = useState('START');
    const [messageType, setMessageType] = useState('info');
    const [conditions, setConditions] = useState([]);

    // Stan wiadomości od trenera AI
    //const [aiMessage, setAiMessage] = useState('');

    // Referencje dla DWÓCH kamer
    const videoFrontRef = useRef(null);
    const canvasFrontRef = useRef(null);
    const videoSideRef = useRef(null);
    const canvasSideRef = useRef(null);
    
    //mowienie
    const lastSpokenMessage = useRef('');

    // Referencje dla WebSocketu i uśredniania klatek (Smoothing)
    const socketRef = useRef(null);
    const cameraState = useRef({
        front: { buffer: [], lastSendTime: 0 },
        side: { buffer: [], lastSendTime: 0 }
    });

    // 1. Pobieranie listy kamer przy starcie komponentu
    useEffect(() => {
        const getDevices = async () => {
            try {
                // Wymuszenie zapytania o zgodę
                await navigator.mediaDevices.getUserMedia({ video: true });
                const allDevices = await navigator.mediaDevices.enumerateDevices();
                const videoInputDevices = allDevices.filter(device => device.kind === 'videoinput');
                setDevices(videoInputDevices);
                
                // Ustaw domyślne kamery
                if (videoInputDevices.length > 0) {
                    setFrontCameraId(videoInputDevices[0].deviceId);
                    if (videoInputDevices.length > 1) setSideCameraId(videoInputDevices[1].deviceId);
                }
            } catch (err) {
                console.error("Błąd dostępu do urządzeń:", err);
            }
        };
        getDevices();
    }, []);

    // 2. Łączenie z lokalnym API przez WebSocket i nasłuchiwanie komunikatów
    useEffect(() => {
        // Ustaw adres swojego lokalnego backendu (np. serwera Python)
        const ws = new WebSocket('ws://localhost:8000/api/trening-stream');

        ws.onopen = () => {
            console.log("🟢 Połączono z lokalnym serwerem API!");
        };

        ws.onmessage = (event) => {
            try {
                // Odkodowujemy to, co przysłał Python
                const response = JSON.parse(event.data);

                // Sprawdzamy, czy to jest komunikat głosowy
                if (response.type === 'feedback' && response.text) {
                    if (response.text !== lastSpokenMessage.current) {
                        setAiMessage(response.text); 
                        speak(response.text);        
                        lastSpokenMessage.current = response.text; // Zapisujemy jako ostatnio powiedziane
                    }
                }
                
                // Opcjonalnie: Jeśli serwer przyśle zaktualizowane powtórzenia
                if (response.type === 'stats' && response.reps !== undefined) {
                    setRepCount(response.reps);
                }

            } catch (err) {
                console.error("Błąd odczytu danych z serwera:", err);
            }
        };

        ws.onerror = (error) => {
            console.error("🔴 Błąd połączenia z serwerem:", error);
        };

        ws.onclose = () => {
            console.log("⚪ Rozłączono z serwerem.");
        };

        socketRef.current = ws;

        // Rozłącz się przy wyjściu z ekranu treningu
        return () => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.close();
            }
        };
    }, [speak]); // Dodajemy 'speak' jako zależność

    // 3. Funkcja uśredniająca i wysyłająca dane do API
    const sendLandmarksToAPI = (landmarks, cameraView) => {
        if (!isCalibrated) return;

        const state = cameraState.current[cameraView];
        const now = Date.now();

        // 1. Zbieramy klatkę do bufora (worka)
        state.buffer.push(landmarks);

        // 2. Jeśli nie minęło jeszcze 100ms, przerywamy (tylko zbieramy, nie wysyłamy)
        if (now - state.lastSendTime < 100) return;

        // 3. Jeśli minęło 100ms, wyliczamy ŚREDNIĄ ze wszystkich zebranych klatek
        const numFrames = state.buffer.length;
        const averagedLandmarks = [];

        // Przechodzimy przez wszystkie 33 punkty szkieletu
        for (let i = 0; i < 33; i++) {
            let sumX = 0, sumY = 0, sumZ = 0, sumVis = 0;

            // Sumujemy dany punkt ze wszystkich klatek w buforze
            for (let j = 0; j < numFrames; j++) {
                sumX += state.buffer[j][i].x;
                sumY += state.buffer[j][i].y;
                sumZ += state.buffer[j][i].z;
                sumVis += state.buffer[j][i].visibility;
            }

            // Dzielimy przez ilość klatek (Średnia Arytmetyczna)
            averagedLandmarks.push({
                x: sumX / numFrames,
                y: sumY / numFrames,
                z: sumZ / numFrames,
                visibility: sumVis / numFrames
            });
        }

        // 4. Budujemy paczkę z UŚREDNIONYMI danymi
        const payload = {
            camera: cameraView,
            exerciseType: passType,
            timestamp: now,
            framesAveraged: numFrames, // Dodatkowe info dla serwera z ilu klatek to średnia
            landmarks: averagedLandmarks
        };

        // 5. Wysyłamy przez WebSocket
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify(payload));
        }

        // 6. Resetujemy bufor i zegar dla tej konkretnej kamery, by zacząć zbierać od nowa
        state.buffer = [];
        state.lastSendTime = now;
    };

    // 4. Uruchomienie DWÓCH instancji hooka MediaPipe
    useMediaPipe(videoFrontRef, canvasFrontRef, frontCameraId, (results) => {
        if (results.poseLandmarks) {
            sendLandmarksToAPI(results.poseLandmarks, 'front');
        }
    });

    useMediaPipe(videoSideRef, canvasSideRef, sideCameraId, (results) => {
        if (results.poseLandmarks) {
            sendLandmarksToAPI(results.poseLandmarks, 'side');
        }
    });

    return (
        <div className="min-h-screen bg-gray-900 text-white flex flex-col p-4 md:p-6 font-sans">
            
            {/* --- NAGŁÓWEK --- */}
            <header className="flex flex-col lg:flex-row justify-between items-start lg:items-center mb-6 gap-4">
                <div>
                    <h1 className="text-2xl md:text-3xl font-bold text-gray-100 tracking-tight">Trening Siatkarski</h1>
                    <p className="text-gray-400 text-sm mt-1">Analiza ułożenia rąk (Front) i pracy nóg (Bok)</p>
                </div>

                {/* Panele ustawień (Ćwiczenie i Kamery) */}
                <div className="flex flex-wrap gap-4 bg-gray-800 p-3 rounded-xl border border-gray-700">
                    
                    {/* Wybór ćwiczenia */}
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

                    {/* Kamera Front */}
                    <div className="flex flex-col">
                        <label className="text-xs text-blue-400 font-bold mb-1 uppercase">Kamera: Front</label>
                        <select value={frontCameraId} onChange={(e) => setFrontCameraId(e.target.value)} className="bg-gray-700 text-white text-sm rounded-lg border-none">
                            <option value="">Wybierz kamerę...</option>
                            {devices.map(device => <option key={device.deviceId} value={device.deviceId}>{device.label || `Kamera ${device.deviceId.substring(0,5)}`}</option>)}
                        </select>
                    </div>
                    
                    {/* Kamera Bok */}
                    <div className="flex flex-col">
                        <label className="text-xs text-green-400 font-bold mb-1 uppercase">Kamera: Bok</label>
                        <select value={sideCameraId} onChange={(e) => setSideCameraId(e.target.value)} className="bg-gray-700 text-white text-sm rounded-lg border-none">
                            <option value="">Wybierz kamerę...</option>
                            {devices.map(device => <option key={device.deviceId} value={device.deviceId}>{device.label || `Kamera ${device.deviceId.substring(0,5)}`}</option>)}
                        </select>
                    </div>
                </div>
                <button onClick={() => navigate('/')} className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-xl font-bold">ZAKOŃCZ</button>
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
                                    onClick={() => setIsCalibrated(true)}
                                    className="bg-green-600 hover:bg-green-500 px-6 py-3 rounded-full font-bold shadow-[0_0_15px_rgba(34,197,94,0.4)] transition-transform hover:scale-105"
                                >
                                    SKALIBRUJ I START
                                </button>
                            </div>
                        )}
                    </div>
                </section>

                {/* SEKCJA STATYSTYK BOCZNYCH */}
                <section className="w-full lg:w-64 flex flex-row lg:flex-col gap-4">
                    <div className="bg-gray-800 rounded-3xl p-4 flex-1 flex flex-col items-center justify-center border border-gray-700 shadow-lg">
                        <h2 className="text-gray-400 text-xs uppercase font-bold mb-2">Poprawne Odbicia</h2>
                        <div className="text-5xl font-black text-blue-500 drop-shadow-[0_0_10px_rgba(59,130,246,0.3)]">{repCount}</div>
                    </div>

                    <div className="bg-gray-800 rounded-3xl p-6 flex-1 flex flex-col justify-center border border-gray-700 shadow-lg relative overflow-hidden">
                        <h2 className="text-gray-400 text-xs uppercase font-bold mb-3 flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full ${isCalibrated ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`}></span>
                            AI Trener
                        </h2>
                        <p className="text-sm text-gray-200 italic leading-relaxed">
                            {!isCalibrated 
                                ? "Czekam na kalibrację..." 
                                : aiMessage || "Rozpocznij trening, analizuję postawę..."}
                        </p>
                    </div>
                </section>
            </main>
        </div>
    );
};

export default Training;