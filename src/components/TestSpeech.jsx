import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useSpeech from '../hooks/useSpeech';

const TestSpeech = () => {
  const navigate = useNavigate();
  const { speak } = useSpeech();
  const [ostatniaKomenda, setOstatniaKomenda] = useState("Czekam na analizę...");

  // Ta funkcja symuluje to, co docelowo będzie przychodzić z serwera (np. z WebSocketu)
  const symulujOdbiorZSerwera = (komendaTekstowa) => {
    setOstatniaKomenda(komendaTekstowa);
    speak(komendaTekstowa); // Odpalamy czytanie na głos!
  };

  return (
    <div className="min-h-screen bg-gray-900 p-6 flex flex-col font-sans">
        <button 
          onClick={() => navigate('/')}
          className="text-white bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg font-medium transition-all"
        >
          ← Przerwij trening
        </button>
      {/* Panel do testowania (Symulacja serwera) */}
      <div className="mt-8 bg-gray-800 p-6 rounded-2xl border border-gray-700">
        <h3 className="text-white font-bold mb-4">Testowanie komend (Symulacja Serwera):</h3>
        <div className="flex flex-wrap gap-3">
          <button onClick={() => symulujOdbiorZSerwera("Świetnie! Trzymaj tak dalej.")} className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded-lg">👍 Świetnie</button>
          <button onClick={() => symulujOdbiorZSerwera("Wyprostuj plecy, za bardzo się pochylasz.")} className="bg-orange-600 hover:bg-orange-500 text-white px-4 py-2 rounded-lg">⚠️ Plecy</button>
          <button onClick={() => symulujOdbiorZSerwera("Ugnij kolana pod kątem dziewięćdziesięciu stopni.")} className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg">🦵 Kolana</button>
          <button onClick={() => symulujOdbiorZSerwera("Koniec serii, czas na przerwę.")} className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-lg">🛑 Koniec</button>
        </div>
      </div>

    </div>
  );
};

export default TestSpeech;