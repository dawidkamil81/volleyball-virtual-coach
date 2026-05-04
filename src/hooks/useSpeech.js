import { useCallback } from 'react';

const useSpeech = () => {
  const speak = useCallback((text) => {
    // Sprawdzamy, czy przeglądarka obsługuje TTS
    if ('speechSynthesis' in window) {
      // Anulujemy poprzednie komunikaty, żeby asystent nie "gadał jeden przez drugiego"
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      
      // Konfiguracja głosu
      utterance.lang = 'pl-PL'; // Język polski
      utterance.rate = 1.1;     // Prędkość (1.0 to domyślna, 1.1 jest nieco bardziej dynamiczna do treningu)
      utterance.pitch = 1.0;    // Ton głosu

      // Odtwarzanie
      window.speechSynthesis.speak(utterance);
    } else {
      console.warn('Twoja przeglądarka nie obsługuje Web Speech API.');
    }
  }, []);

  return { speak };
};

export default useSpeech;