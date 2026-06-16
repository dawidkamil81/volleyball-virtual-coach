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
    const [isCalibrated, setIsCalibrated] = useState(false);
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
    
    // Referencje dla WebSocketu i uśredniania klatek (Smoothing)
    const socketRef = useRef(null);
    const cameraState = useRef({
        front: { buffer: [], lastSendTime: 0 },
        side: { buffer: [], lastSendTime: 0 }
    });

    // Połączenie z WebSocketem
    useEffect(() => {
        const ws = new WebSocket('ws://localhost:8000/ws/trainer');
        socketRef.current = ws;

        ws.onopen = () => {
            setAiMessage('Połączono. Zaczynajmy!');
            setMessageType('info');
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.status) setCurrentPhase(data.status);
            if (data.conditions) setConditions(data.conditions);
            else setConditions([]);
            
            if (data.type === 'feedback' || data.type === 'state_change' || data.type === 'info') {
                setAiMessage(data.message); // TYLKO TEKST, BEZ SYNTEZATORA
                
                if (data.type === 'feedback') {
                    if (data.rep_increment > 0) {
                        setMessageType('success');
                        setRepCount(prev => prev + data.rep_increment);
                    } else {
                        setMessageType('error');
                    }
                } else {
                    setMessageType('info');
                }
            }
        };

        ws.onclose = () => {
            setAiMessage('Rozłączono z serwerem.');
            setMessageType('error');
        };

        return () => ws.close();
    }, []);

    // Pobieranie listy kamer
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

    // Funkcja uśredniająca klatki (SMOOTHING)
    const sendLandmarksToAPI = (landmarks, cameraView) => {
        if (!isCalibrated) return;

        const state = cameraState.current[cameraView];
        const now = Date.now();

        state.buffer.push(landmarks);

        // Wysyłaj uśrednioną paczkę co 100ms
        if (now - state.lastSendTime < 100) return;

        const numFrames = state.buffer.length;
        const averagedLandmarks = [];

        for (let i = 0; i < 33; i++) {
            let sumX = 0, sumY = 0, sumZ = 0, sumVis = 0;
            for (let j = 0; j < numFrames; j++) {
                sumX += state.buffer[j][i].x;
                sumY += state.buffer[j][i].y;
                sumZ += state.buffer[j][i].z;
                sumVis += state.buffer[j][i].visibility;
            }
            averagedLandmarks.push({
                x: sumX / numFrames,
                y: sumY / numFrames,
                z: sumZ / numFrames,
                visibility: sumVis / numFrames
            });
        }

        const payload = {
            camera: cameraView,
            landmarks: averagedLandmarks
        };

        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify(payload));
        }

        state.buffer = [];
        state.lastSendTime = now;
    };

    useMediaPipe(videoFrontRef, canvasFrontRef, frontCameraId, (results) => {
        if (results.poseLandmarks) sendLandmarksToAPI(results.poseLandmarks, 'front');
    });

    useMediaPipe(videoSideRef, canvasSideRef, sideCameraId, (results) => {
        if (results.poseLandmarks) sendLandmarksToAPI(results.poseLandmarks, 'side');
    });

    return (
        <div className="min-h-screen bg-gray-900 text-white flex flex-col p-4 md:p-6 font-sans">
            <header className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div>
                    <h1 className="text-2xl md:text-3xl font-bold text-gray-100 tracking-tight">Trening Siatkarski</h1>
                    <p className="text-gray-400 text-sm mt-1">Analiza z uśrednianiem klatek (Bez mowy AI)</p>
                </div>
                <div className="flex gap-4 bg-gray-800 p-3 rounded-xl border border-gray-700">
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
                <button onClick={() => navigate('/')} className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-xl font-bold">ZAKOŃCZ</button>
            </header>

            <main className="flex-1 flex flex-col lg:flex-row gap-6">
                <section className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="bg-black rounded-3xl relative overflow-hidden border border-blue-500/50 min-h-[400px]">
                        <div className="absolute top-4 left-4 z-10 bg-blue-600/80 px-3 py-1 rounded-lg text-sm font-bold">Front</div>
                        <video ref={videoFrontRef} className="hidden" playsInline></video>
                        <canvas ref={canvasFrontRef} className="absolute inset-0 w-full h-full object-cover z-0" width="640" height="480"></canvas>
                    </div>
                    <div className="bg-black rounded-3xl relative overflow-hidden border border-green-500/50 min-h-[400px]">
                        <div className="absolute top-4 left-4 z-10 bg-green-600/80 px-3 py-1 rounded-lg text-sm font-bold">Bok</div>
                        <video ref={videoSideRef} className="hidden" playsInline></video>
                        <canvas ref={canvasSideRef} className="absolute inset-0 w-full h-full object-cover z-0" width="640" height="480"></canvas>
                        {!isCalibrated && (
                            <div className="absolute inset-0 bg-black/60 z-20 flex flex-col items-center justify-center">
                                <button onClick={() => setIsCalibrated(true)} className="bg-green-600 hover:bg-green-500 px-6 py-2 rounded-full font-bold">START</button>
                            </div>
                        )}
                    </div>
                </section>

                <section className="w-full lg:w-64 flex flex-row lg:flex-col gap-4">
                    <div className="bg-gray-800 rounded-3xl p-4 flex-1 flex flex-col items-center justify-center border border-gray-700">
                        <h2 className="text-gray-400 text-xs uppercase font-bold mb-2">Poprawne Odbicia</h2>
                        <div className="text-4xl font-black text-blue-500">{repCount}</div>
                    </div>
                    <div className="bg-gray-800 rounded-3xl p-4 flex-1 flex flex-col justify-start border border-gray-700">
                        <div className="flex justify-between items-center mb-4 border-b border-gray-700 pb-2">
                            <h2 className="text-gray-400 text-xs uppercase font-bold">AI Trener</h2>
                            <span className="bg-gray-700 text-yellow-400 text-[10px] px-2 py-1 rounded-full font-bold">{currentPhase}</span>
                        </div>
                        <div className="flex-1 flex flex-col items-center justify-center space-y-3">
                            <p className={`text-sm text-center ${messageType === 'error' ? 'text-red-400 font-bold' : messageType === 'success' ? 'text-green-400 font-bold' : 'text-blue-400 font-medium'}`}>
                                {!isCalibrated ? "Czekam na start..." : aiMessage}
                            </p>
                            
                            {/* Wyświetlanie warunków dla danej fazy */}
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