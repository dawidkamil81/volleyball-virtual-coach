import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMediaPipe } from '../hooks/useMediaPipe';
import useSpeech from '../hooks/useSpeech';
import useVoiceCommand from '../hooks/useVoiceCommand';

const Training = () => {
    const navigate = useNavigate();
    const { speak } = useSpeech();
    
    // Nasłuchiwanie na komendę głosową "STOP" - ODKOMENTOWANE I GOTOWE!
    useVoiceCommand(() => {
        console.log("🛑 Wypowiedziano STOP. Zamykam trening!");
        navigate('/');
    });
    
    // Stany dla kamer
    const [devices, setDevices] = useState([]);
    const [frontCameraId, setFrontCameraId] = useState('');
    const [sideCameraId, setSideCameraId] = useState('');

    // Stany treningu
    const [repCount, setRepCount] = useState(0);
    const [isCalibrated, setIsCalibrated] = useState(false);
    
    // Stan wyboru ćwiczenia i UI Trenera
    const [passType, setPassType] = useState('górne');
    const [aiMessage, setAiMessage] = useState('Czekam na połączenie z serwerem...');
    const [currentPhase, setCurrentPhase] = useState('START');
    const [messageType, setMessageType] = useState('info');
    const [conditions, setConditions] = useState([]);

    // Referencje dla DWÓCH kamer
    const videoFrontRef = useRef(null);
    const canvasFrontRef = useRef(null);
    const videoSideRef = useRef(null);
    const canvasSideRef = useRef(null);
    
    // Zapobieganie "jąkaniu się" trenera AI
    const lastSpokenMessage = useRef('');

    // Referencje dla WebSocketu (USUNIĘTY BUFOR, zostaje tylko zegar do szybkiej wysyłki)
    const socketRef = useRef(null);
    const cameraState = useRef({
        front: { lastSendTime: 0 },
        side: { lastSendTime: 0 }
    });

    // 1. Pobieranie listy kamer przy starcie komponentu
    useEffect(() => {
        const getDevices = async () => {
            try {
                await navigator.mediaDevices.getUserMedia({ video: true });
                const allDevices = await navigator.mediaDevices.enumerateDevices();
                const videoInputDevices = allDevices.filter(device => device.kind === 'videoinput');
                
                setDevices(videoInputDevices);
                
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
        // PRAWIDŁOWY ADRES zgodny z FastAPI w main.py
        const ws = new WebSocket('ws://localhost:8000/ws/trainer');

        ws.onopen = () => {
            console.log("🟢 Połączono z lokalnym serwerem API!");
            setAiMessage('Połączono z AI. Wybierz sprzęt i startuj!');
            setMessageType('info');
        };

        ws.onmessage = (event) => {
            try {
                const response = JSON.parse(event.data);

                // 1. Aktualizacja Fazy (tylko jeśli się zmieniła)
                if (response.status) {
                    setCurrentPhase(prev => prev !== response.status ? response.status : prev);
                }

                // 2. Aktualizacja warunków TYLKO jeśli faktycznie się zmieniły (Zabezpieczenie przed klatkowaniem)
                if (response.conditions) {
                    setConditions(prev => {
                        if (JSON.stringify(prev) !== JSON.stringify(response.conditions)) {
                            return response.conditions; 
                        }
                        return prev; 
                    });
                } else {
                    setConditions(prev => prev.length > 0 ? [] : prev);
                }

                // 3. Obsługa wiadomości tekstowych
                if (response.type === 'feedback' || response.type === 'state_change' || response.type === 'info') {
                    setAiMessage(prev => prev !== response.message ? response.message : prev); 
                    
                    // Mowa AI - mówimy tylko o zmianach stanu lub błędach
                    if ((response.type === 'feedback' || response.type === 'state_change') && response.message) {
                        if (response.message !== lastSpokenMessage.current) {
                            speak(response.message);
                            lastSpokenMessage.current = response.message;
                        }
                    }
                    
                    // Kolorowanie komunikatów w UI i dodawanie powtórzeń
                    if (response.type === 'feedback') {
                        if (response.rep_increment > 0) {
                            setMessageType('success');
                            setRepCount(prev => prev + response.rep_increment);
                        } else {
                            setMessageType('error');
                        }
                    } else {
                        setMessageType(prev => prev !== 'info' ? 'info' : prev);
                    }
                }

            } catch (err) {
                console.error("Błąd odczytu danych z serwera:", err);
            }
        };

        ws.onerror = (error) => {
            console.error("🔴 Błąd połączenia z serwerem:", error);
            setAiMessage('Błąd połączenia. Upewnij się, że serwer Python działa.');
            setMessageType('error');
        };

        ws.onclose = () => {
            console.log("⚪ Rozłączono z serwerem.");
            setAiMessage('Rozłączono z serwerem.');
            setMessageType('error');
        };

        socketRef.current = ws;

        return () => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.close();
            }
        };
    }, [speak]);

    // 3. BŁYSKAWICZNA funkcja wysyłająca dane (Zoptymalizowana, bez pętli uśredniających)
    const sendLandmarksToAPI = (landmarks, cameraView) => {
        if (!isCalibrated) return;

        const state = cameraState.current[cameraView];
        const now = Date.now();

        // Limit wysyłania do ok. 10 FPS (co 100ms)
        if (now - state.lastSendTime < 100) return;

        const payload = {
            camera: cameraView,
            exerciseType: passType,
            timestamp: now,
            landmarks: landmarks // Wysyłamy najświeższe punkty bezpośrednio
        };

        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify(payload));
        }

        state.lastSendTime = now;
    };

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
                    <p className="text-gray-400 text-sm mt-1">Analiza ułożenia rąk (Front) i pracy nóg (Bok)</p>
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

                <div className="flex flex-col items-center">
                    <button onClick={() => navigate('/')} className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-xl font-bold w-full">ZAKOŃCZ</button>
                    <span className="text-[10px] text-gray-500 mt-1 uppercase font-bold tracking-wider flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                        Powiedz "STOP"
                    </span>
                </div>
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

                <section className="w-full lg:w-64 flex flex-row lg:flex-col gap-4">
                    <div className="bg-gray-800 rounded-3xl p-4 flex-1 flex flex-col items-center justify-center border border-gray-700 shadow-lg">
                        <h2 className="text-gray-400 text-xs uppercase font-bold mb-2">Poprawne Odbicia</h2>
                        <div className="text-5xl font-black text-blue-500 drop-shadow-[0_0_10px_rgba(59,130,246,0.3)]">{repCount}</div>
                    </div>

                    <div className="bg-gray-800 rounded-3xl p-4 flex-1 flex flex-col justify-start border border-gray-700 shadow-lg">
                        <div className="flex justify-between items-center mb-4 border-b border-gray-700 pb-2">
                            <h2 className="text-gray-400 text-xs uppercase font-bold flex items-center gap-2">
                                <span className={`w-2 h-2 rounded-full ${isCalibrated ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`}></span>
                                AI Trener
                            </h2>
                            <span className="bg-gray-700 text-yellow-400 text-[10px] px-2 py-1 rounded-full font-bold">{currentPhase}</span>
                        </div>
                        
                        <div className="flex-1 flex flex-col items-center justify-center space-y-3">
                            <p className={`text-sm text-center ${messageType === 'error' ? 'text-red-400 font-bold' : messageType === 'success' ? 'text-green-400 font-bold' : 'text-blue-400 font-medium'}`}>
                                {!isCalibrated ? "Czekam na start..." : aiMessage}
                            </p>
                            
                            {/* Wyświetlanie warunków z Pythona */}
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