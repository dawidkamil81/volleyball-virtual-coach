import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMediaPipe } from '../hooks/useMediaPipe';

const Training = () => {
    const navigate = useNavigate();
    
    // Stany dla kamer
    const [devices, setDevices] = useState([]);
    const [frontCameraId, setFrontCameraId] = useState('');
    const [sideCameraId, setSideCameraId] = useState('');

    const [repCount, setRepCount] = useState(0);
    const [energyLevel, setEnergyLevel] = useState(85);
    const [isCalibrated, setIsCalibrated] = useState(false);
    const [passType, setPassType] = useState('górne');
    const [aiMessage, setAiMessage] = useState('Czekam na połączenie z serwerem...');

    // Referencje dla DWÓCH kamer
    const videoFrontRef = useRef(null);
    const canvasFrontRef = useRef(null);
    const videoSideRef = useRef(null);
    const canvasSideRef = useRef(null);
    
    // Referencja do WebSocketa
    const socketRef = useRef(null);

    // Połączenie z WebSocketem
    useEffect(() => {
        const ws = new WebSocket('ws://localhost:8000/ws/trainer');
        socketRef.current = ws;

        ws.onopen = () => {
            setAiMessage('Połączono. Zaczynajmy!');
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'feedback' || data.type === 'state_change') {
                setAiMessage(data.message);
                if (data.rep_increment > 0) {
                    setRepCount(prev => prev + data.rep_increment);
                }
            }
        };

        ws.onclose = () => {
            setAiMessage('Rozłączono z serwerem.');
        };

        return () => {
            ws.close();
        };
    }, []);

    // Pobieranie listy kamer przy starcie komponentu
    useEffect(() => {
        const getDevices = async () => {
            try {
                // Wymuszenie zapytania o zgodę (inaczej przeglądarka ukryje nazwy kamer)
                await navigator.mediaDevices.getUserMedia({ video: true });
                const allDevices = await navigator.mediaDevices.enumerateDevices();
                const videoInputDevices = allDevices.filter(device => device.kind === 'videoinput');
                
                setDevices(videoInputDevices);
                
                // Ustaw domyślne kamery, jeśli jakieś znaleziono
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

    // Uruchomienie DWÓCH instancji hooka z różnymi ID kamer
    useMediaPipe(videoFrontRef, canvasFrontRef, frontCameraId, (results) => {
        if (results.poseLandmarks && socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify({
                camera: "front",
                landmarks: results.poseLandmarks
            }));
        }
    });

    useMediaPipe(videoSideRef, canvasSideRef, sideCameraId, (results) => {
        if (results.poseLandmarks && socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify({
                camera: "side",
                landmarks: results.poseLandmarks
            }));
        }
    });

    return (
        <div className="min-h-screen bg-gray-900 text-white flex flex-col p-4 md:p-6 font-sans">
            
            <header className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div>
                    <h1 className="text-2xl md:text-3xl font-bold text-gray-100 tracking-tight">Trening Siatkarski (Wielokamerowy)</h1>
                    <p className="text-gray-400 text-sm mt-1">Analiza ułożenia rąk (Front) i pracy nóg (Bok)</p>
                </div>

                {/* Panele wyboru kamer */}
                <div className="flex gap-4 bg-gray-800 p-3 rounded-xl border border-gray-700">
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
                                <p className="text-blue-400 font-bold">Ustaw się twarzą do kamery</p>
                            </div>
                        )}
                    </div>

                    {/* WIDOK: BOK */}
                    <div className="bg-black rounded-3xl relative overflow-hidden border border-green-500/50 shadow-lg min-h-[400px]">
                        <div className="absolute top-4 left-4 z-10 bg-green-600/80 px-3 py-1 rounded-lg text-sm font-bold uppercase tracking-widest backdrop-blur-sm">Bok</div>
                        <video ref={videoSideRef} className="hidden" playsInline></video>
                        <canvas ref={canvasSideRef} className="absolute inset-0 w-full h-full object-cover z-0" width="640" height="480"></canvas>

                        {!isCalibrated && (
                            <div className="absolute inset-0 bg-black/60 z-20 flex flex-col items-center justify-center">
                                <p className="text-green-400 font-bold mb-4">Ustaw się bokiem do kamery</p>
                                <button
                                    onClick={() => setIsCalibrated(true)}
                                    className="bg-green-600 hover:bg-green-500 px-6 py-2 rounded-full font-bold shadow-lg"
                                >
                                    SKALIBRUJ I START
                                </button>
                            </div>
                        )}
                    </div>
                </section>

                {/* SEKCJA STATYSTYK BOCZNYCH (Zwężona dla zrobienia miejsca na kamery) */}
                <section className="w-full lg:w-64 flex flex-row lg:flex-col gap-4">
                    <div className="bg-gray-800 rounded-3xl p-4 flex-1 flex flex-col items-center justify-center border border-gray-700">
                        <h2 className="text-gray-400 text-xs uppercase font-bold mb-2">Poprawne Odbicia</h2>
                        <div className="text-4xl font-black text-blue-500">{repCount}</div>
                    </div>

                    <div className="bg-gray-800 rounded-3xl p-4 flex-1 flex flex-col justify-center border border-gray-700">
                        <h2 className="text-gray-400 text-xs uppercase font-bold mb-2 text-center">AI Trener</h2>
                        <p className="text-sm text-gray-300 italic text-center">
                            {!isCalibrated ? "Czekam na kalibrację..." : aiMessage}
                        </p>
                    </div>
                </section>
            </main>
        </div>
    );
};

export default Training;