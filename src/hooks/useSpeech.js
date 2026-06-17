import { useCallback } from 'react';

const useSpeech = () => {
  const speak = useCallback((text) => {
    // Sprawdzamy, czy przeglądarka obsługuje TTS
    if ('speechSynthesis' in window) {
      
      // 1. Twardy reset - uciszamy aktualnie wypowiadany tekst
      window.speechSynthesis.cancel();

      // 2. Hack na bug w Chrome: dajemy przeglądarce 50ms na wyczyszczenie pamięci
      setTimeout(() => {
        const utterance = new SpeechSynthesisUtterance(text);
        
        // Konfiguracja głosu
        utterance.lang = 'pl-PL'; // Język polski
        utterance.rate = 1.1;     // Prędkość (nieco szybsza)
        utterance.pitch = 1.0;    // Ton głosu
        utterance.volume = 1.0;   // Głośność

        // Odtwarzanie
        window.speechSynthesis.speak(utterance);
      }, 50);

    } else {
      console.warn('Twoja przeglądarka nie obsługuje Web Speech API.');
    }
  }, []);

  return { speak };
};

export default useSpeech;