import { useEffect, useRef } from 'react';
import { Pose, VERSION } from '@mediapipe/pose';
import * as drawing from '@mediapipe/drawing_utils';

// Globalna blokada zapewniająca sekwencyjne ładowanie plików binarnych (.data/.wasm) z sieci
let globalInitializationPromise = Promise.resolve();

export const useMediaPipe = (videoRef, canvasRef, deviceId, onResultsCallback) => {
    const streamRef = useRef(null);
    const animationRef = useRef(null);
    const poseRef = useRef(null);
    const callbackRef = useRef(onResultsCallback);

    useEffect(() => {
        callbackRef.current = onResultsCallback;
    }, [onResultsCallback]);

    // 1. CYKL ŻYCIA SILNIKA AI
    useEffect(() => {
        let isInstanceMounted = true;

        const initPose = async () => {
            // Kolejkujemy inicjalizację, żeby kamery nie biły się o pobieranie plików .data w tym samym ułamku sekundy
            globalInitializationPromise = globalInitializationPromise.then(async () => {
                if (!isInstanceMounted) return;

                try {
                    const pose = new Pose({
                        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose@${VERSION}/${file}`,
                    });

                    pose.setOptions({
                        modelComplexity: 0,
                        smoothLandmarks: true,
                        minDetectionConfidence: 0.5,
                        minTrackingConfidence: 0.5,
                    });

                    pose.onResults((results) => {
                        if (!canvasRef.current || !isInstanceMounted) return;
                        const canvasCtx = canvasRef.current.getContext('2d');

                        canvasCtx.save();
                        // Wymuszone czyszczenie i rysowanie klatki wideo na canvas
                        canvasCtx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
                        canvasCtx.drawImage(results.image, 0, 0, canvasRef.current.width, canvasRef.current.height);

                        // Nakładanie punktów szkieletu
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

                    // Małe opóźnienie przed puszczeniem kolejnej kamery, by przeglądarka zapisała model w pamięci podręcznej (cache)
                    await new Promise(resolve => setTimeout(resolve, 800));
                } catch (err) {
                    console.error("Błąd krytyczny inicjalizacji instancji MediaPipe:", err);
                }
            });
        };

        initPose();

        return () => {
            isInstanceMounted = false;
            if (poseRef.current) {
                poseRef.current.close();
                poseRef.current = null;
            }
        };
    }, [canvasRef]);

    // 2. CYKL ŻYCIA KAMERY
    useEffect(() => {
        if (!deviceId || !videoRef.current) return;

        let isVideoMounted = true;

        const startCamera = async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { deviceId: { exact: deviceId }, width: 640, height: 480 }
                });

                if (!isVideoMounted) {
                    stream.getTracks().forEach(track => track.stop());
                    return;
                }

                if (videoRef.current) {
                    videoRef.current.srcObject = stream;
                    streamRef.current = stream;
                    await videoRef.current.play();

                    const sendFrame = async () => {
                        // Klatki wysyłamy TYLKO wtedy, gdy obiekt silnika (poseRef.current) został pomyślnie zbudowany w kroku 1
                        if (videoRef.current && !videoRef.current.paused && videoRef.current.readyState >= 2 && poseRef.current) {
                            try {
                                await poseRef.current.send({ image: videoRef.current });
                            } catch (err) {
                                // Ignorowanie błędów pojedynczych klatek
                            }
                        }

                        if (streamRef.current && streamRef.current.active && isVideoMounted) {
                            animationRef.current = requestAnimationFrame(sendFrame);
                        }
                    };
                    sendFrame();
                }
            } catch (error) {
                console.error("Błąd sprzętowy pobierania strumienia kamery:", error);
            }
        };

        startCamera();

        return () => {
            isVideoMounted = false;
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