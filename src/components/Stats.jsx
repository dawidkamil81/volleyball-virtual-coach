import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const Stats = () => {
  const navigate = useNavigate();
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8000/api/training/stats')
      .then(res => res.json())
      .then(response => {
        if (response.status === 'success') {
          setHistory(response.data);
        }
        setIsLoading(false);
      })
      .catch(err => {
        console.error("Błąd pobierania bazy:", err);
        setIsLoading(false);
      });
  }, []);

  // Funkcja formatująca datę w ładny sposób (np. "12 Kwi 2024, 14:30")
  const formatDate = (isoString) => {
    if (!isoString) return "-";
    const date = new Date(isoString);
    return date.toLocaleString('pl-PL', { 
      day: 'numeric', month: 'short', year: 'numeric', 
      hour: '2-digit', minute: '2-digit' 
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6 md:p-10 font-sans">
      
      <header className="mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
            Historia Treningów 📊
          </h1>
          <p className="text-gray-500 mt-2 text-lg">
            Lista wszystkich Twoich sesji z trenerem AI.
          </p>
        </div>
        <button 
          onClick={() => navigate('/')}
          className="bg-white border border-gray-200 text-gray-700 hover:bg-gray-100 font-semibold py-2 px-5 rounded-xl shadow-sm transition-all"
        >
          Wróć do Dashboardu
        </button>
      </header>

      <section className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100 text-gray-500 text-sm uppercase tracking-wider">
                <th className="p-5 font-bold">Data i Czas</th>
                <th className="p-5 font-bold">Rodzaj Ćwiczenia</th>
                <th className="p-5 font-bold">Czas Trwania</th>
                <th className="p-5 font-bold">Poprawne / Próby</th>
                <th className="p-5 font-bold">Skuteczność</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                <tr>
                  <td colSpan="5" className="p-8 text-center text-gray-500">Ładowanie historii...</td>
                </tr>
              ) : history.length === 0 ? (
                <tr>
                  <td colSpan="5" className="p-8 text-center text-gray-500 font-medium text-lg">
                    Jeszcze nic tu nie ma. Czas na pierwszy trening! 🏐
                  </td>
                </tr>
              ) : (
                history.map((session, index) => (
                  <tr key={session.TrainingID || index} className="hover:bg-blue-50/50 transition-colors">
                    <td className="p-5 font-medium text-gray-800">
                      {formatDate(session.StartTime)}
                    </td>
                    <td className="p-5">
                      <span className="bg-purple-100 text-purple-700 py-1 px-3 rounded-full text-xs font-bold uppercase tracking-wide">
                        {session.TrainingType}
                      </span>
                    </td>
                    <td className="p-5 text-gray-600">
                      {Math.floor((session.Duration || 0) / 60)} min {(session.Duration || 0) % 60} sek
                    </td>
                    <td className="p-5 font-bold text-gray-700">
                      <span className="text-green-600">{session.SuccessfulReps}</span> 
                      <span className="text-gray-400 font-normal mx-1">/</span> 
                      {session.TotalAttempts}
                    </td>
                    <td className="p-5">
                      <div className="flex items-center gap-3">
                        <span className={`font-black ${session.OverallAccuracy >= 80 ? 'text-green-600' : session.OverallAccuracy >= 50 ? 'text-orange-500' : 'text-red-500'}`}>
                          {session.OverallAccuracy}%
                        </span>
                        {/* Wizualny pasek skuteczności */}
                        <div className="w-24 bg-gray-200 rounded-full h-2 hidden sm:block">
                          <div 
                            className={`h-2 rounded-full ${session.OverallAccuracy >= 80 ? 'bg-green-500' : session.OverallAccuracy >= 50 ? 'bg-orange-400' : 'bg-red-500'}`} 
                            style={{ width: `${session.OverallAccuracy}%` }}
                          ></div>
                        </div>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

    </div>
  );
};

export default Stats;