import { useEffect, useRef } from 'react';
import useSpeech from '../hooks/useSpeech';

// ZMIANA: Dodano parametr onStartCommand
const useVoiceCommand = (onStopCommand, onStartCommand, speakFunction) => {
    const onStopRef = useRef(onStopCommand);
    const onStartRef = useRef(onStartCommand); // Referencja dla startu
    const isRunning = useRef(false); 

    useEffect(() => {
        onStopRef.current = onStopCommand;
        onStartRef.current = onStartCommand; // Aktualizacja referencji
    }, [onStopCommand, onStartCommand]);

    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            console.warn('Web Speech API nie jest obsługiwane.');
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.lang = 'pl-PL';
        recognition.continuous = true; 
        recognition.interimResults = false; 

        recognition.onstart = () => {
            isRunning.current = true;
        };

        recognition.onresult = (event) => {
            const current = event.resultIndex;
            const transcript = event.results[current][0].transcript.trim().toLowerCase();
            
            console.log("🎤 Mikrofon usłyszał:", transcript);

            // ZMIANA: Obsługa komendy STOP
            if (transcript.includes('stop')) {
                if (speakFunction) speakFunction("koniec");
                if (onStopRef.current) {
                    onStopRef.current();
                }
            } 
            // ZMIANA: Obsługa komendy START
            else if (transcript.includes('start') || transcript.includes('zacznij')) {
                if (speakFunction) speakFunction("startujemy");
                if (onStartRef.current) {
                    onStartRef.current();
                }
            }
        };

        recognition.onerror = (event) => {
            if (event.error !== 'no-speech') {
                console.warn("🎤 Błąd mikrofonu:", event.error);
            }
        };

        recognition.onend = () => {
            isRunning.current = false;
            setTimeout(() => {
                try {
                    if (!isRunning.current) {
                        recognition.start();
                    }
                } catch (error) {}
            }, 500);
        };

        try {
            if (!isRunning.current) {
                recognition.start();
            }
        } catch (error) {
            console.error("Błąd startu mikrofonu:", error);
        }

        return () => {
            recognition.onend = null; 
            try {
                recognition.stop();
            } catch (e) {}
            isRunning.current = false;
        };
    }, [speakFunction]); 
};

export default useVoiceCommand;