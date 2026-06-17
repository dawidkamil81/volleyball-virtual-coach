import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const Dashboard = () => {
  const navigate = useNavigate();

  // Stan agregujący globalne wyliczenia statystyczne ze wszystkich zapisanych treningów
  const [stats, setStats] = useState({
    totalTrainings: 0,
    avgAccuracy: 0,
    totalTimeHours: 0,
    totalTimeMinutes: 0
  });

  // Odpytanie API o statystyki ogólne od razu przy wejściu użytkownika na stronę główną
  useEffect(() => {
    fetch('http://localhost:8000/api/training/stats')
      .then(res => res.json())
      .then(response => {
        if (response.status === 'success' && response.data.length > 0) {
          const trainings = response.data;
          const count = trainings.length;

          // Redukcja (sumowanie) całkowitej liczby sekund spędzonych na ćwiczeniach
          const totalSecs = trainings.reduce((acc, curr) => acc + (curr.Duration || 0), 0);

          // Redukcja i wyciągnięcie średniej wartości celności (Overall Accuracy)
          const totalAcc = trainings.reduce((acc, curr) => acc + (curr.OverallAccuracy || 0), 0);

          setStats({
            totalTrainings: count,
            avgAccuracy: Math.round(totalAcc / count),
            totalTimeHours: Math.floor(totalSecs / 3600),
            totalTimeMinutes: Math.floor((totalSecs % 3600) / 60)
          });
        }
      })
      .catch(err => console.error("Błąd pobierania statystyk:", err));
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 p-6 md:p-10 font-sans">
      
      <header className="mb-8">
        <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
          Cześć, gotowy na trening? 👋
        </h1>
        <p className="text-gray-500 mt-2 text-lg">
          Oto twoje podsumowanie aktywności.
        </p>
      </header>

      <section className="mb-12">
        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 text-center flex flex-col items-center justify-center">
          <div className="bg-blue-50 w-20 h-20 rounded-full flex items-center justify-center mb-4">
            <svg className="w-10 h-10 text-blue-600 ml-1" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-800 mb-2">Rozpocznij nową sesję</h2>
          <p className="text-gray-500 mb-6 max-w-md">
            Włącz kamerę i pozwól trenerowi AI przeanalizować Twoją postawę w czasie rzeczywistym.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4">
            <button 
              onClick={() => navigate('/trening')}
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 px-10 rounded-full text-lg shadow-lg shadow-blue-200 transform transition-all duration-200 hover:scale-105 active:scale-95 flex items-center justify-center"
            >
              Szybki Start
            </button>
            <button 
              onClick={() => navigate('/stats')} 
              className="bg-white border-2 border-blue-600 text-blue-600 font-bold py-4 px-8 rounded-full text-lg hover:bg-blue-50 transition-all flex items-center justify-center"
            >
              Pełna Historia
            </button>
          </div>
        </div>
      </section>

      {/* Kafle podsumowujące połączone z API */}
      <section>
        <h2 className="text-xl font-bold text-gray-800 mb-6">Twoje Osiągnięcia</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          
          <div className="bg-white rounded-2xl shadow-sm p-6 border border-gray-100 flex items-center space-x-5 transition-hover duration-200 hover:shadow-md">
            <div className="p-4 bg-green-100 text-green-600 rounded-xl">
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            </div>
            <div>
              <p className="text-sm text-gray-500 font-medium mb-1">Ukończone Treningi</p>
              <p className="text-3xl font-bold text-gray-800">{stats.totalTrainings}</p>
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-sm p-6 border border-gray-100 flex items-center space-x-5 transition-hover duration-200 hover:shadow-md">
            <div className="p-4 bg-purple-100 text-purple-600 rounded-xl">
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
            </div>
            <div>
              <p className="text-sm text-gray-500 font-medium mb-1">Średnia Skuteczność</p>
              <p className="text-3xl font-bold text-gray-800">{stats.avgAccuracy}<span className="text-lg text-gray-500">%</span></p>
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-sm p-6 border border-gray-100 flex items-center space-x-5 transition-hover duration-200 hover:shadow-md">
            <div className="p-4 bg-orange-100 text-orange-600 rounded-xl">
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            </div>
            <div>
              <p className="text-sm text-gray-500 font-medium mb-1">Całkowity czas z AI</p>
              <p className="text-3xl font-bold text-gray-800">
                {stats.totalTimeHours}<span className="text-lg text-gray-500">h</span> {stats.totalTimeMinutes}<span className="text-lg text-gray-500">m</span>
              </p>
            </div>
          </div>

        </div>
      </section>
    </div>
  );
};

export default Dashboard;