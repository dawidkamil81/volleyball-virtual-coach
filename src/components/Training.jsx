import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useMediaPipe } from "../hooks/useMediaPipe";

const Training = () => {
  const navigate = useNavigate();

  const [devices, setDevices] = useState([]);
  const [frontCameraId, setFrontCameraId] = useState("");
  const [sideCameraId, setSideCameraId] = useState("");

  const [repCount, setRepCount] = useState(0);
  const [isCalibrated, setIsCalibrated] = useState(false);
  const [passType, setPassType] = useState("górne");
  const [coachMessage, setCoachMessage] = useState("Łączenie z serwerem...");

  const videoFrontRef = useRef(null);
  const canvasFrontRef = useRef(null);
  const videoSideRef = useRef(null);
  const canvasSideRef = useRef(null);
  const wsRef = useRef(null);
  const sideLandmarksRef = useRef(null);

  // --- MASZYNA STANÓW ---
  const phaseRef = useRef("idle");
  const repStateRef = useRef({
      squatDone: false,
      peakReached: false,
      peakPerfect: false,
      peakErrors: new Set(),
  });

  useEffect(() => {
    const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
    const wsHost = window.location.hostname || "127.0.0.1";
    const backendPort = process.env.REACT_APP_BACKEND_PORT || "8000";
    const wsUrl = `${wsProtocol}://${wsHost}:${backendPort}/ws/trainer`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setCoachMessage(
        "✅ Połączono z AI. Ustaw się w kadrze i kliknij SKALIBRUJ I START.",
      );
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.status === "error") return;

        const currentPhase = msg.phase; // "idle", "bottom", "peak"
        
        // Wyświetlamy błędy widoczności natychmiast
        const visIssue = msg.issues.find((i) => i.code === "low_visibility" || i.code === "side_low_visibility");
        if (visIssue) {
          setCoachMessage(`❌ WIDOCZNOŚĆ: ${visIssue.message}`);
          return;
        }

        // Histereza - jeśli dotarliśmy do PEAK, nie wracamy do BOTTOM ze względu na drgania kamery.
        // Wrócić można tylko do IDLE po opuszczeniu rąk.
        let effectivePhase = currentPhase;
        if (currentPhase === "idle") {
            phaseRef.current = "idle";
        } else if (currentPhase === "peak") {
            phaseRef.current = "peak";
        } else if (currentPhase === "bottom" && phaseRef.current === "peak") {
            effectivePhase = "peak"; // Ignorujemy spadek do bottom, trzymamy peak
        }

        let message = `[FAZA: ${effectivePhase.toUpperCase()}] `;
        
        if (effectivePhase === "idle") {
            message += "Opuść ręce. Czekam na uniesienie dłoni.";
        } else if (effectivePhase === "bottom") {
            const straightKnees = msg.issues.find(i => i.code === "knees_too_straight");
            const straightElbows = msg.issues.find(i => i.code === "elbows_too_straight");
            const contactTooLow = msg.issues.find(i => i.code === "contact_too_low");
            
            const kneesMsg = straightKnees ? "❌ KOLANA PROSTE" : "✅ KOLANA UGIĘTE";
            const elbowsMsg = straightElbows ? "❌ RĘCE PROSTE" : "✅ RĘCE UGIĘTE";
            
            if (contactTooLow) {
                 message += `${kneesMsg} | ${elbowsMsg} (DŁONIE ZA NISKO!)`;
            } else {
                 message += `${kneesMsg} | ${elbowsMsg}`;
            }
        } else if (effectivePhase === "peak") {
            const bentKnees = msg.issues.find(i => i.code === "no_legs_drive");
            const bentElbows = msg.issues.find(i => i.code === "elbows_too_bent");
            
            const kneesMsg = bentKnees ? "❌ KOLANA ZGIĘTE (wyprostuj!)" : "✅ KOLANA WYPROSTOWANE";
            const elbowsMsg = bentElbows ? "❌ RĘCE ZGIĘTE (wyprostuj!)" : "✅ RĘCE WYPROSTOWANE";
            
            message += `${kneesMsg} | ${elbowsMsg}`;
        }
        
        setCoachMessage(message);
      } catch (e) {
        console.error("Błąd parsowania", e);
      }
    };

    ws.onerror = () => {
      setCoachMessage(
        "❌ Brak połączenia. Upewnij się, że w terminalu działa komenda 'uvicorn main:app'.",
      );
    };

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  useEffect(() => {
    const getDevices = async () => {
      try {
        await navigator.mediaDevices.getUserMedia({ video: true });
        const allDevices = await navigator.mediaDevices.enumerateDevices();
        const videoInputDevices = allDevices.filter(
          (device) => device.kind === "videoinput",
        );

        setDevices(videoInputDevices);
        if (videoInputDevices.length > 0) {
          setFrontCameraId(videoInputDevices[0].deviceId);
          if (videoInputDevices.length > 1)
            setSideCameraId(videoInputDevices[1].deviceId);
        }
      } catch (err) {
        console.error("Błąd dostępu:", err);
      }
    };
    getDevices();
  }, []);

  useMediaPipe(videoFrontRef, canvasFrontRef, frontCameraId, (results) => {
    if (!isCalibrated || passType !== "górne" || !results?.poseLandmarks)
      return;
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    const normalizedLandmarks = results.poseLandmarks.map((lm) => ({
      // Normalizacja payloadu: zawsze x,y,z,visibility (visibility default 1.0)
      x: lm.x ?? 0.0,
      y: lm.y ?? 0.0,
      z: lm.z ?? 0.0,
      visibility: lm.visibility ?? 1.0,
    }));

    const payload = { landmarks: normalizedLandmarks };
    if (sideLandmarksRef.current) {
      payload.side_landmarks = sideLandmarksRef.current;
    }
    ws.send(JSON.stringify(payload));
  });

  useMediaPipe(videoSideRef, canvasSideRef, sideCameraId, (results) => {
    if (!results?.poseLandmarks) return;
    sideLandmarksRef.current = results.poseLandmarks.map((lm) => ({
      x: lm.x ?? 0.0,
      y: lm.y ?? 0.0,
      z: lm.z ?? 0.0,
      visibility: lm.visibility ?? 1.0,
    }));
  });

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col p-4 md:p-6 font-sans">
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-gray-100 tracking-tight">
            Trening Siatkarski
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Analiza ułożenia rąk (Front) i pracy nóg (Bok)
          </p>
        </div>

        <div className="flex gap-4 bg-gray-800 p-3 rounded-xl border border-gray-700">
          <div className="flex flex-col">
            <label className="text-xs text-blue-400 font-bold mb-1 uppercase">
              Kamera: Front
            </label>
            <select
              value={frontCameraId}
              onChange={(e) => setFrontCameraId(e.target.value)}
              className="bg-gray-700 text-white text-sm rounded-lg border-none focus:ring-2 focus:ring-blue-500 max-w-[200px]"
            >
              <option value="">Wybierz kamerę...</option>
              {devices.map((device) => (
                <option key={device.deviceId} value={device.deviceId}>
                  {device.label || `Kamera ${device.deviceId.substring(0, 5)}`}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col">
            <label className="text-xs text-green-400 font-bold mb-1 uppercase">
              Kamera: Bok
            </label>
            <select
              value={sideCameraId}
              onChange={(e) => setSideCameraId(e.target.value)}
              className="bg-gray-700 text-white text-sm rounded-lg border-none focus:ring-2 focus:ring-green-500 max-w-[200px]"
            >
              <option value="">Wybierz kamerę...</option>
              {devices.map((device) => (
                <option key={device.deviceId} value={device.deviceId}>
                  {device.label || `Kamera ${device.deviceId.substring(0, 5)}`}
                </option>
              ))}
            </select>
          </div>
        </div>

        <button
          onClick={() => navigate("/")}
          className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-xl font-bold shadow-lg"
        >
          ZAKOŃCZ
        </button>
      </header>

      <main className="flex-1 flex flex-col lg:flex-row gap-6">
        <section className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* FRONT */}
          <div className="bg-black rounded-3xl relative overflow-hidden border border-blue-500/50 shadow-lg min-h-[400px]">
            <div className="absolute top-4 left-4 z-10 bg-blue-600/80 px-3 py-1 rounded-lg text-sm font-bold uppercase tracking-widest backdrop-blur-sm">
              Front
            </div>
            <video ref={videoFrontRef} className="hidden" playsInline></video>
            <canvas
              ref={canvasFrontRef}
              className="absolute inset-0 w-full h-full object-cover z-0"
              width="640"
              height="480"
            ></canvas>

            {!isCalibrated && (
              <div className="absolute inset-0 bg-black/60 z-20 flex items-center justify-center">
                <p className="text-blue-400 font-bold mb-4">
                  Ustaw się twarzą do kamery
                </p>
                <button
                  onClick={() => {
                    setIsCalibrated(true);
                    setCoachMessage(
                      "🎯 Kalibracja zakończona. Wykonaj pierwsze odbicie...",
                    );
                  }}
                  className="bg-blue-600 hover:bg-blue-500 px-6 py-2 rounded-full font-bold shadow-lg"
                >
                  SKALIBRUJ I START
                </button>
              </div>
            )}
          </div>

          {/* BOK */}
          <div className="bg-black rounded-3xl relative overflow-hidden border border-green-500/50 shadow-lg min-h-[400px]">
            <div className="absolute top-4 left-4 z-10 bg-green-600/80 px-3 py-1 rounded-lg text-sm font-bold uppercase tracking-widest backdrop-blur-sm">
              Bok
            </div>
            <video ref={videoSideRef} className="hidden" playsInline></video>
            <canvas
              ref={canvasSideRef}
              className="absolute inset-0 w-full h-full object-cover z-0"
              width="640"
              height="480"
            ></canvas>
          </div>
        </section>

        <section className="w-full lg:w-64 flex flex-row lg:flex-col gap-4">
          <div className="bg-gray-800 rounded-3xl p-4 flex-1 flex flex-col items-center justify-center border border-gray-700">
            <h2 className="text-gray-400 text-xs uppercase font-bold mb-2">
              Poprawne Odbicia
            </h2>
            <div className="text-4xl font-black text-blue-500">{repCount}</div>
          </div>

          <div className="bg-gray-800 rounded-3xl p-4 flex-1 flex flex-col justify-center border border-gray-700">
            <h2 className="text-gray-400 text-xs uppercase font-bold mb-2 text-center">
              AI Trener
            </h2>
            <p className="text-sm text-gray-300 font-medium text-center">
              {coachMessage}
            </p>
          </div>
        </section>
      </main>
    </div>
  );
};

export default Training;
