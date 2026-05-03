import React from 'react';
import { useNavigate } from 'react-router-dom';

const Stats = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50 p-6 md:p-10 font-sans">
      
      {/* Nagłówek i nawigacja */}
      <header className="mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
            Twoje Statystyki 📊
          </h1>
          <p className="text-gray-500 mt-2 text-lg">
            Analiza kątów, symetrii i stabilności postawy.
          </p>
        </div>
        <button 
          onClick={() => navigate('/')}
          className="bg-white border border-gray-200 text-gray-700 hover:bg-gray-100 font-semibold py-2 px-5 rounded-xl shadow-sm transition-all"
        >
          Wróć do Dashboardu
        </button>
      </header>

      {/* Główna siatka statystyk */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* Sekcja 1: Stabilność Postawy (Ogólny wynik) */}
        <section className="bg-white p-8 rounded-3xl shadow-sm border border-gray-100 flex flex-col items-center justify-center">
          <h2 className="text-xl font-bold text-gray-800 mb-6 w-full text-left">Stabilność Postawy</h2>
          
          {/* Wizualizacja wyniku procentowego (Kółko) */}
          <div className="relative w-48 h-48 flex items-center justify-center mb-6">
            <div className="absolute w-full h-full rounded-full border-[12px] border-gray-100"></div>
            <div className="absolute w-full h-full rounded-full border-[12px] border-blue-600 border-r-transparent border-b-transparent transform rotate-45"></div>
            <div className="text-center">
              <span className="text-5xl font-extrabold text-gray-800">88<span className="text-2xl">%</span></span>
            </div>
          </div>

          <p className="text-gray-500 text-center max-w-sm">
            Twój balans ciała uległ poprawie o <strong className="text-green-600">5%</strong> w stosunku do ostatniego treningu. Świetnie utrzymujesz środek ciężkości!
          </p>
        </section>

        {/* Sekcja 2: Analiza Kątów Stawów */}
        <section className="bg-white p-8 rounded-3xl shadow-sm border border-gray-100">
          <h2 className="text-xl font-bold text-gray-800 mb-6">Analiza Kątów (Ostatnia sesja)</h2>
          
          <div className="space-y-8">
            
            {/* Cecha 1: Zgięcie Kolan */}
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-sm font-semibold text-gray-700">Zgięcie kolan (Przysiad)</span>
                <span className="text-sm font-bold text-gray-900">85° / 90°</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-3">
                <div className="bg-green-500 h-3 rounded-full" style={{ width: '95%' }}></div>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Niemal idealny kąt prosty. Bardzo dobra głębokość przysiadu.
              </p>
            </div>

            {/* Cecha 2: Proste Plecy */}
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-sm font-semibold text-gray-700">Odchylenie pleców</span>
                <span className="text-sm font-bold text-gray-900">15° / 20°</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-3">
                <div className="bg-blue-500 h-3 rounded-full" style={{ width: '75%' }}></div>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Plecy trzymane prosto. Naturalne pochylenie przy fazie ekscentrycznej.
              </p>
            </div>

            {/* Cecha 3: Asymetria Bioder (Błąd) */}
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-sm font-semibold text-gray-700">Symetria Bioder</span>
                <span className="text-sm font-bold text-red-600">Wymaga poprawy</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-3">
                <div className="bg-red-500 h-3 rounded-full" style={{ width: '40%' }}></div>
              </div>
              <p className="text-xs text-red-500 mt-2 font-medium">
                Zauważono lekkie przenoszenie ciężaru na prawą nogę (asymetria 8°).
              </p>
            </div>

          </div>
        </section>

      </div>
    </div>
  );
};

export default Stats;