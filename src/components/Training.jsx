import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMediaPipe } from '../hooks/useMediaPipe';
import useSpeech from '../hooks/useSpeech';

const Training = () => {
    const navigate = useNavigate();
    const { speak } = useSpeech();
    
    const [hasPermissions, setHasPermissions] = useState(false);
    const [devices, setDevices] = useState([]);
    const [frontCameraId, setFrontCameraId] = useState('');
    const [sideCameraId, setSideCameraId] = useState('');

    const [repCount, setRepCount] = useState(0);
    const [isCalibrated, setIsCalibrated] = useState(false);
    const [passType, setPassType] = useState('górne');
    const [aiMessage, setAiMessage] = useState('Czekam na uprawnienia i połączenie...');
    const [currentPhase, setCurrentPhase] = useState('START');
    const [messageType, setMessageType] = useState('info');
    const [conditions, setConditions] = useState([]);
    const [isVoicePaused, setIsVoicePaused] = useState(false);

    const videoFrontRef = useRef(null);
    const canvasFrontRef = useRef(null);
    const videoSideRef = useRef(null);
    const canvasSideRef = useRef(null);
    const socketRef = useRef(null);

    const lastSpokenMessage = useRef('');
    const cameraState = useRef({
        front: { lastSendTime: 0 },
        side: { lastSendTime: 0 }
    });

    useEffect(() => {
        const requestInitialPermissions = async () => {
            try {
                const testStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
                testStream.getTracks().forEach(track => track.stop());
                setHasPermissions(true);
            } catch (err) {
                console.error("Odrzucono uprawnienia:", err);
                setAiMessage("Brak uprawnień do kamery lub mikrofonu!");
            }
        };
        requestInitialPermissions();
    }, []);

    useEffect(() => {
        if (!hasPermissions) return;
        const getDevices = async () => {
            try {
                const allDevices = await navigator.mediaDevices.enumerateDevices();
                const videoDevices = allDevices.filter(d => d.kind === 'videoinput');
                setDevices(videoDevices);

                if (videoDevices.length > 0) {
                    setFrontCameraId(prev => prev || videoDevices[0].deviceId);
                    setSideCameraId(prev => prev || (videoDevices[1] ? videoDevices[1].deviceId : videoDevices[0].deviceId));
                }
            } catch (err) {
                console.error("Błąd ładowania urządzeń wideo:", err);
            }
        };
        getDevices();
    }, [hasPermissions]);

    useEffect(() => {
        const ws = new WebSocket("ws://localhost:8000/ws/trainer");
        socketRef.current = ws;

        ws.onopen = () => {
            setAiMessage("Połączono z serwerem. Gotowy do treningu...");
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === "voice_command") {
                if (data.message) {
                    speak(data.message);
                    setAiMessage(data.message);
                }
                switch (data.event) {
                    case "voice_pause": setIsVoicePaused(true); setMessageType("info"); break;
                    case "voice_resume": setIsVoicePaused(false); break;
                    case "voice_reset": setRepCount(0); setConditions([]); setCurrentPhase("START"); setMessageType("info"); break;
                    case "voice_stop": navigate('/stats'); break;
                    default: break;
                }
                return;
            }

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
                if (data.session) setRepCount(data.session.total_reps);
                if (data.conditions) { setConditions(data.conditions); setIsCalibrated(true); }
            }
        };

        return () => { if (ws) ws.close(); };
    }, [navigate, speak]);

    useEffect(() => {
        if (!hasPermissions) return;
        let audioContext, mediaStream, processor;

        const startAudioStream = async () => {
            try {
                mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
                const source = audioContext.createMediaStreamSource(mediaStream);
                processor = audioContext.createScriptProcessor(4096, 1, 1);
                source.connect(processor);
                processor.connect(audioContext.destination);

                processor.onaudioprocess = (e) => {
                    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN || isVoicePaused) return;
                    const inputData = e.inputBuffer.getChannelData(0);
                    const int16Buffer = new Int16Array(inputData.length);
                    for (let i = 0; i < inputData.length; i++) {
                        int16Buffer[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
                    }
                    socketRef.current.send(int16Buffer.buffer);
                };
            } catch (err) {
                console.error("Błąd audio:", err);
            }
        };
        startAudioStream();
        return () => {
            if (processor) processor.disconnect();
            if (audioContext) audioContext.close();
            if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
        };
    }, [isVoicePaused, hasPermissions]);

    const handleFrontResults = (results) => {
        if (!hasPermissions || isVoicePaused || !socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) return;
        if (!results || !results.poseLandmarks || results.poseLandmarks.length === 0) return;
        const now = performance.now();
        if (now - cameraState.current.front.lastSendTime < 100) return;
        cameraState.current.front.lastSendTime = now;
        socketRef.current.send(JSON.stringify({ camera: "front", landmarks: results.poseLandmarks }));
    };

    const handleSideResults = (results) => {
        if (!hasPermissions || isVoicePaused || !socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) return;
        if (!results || !results.poseLandmarks || results.poseLandmarks.length === 0) return;
        const now = performance.now();
        if (now - cameraState.current.side.lastSendTime < 100) return;
        cameraState.current.side.lastSendTime = now;
        socketRef.current.send(JSON.stringify({ camera: "side", landmarks: results.poseLandmarks }));
    };

    useMediaPipe(videoFrontRef, canvasFrontRef, frontCameraId, handleFrontResults);
    useMediaPipe(videoSideRef, canvasSideRef, sideCameraId, handleSideResults);

    return (
        <div className="min-h-screen bg-gray-900 text-gray-100 font-sans flex flex-col">
            <header className="bg-gray-800 border-b border-gray-700 px-6 py-4 flex items-center justify-between shadow-lg">
                <div className="flex items-center space-x-3">
                    <span className="text-2xl">🏐</span>
                    <h1 className="text-xl font-black tracking-tight text-white uppercase">Trener AI</h1>
                </div>
                <button onClick={() => navigate('/stats')} className="bg-red-600 hover:bg-red-500 text-white px-5 py-2 rounded-xl font-bold text-sm transition-all shadow-md">
                    ZAKOŃCZ TRENING
                </button>
            </header>

            <main className="flex-1 p-6 grid grid-cols-1 xl:grid-cols-4 gap-6 overflow-hidden">
                <section className="xl:col-span-3 grid grid-cols-1 md:grid-cols-2 gap-6 h-full">

                    {/* Kamera Frontowa */}
                    <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden relative shadow-md flex flex-col">
                        <div className="p-3 bg-gray-750 border-b border-gray-700 flex justify-between items-center">
                            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">Kamera Frontowa</span>
                            <select value={frontCameraId} onChange={(e) => setFrontCameraId(e.target.value)} className="bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-gray-300">
                                {devices.map(d => <option key={d.deviceId} value={d.deviceId}>{d.label || `Kamera ${d.deviceId.slice(0,5)}`}</option>)}
                            </select>
                        </div>
                        <div className="flex-1 bg-black relative flex items-center justify-center min-h-[300px]">
                            {/* WIDEO JEST TERAZ WIDOCZNE (USUNIĘTE OPACITY-0) */}
                            <video ref={videoFrontRef} className="absolute inset-0 w-full h-full object-cover" playsInline muted />
                            {/* CANVAS JEST PRZEZROCZYSTĄ WARSTWĄ DO RYSOwANIA LINII AI */}
                            <canvas ref={canvasFrontRef} className="absolute inset-0 w-full h-full object-cover pointer-events-none" width={640} height={480} />
                        </div>
                    </div>

                    {/* Kamera Boczna */}
                    <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden relative shadow-md flex flex-col">
                        <div className="p-3 bg-gray-750 border-b border-gray-700 flex justify-between items-center">
                            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">Kamera Boczna</span>
                            <select value={sideCameraId} onChange={(e) => setSideCameraId(e.target.value)} className="bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-gray-300">
                                {devices.map(d => <option key={d.deviceId} value={d.deviceId}>{d.label || `Kamera ${d.deviceId.slice(0,5)}`}</option>)}
                            </select>
                        </div>
                        <div className="flex-1 bg-black relative flex items-center justify-center min-h-[300px]">
                            <video ref={videoSideRef} className="absolute inset-0 w-full h-full object-cover" playsInline muted />
                            <canvas ref={canvasSideRef} className="absolute inset-0 w-full h-full object-cover pointer-events-none" width={640} height={480} />
                        </div>
                    </div>

                </section>

                {/* Panel boczny statystyk */}
                <section className="flex flex-col gap-6 h-full">
                    <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-3xl p-6 shadow-lg text-center py-8">
                        <h2 className="text-xs font-bold uppercase tracking-widest text-blue-200 mb-1">Poprawne Powtórzenia</h2>
                        <p className="text-7xl font-black text-white">{repCount}</p>
                        <span className="mt-2 inline-block text-[10px] font-bold px-3 py-1 bg-blue-900/40 rounded-full text-blue-100 uppercase">
                            Tryb: {passType}
                        </span>
                    </div>

                    <div className="bg-gray-800 rounded-2xl border border-gray-700 p-5 shadow-md flex-1 flex flex-col justify-between">
                        <div>
                            <div className="flex justify-between items-center mb-4">
                                <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400">Analiza na żywo</h2>
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${isVoicePaused ? 'bg-amber-500/20 text-amber-400' : 'bg-blue-500/20 text-blue-400'}`}>
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

                        <div className="mt-4 pt-4 border-t border-gray-700 flex items-center justify-center space-x-2 text-xs text-gray-400">
                            <span className={`w-2 h-2 rounded-full ${isVoicePaused ? 'bg-amber-500 animate-pulse' : 'bg-green-500 animate-pulse'}`} />
                            <span>Lokalny mikrofon aktywny.</span>
                        </div>
                    </div>
                </section>
            </main>
        </div>
    );
};

export default Training;