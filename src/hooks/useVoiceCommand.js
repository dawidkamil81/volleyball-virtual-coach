import { useEffect, useRef } from 'react';

const useVoiceCommand = (onStopCommand) => {
    // Trzymamy referencję do funkcji, żeby uniknąć problemów z odświeżaniem Reacta
    const onStopRef = useRef(onStopCommand);

    useEffect(() => {
        onStopRef.current = onStopCommand;
    }, [onStopCommand]);

    useEffect(() => {
        // Sprawdzenie, czy przeglądarka wspiera nasłuchiwanie (Chrome/Edge działają najlepiej)
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            console.warn('Twoja przeglądarka nie obsługuje rozpoznawania mowy (Web Speech API).');
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.lang = 'pl-PL';
        recognition.continuous = true; // Słuchaj bez przerwy
        recognition.interimResults = false; // Bierzemy pod uwagę tylko pełne słowa

        // Co się dzieje, gdy przeglądarka rozpozna tekst:
        recognition.onresult = (event) => {
            const current = event.resultIndex;
            // Pobieramy to, co usłyszał komputer, usuwamy spacje i zamieniamy na małe litery
            const transcript = event.results[current][0].transcript.trim().toLowerCase();

            console.log("🎤 Komputer usłyszał:", transcript);

            // Jeśli w wypowiedzi padło słowo "stop"
            if (transcript.includes('stop')) {
                if (onStopRef.current) {
                    onStopRef.current(); // Uruchom funkcję przekazaną do hooka (np. navigate('/'))
                }
            }
        };

        // Przeglądarka ma w zwyczaju wyłączać mikrofon po chwili ciszy.
        // Ta funkcja zmusza ją, żeby od razu włączyła go z powrotem.
        recognition.onend = () => {
            try {
                recognition.start();
            } catch (error) {
                // Ciche zignorowanie błędu, gdy komponent jest niszczony
            }
        };

        // Uruchamiamy mikrofon
        try {
            recognition.start();
        } catch (error) {
            console.error("Błąd startu mikrofonu:", error);
        }

        // Funkcja sprzątająca (wyłącza mikrofon, gdy wyjdziesz z treningu)
        return () => {
            recognition.onend = null; // Wyłączamy automatyczne wznawianie
            recognition.stop();
        };
    }, []); 
};

export default useVoiceCommand;