import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMediaPipe } from '../hooks/useMediaPipe';

const Training = () => {
    const navigate = useNavigate();
    
    // Stany dla kamer
    const [devices, setDevices] = useState([]);
    const [frontCameraId, setFrontCameraId] = useState('');
    const [sideCameraId, setSideCameraId] = useState('');

    // Stany treningu
    const [repCount, setRepCount] = useState(0);
    const [energyLevel, setEnergyLevel] = useState(85);
    const [isCalibrated, setIsCalibrated] = useState(false);
    
    // Stan wyboru ćwiczenia
    const [passType, setPassType] = useState('górne');

    // Referencje dla DWÓCH kamer
    const videoFrontRef = useRef(null);
    const canvasFrontRef = useRef(null);
    const videoSideRef = useRef(null);
    const canvasSideRef = useRef(null);

    // Referencje dla WebSocketu i limitowania zapytań (Throttling)
    const socketRef = useRef(null);
    const lastSendTime = useRef(0);

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
                    if (videoInputDevices.length > 1) {
                        setSideCameraId(videoInputDevices[1].deviceId);
                    }
                }
            } catch (err) {
                console.error("Błąd dostępu do urządzeń:", err);
            }
        };
        getDevices();
    }, []);

    // 2. Łączenie z lokalnym API przez WebSocket
    useEffect(() => {
        // Ustaw adres swojego lokalnego backendu (np. serwera Python)
        const ws = new WebSocket('ws://localhost:8000/api/trening-stream');

        ws.onopen = () => {
            console.log("🟢 Połączono z lokalnym serwerem API!");
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
    }, []);

    // 3. Funkcja wysyłająca dane do serwera API
    const sendLandmarksToAPI = (landmarks, cameraView) => {
        // Nie wysyłaj, jeśli trening się jeszcze nie zaczął (brak kalibracji)
        if (!isCalibrated) return;

        // Limitowanie do około 10 klatek na sekundę (żeby nie zadławić serwera)
        const now = Date.now();
        if (now - lastSendTime.current < 100) return; 
        lastSendTime.current = now;

        const payload = {
            camera: cameraView,         // 'front' albo 'side'
            exerciseType: passType,     // 'górne' albo 'dolne'
            timestamp: now,
            landmarks: landmarks        // Punkty z MediaPipe
        };

        // Wysyłamy paczkę przez WebSocket
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify(payload));
        }
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
                        <select 
                            value={frontCameraId} 
                            onChange={(e) => setFrontCameraId(e.target.value)}
                            className="bg-gray-700 text-white text-sm rounded-lg border-none focus:ring-2 focus:ring-blue-500 max-w-[200px]"
                        >
                            <option value="">Wybierz kamerę...</option>
                            {devices.map(device => (
                                <option key={device.deviceId} value={device.deviceId}>{device.label || `Kamera ${device.deviceId.substring(0,5)}`}</option>
                            ))}
                        </select>
                    </div>
                    
                    {/* Kamera Bok */}
                    <div className="flex flex-col">
                        <label className="text-xs text-green-400 font-bold mb-1 uppercase">Kamera: Bok</label>
                        <select 
                            value={sideCameraId} 
                            onChange={(e) => setSideCameraId(e.target.value)}
                            className="bg-gray-700 text-white text-sm rounded-lg border-none focus:ring-2 focus:ring-green-500 max-w-[200px]"
                        >
                            <option value="">Wybierz kamerę...</option>
                            {devices.map(device => (
                                <option key={device.deviceId} value={device.deviceId}>{device.label || `Kamera ${device.deviceId.substring(0,5)}`}</option>
                            ))}
                        </select>
                    </div>
                </div>

                <button
                    onClick={() => navigate('/')}
                    className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-xl font-bold shadow-lg"
                >
                    ZAKOŃCZ
                </button>
            </header>

            {/* --- GŁÓWNA TREŚĆ --- */}
            <main className="flex-1 flex flex-col lg:flex-row gap-6">
                
                {/* SEKCJA WIDEO (Siatka 2 kamer) */}
                <section className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
                    
                    {/* WIDOK: FRONT */}
                    <div className="bg-black rounded-3xl relative overflow-hidden border border-blue-500/50 shadow-lg min-h-[400px]">
                        <div className="absolute top-4 left-4 z-10 bg-blue-600/80 px-3 py-1 rounded-lg text-sm font-bold uppercase tracking-widest backdrop-blur-sm">Front</div>
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

                    {/* WIDOK: BOK */}
                    <div className="bg-black rounded-3xl relative overflow-hidden border border-green-500/50 shadow-lg min-h-[400px]">
                        <div className="absolute top-4 left-4 z-10 bg-green-600/80 px-3 py-1 rounded-lg text-sm font-bold uppercase tracking-widest backdrop-blur-sm">Bok</div>
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
                                : passType === 'górne' 
                                    ? '"Odbicie górne: Pamiętaj o ułożeniu dłoni w koszyczek nad czołem."' 
                                    : '"Odbicie dolne: Pracuj na ugiętych nogach i złącz ramiona."'}
                        </p>
                    </div>
                </section>
            </main>
        </div>
    );
};

export default Training;