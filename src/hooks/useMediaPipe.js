import { useEffect, useRef } from 'react';
import { Pose, VERSION } from '@mediapipe/pose';
import * as drawing from '@mediapipe/drawing_utils';

export const useMediaPipe = (videoRef, canvasRef, deviceId, onResultsCallback, initDelay = 0) => {
    const streamRef = useRef(null);
    const animationRef = useRef(null);
    const poseRef = useRef(null);
    const callbackRef = useRef(onResultsCallback);

    useEffect(() => {
        callbackRef.current = onResultsCallback;
    }, [onResultsCallback]);

    // --------------------------------------------------------
    // 1. CYKL ŻYCIA MÓZGU (AI)
    // --------------------------------------------------------
    useEffect(() => {
        let pose = null;
        let isMounted = true; // Zabezpieczenie

        // ZMIANA 2: Obudowujemy tworzenie modelu w setTimeout
        const timer = setTimeout(() => {
            if (!isMounted) return;

            pose = new Pose({
                locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose@${VERSION}/${file}`,
            });

            pose.setOptions({
                modelComplexity: 0,
                smoothLandmarks: true,
                minDetectionConfidence: 0.5,
                minTrackingConfidence: 0.5,
            });

            pose.onResults((results) => {
                if (!canvasRef.current) return;
                const canvasCtx = canvasRef.current.getContext('2d');
                canvasCtx.save();
                canvasCtx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
                canvasCtx.drawImage(results.image, 0, 0, canvasRef.current.width, canvasRef.current.height);

                if (results.poseLandmarks) {
                    drawing.drawConnectors(canvasCtx, results.poseLandmarks, Pose.POSE_CONNECTIONS,
                        { color: '#00FF00', lineWidth: 4 });
                    drawing.drawLandmarks(canvasCtx, results.poseLandmarks,
                        { color: '#FF0000', lineWidth: 2 });
                }
                canvasCtx.restore();

                if (callbackRef.current) {
                    callbackRef.current(results);
                }
            });

            poseRef.current = pose;
        }, initDelay); 

        return () => {
            isMounted = false;
            clearTimeout(timer); // Sprzątamy timer
            if (pose) {
                pose.close();
            }
            poseRef.current = null;
        };
    }, [initDelay]);

    // --------------------------------------------------------
    // 2. CYKL ŻYCIA OCZU (Kamery): Reaguje na zmiany urządzenia
    // --------------------------------------------------------
    useEffect(() => {
        // Jeśli nie wybrano kamery lub wideo nie jest gotowe - nic nie rób
        if (!deviceId || !videoRef.current) return;

        const startCamera = async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { deviceId: { exact: deviceId }, width: 640, height: 480 }
                });
                
                if (videoRef.current) {
                    videoRef.current.srcObject = stream;
                    streamRef.current = stream;
                    await videoRef.current.play();

                    stream.getVideoTracks()[0].onended = () => {
                        console.warn(`Zgubiono sygnał z kamery: ${deviceId}`);
                        if (animationRef.current) cancelAnimationFrame(animationRef.current);
                    };

                    const sendFrame = async () => {
                        if (videoRef.current && !videoRef.current.paused && videoRef.current.readyState >= 2 && poseRef.current) {
                            try {
                                await poseRef.current.send({ image: videoRef.current });
                            } catch (err) {
                                // Ciche ignorowanie pojedynczych uszkodzonych klatek podczas odłączania kabla
                            }
                        }
                        
                        if (streamRef.current && streamRef.current.active) {
                            animationRef.current = requestAnimationFrame(sendFrame);
                        }
                    };
                    sendFrame();
                }
            } catch (error) {
                console.error("Błąd sprzętowy kamery:", error);
            }
        };

        startCamera();

        return () => {
            if (animationRef.current) cancelAnimationFrame(animationRef.current);
            if (streamRef.current) {
                streamRef.current.getTracks().forEach(track => track.stop());
            }
            if (videoRef.current) {
                videoRef.current.srcObject = null;
            }
        };
    }, [deviceId, videoRef]); 

    return null;
};