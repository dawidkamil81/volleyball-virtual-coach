import { useEffect, useRef } from 'react';

const useVoiceCommand = (onStopCommand) => {
    const onStopRef = useRef(onStopCommand);
    const isRunning = useRef(false); // Flaga zapobiegająca dublowaniu startu

    useEffect(() => {
        onStopRef.current = onStopCommand;
    }, [onStopCommand]);

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

            if (transcript.includes('stop')) {
                if (onStopRef.current) {
                    onStopRef.current();
                }
            }
        };

        // Zabezpieczenie przed zablokowaniem głównego wątku (Pętla Śmierci)
        recognition.onerror = (event) => {
            // Ignorujemy błędy braku mowy (to normalne przy ciszy)
            if (event.error !== 'no-speech') {
                console.warn("🎤 Błąd mikrofonu:", event.error);
            }
        };

        recognition.onend = () => {
            isRunning.current = false;
            // Dodajemy 500ms (pół sekundy) przerwy, zanim pozwolimy mikrofonowi wystartować ponownie.
            // To całkowicie ulecza problem klatkowania kamer (lagów)!
            setTimeout(() => {
                try {
                    if (!isRunning.current) {
                        recognition.start();
                    }
                } catch (error) {
                    // ignorujemy ciche błędy startu
                }
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
    }, []); 
};

export default useVoiceCommand;