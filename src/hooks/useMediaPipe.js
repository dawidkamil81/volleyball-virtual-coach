import { useEffect, useRef } from 'react';
import { Pose } from '@mediapipe/pose';
import * as cam from '@mediapipe/camera_utils';
import * as drawing from '@mediapipe/drawing_utils';

export const useMediaPipe = (videoRef, canvasRef, onResultsCallback) => {
    const cameraRef = useRef(null);

    useEffect(() => {
        const pose = new Pose({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`;
            },
        });

        pose.setOptions({
            modelComplexity: 1,
            smoothLandmarks: true,
            minDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5,
        });

        pose.onResults((results) => {
            if (!canvasRef.current || !videoRef.current) return;

            const canvasCtx = canvasRef.current.getContext('2d');
            canvasCtx.save();
            canvasCtx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);

            //szkielet
            if (results.poseLandmarks) {
                drawing.drawConnectors(canvasCtx, results.poseLandmarks, Pose.POSE_CONNECTIONS,
                    { color: '#00FF00', lineWidth: 4 });
                drawing.drawLandmarks(canvasCtx, results.poseLandmarks,
                    { color: '#FF0000', lineWidth: 2 });
            }
            canvasCtx.restore();

            if (onResultsCallback) {
                onResultsCallback(results);
            }
        });

        //uruchamianie kamery
        if (videoRef.current) {
            cameraRef.current = new cam.Camera(videoRef.current, {
                onFrame: async () => {
                    await pose.send({ image: videoRef.current });
                },
                width: 1280,
                height: 720,
            });
            cameraRef.current.start();
        }

        return () => {
            if (cameraRef.current) {
                cameraRef.current.stop();
            }
        };
    }, [videoRef, canvasRef, onResultsCallback]);

    return null;
};