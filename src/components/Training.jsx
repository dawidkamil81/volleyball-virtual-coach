import React, { useState, useRef} from 'react';
import { useNavigate } from 'react-router-dom';
import { useMediaPipe } from '../hooks/useMediaPipe';

const Training = () => {
    const navigate = useNavigate();
    // Stany aplikacji
    const [repCount, setRepCount] = useState(0);
    const [energyLevel, setEnergyLevel] = useState(85);
    // kalibracja postawy
    const [isCalibrated, setIsCalibrated] = useState(false);
    // wybor odbicia (domyslnie jest gorne)
    const [passType, setPassType] = useState('górne');
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    //uzycie mediapipe
    useMediaPipe(videoRef, canvasRef);

    return (
        <div className="min-h-screen bg-gray-900 text-white flex flex-col p-4 md:p-6 font-sans">

            {/* header */}
            <header className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl md:text-3xl font-bold text-gray-100 tracking-tight">Trening Siatkarski</h1>
                    <p className="text-gray-400 text-sm mt-1">
                        {isCalibrated
                            ? "Twoja technika jest analizowana na biezaco przez Wirtualnego Trenera"
                            : "Wymagana kalibracja do pomiaru proporcji ciała"}
                    </p>
                </div>
                <button
                    onClick={() => navigate('/')}
                    className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-xl font-bold shadow-lg transition-colors duration-200"
                >
                    ZAKOŃCZ
                </button>
            </header>

            {/* glowny uklad */}
            <main className="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-6">
                {/* widok z kamery */}
                <section className="lg:col-span-3 bg-black rounded-3xl relative overflow-hidden flex items-center justify-center border border-gray-800 shadow-2xl">

                    {/* kontener na zrodlo z kamery */}
                    <video ref={videoRef} className="hidden" playsInline></video>
                    <canvas ref={canvasRef} className="absolute inset-0 w-full h-full object-cover z-0" width="1280" height="720"></canvas>

                    {/*nakladka kalibracji (gdy nie jest skalibrowane)*/}
                    {!isCalibrated && (
                        <div className="absolute inset-0 bg-black/80 z-20 flex flex-col items-center justify-center p-8 text-center backdrop-blur-sm">
                            <h2 className="text-3xl font-bold text-white mb-2">Przygotowanie do treningu</h2>
                            <p className="text-gray-300 max-w-lg mb-8 leading-relaxed">
                                Stań w odległości 2-3 metrów od kamery, aby objęła całą Twoją sylwetkę. Pozwoli to algorytmowi poprawnie zmapować Twój wzrost.
                            </p>

                            {/* Wybór ćwiczenia */}
                            <div className="bg-gray-800 p-2 rounded-2xl mb-8 flex gap-2 border border-gray-700">
                                <button
                                    onClick={() => setPassType('górne')}
                                    className={`px-6 py-3 rounded-xl font-bold transition-all ${passType === 'górne' ? 'bg-blue-600 text-white shadow-md' : 'text-gray-400 hover:text-white'}`}
                                >
                                    Odbicie Górne
                                </button>
                                <button
                                    onClick={() => setPassType('dolne')}
                                    className={`px-6 py-3 rounded-xl font-bold transition-all ${passType === 'dolne' ? 'bg-blue-600 text-white shadow-md' : 'text-gray-400 hover:text-white'}`}
                                >
                                    Odbicie Dolne
                                </button>
                            </div>

                            <button
                                onClick={() => setIsCalibrated(true)}
                                className="bg-green-600 hover:bg-green-500 text-white font-bold py-4 px-10 rounded-full shadow-[0_0_20px_rgba(34,197,94,0.4)] transition-all duration-300 transform hover:scale-105 flex items-center gap-2"
                            >
                                ROZPOCZNIJ TRENING
                            </button>
                        </div>
                    )}

                    {/* komunikat o wybranym trybie */}
                    {isCalibrated && (
                        <div className="absolute top-6 left-6 z-10 bg-black/60 backdrop-blur-md px-5 py-3 rounded-2xl border border-gray-700 animate-fade-in">
                            <span className="text-xs text-gray-400 uppercase tracking-wider block mb-1">Trenowany element</span>
                            <span className="text-xl font-bold text-blue-400">
                {passType === 'górne' ? 'Odbicie sposobem górnym' : 'Odbicie sposobem dolnym'}
              </span>
                        </div>
                    )}
                </section>

                <section className={`lg:col-span-1 flex flex-col gap-6 transition-opacity duration-500 ${!isCalibrated ? 'opacity-40 pointer-events-none' : 'opacity-100'}`}>

                    {/*licznik powotorzen*/}
                    <div className="bg-gray-800 rounded-3xl p-6 flex flex-col items-center justify-center border border-gray-700 shadow-lg h-1/3">
                        <h2 className="text-gray-400 text-sm uppercase tracking-wider mb-2 font-bold">Poprawne Odbicia</h2>
                        <div className="text-7xl md:text-8xl font-black text-blue-500 drop-shadow-[0_0_15px_rgba(59,130,246,0.5)]">
                            {repCount}
                        </div>
                    </div>

                    {/*energia*/}
                    <div className="bg-gray-800 rounded-3xl p-6 flex flex-col justify-center border border-gray-700 shadow-lg h-1/3">
                        <div className="flex justify-between items-end mb-4">
                            <h2 className="text-gray-400 text-sm uppercase tracking-wider font-bold">Energia</h2>
                            <span className="text-2xl font-bold text-gray-100">{energyLevel}%</span>
                        </div>

                        <div className="w-full h-8 bg-gray-900 rounded-full overflow-hidden shadow-inner border border-gray-700">
                            <div
                                className={`h-full transition-all duration-500 ease-out rounded-full ${
                                    energyLevel > 50 ? 'bg-green-500' : energyLevel > 20 ? 'bg-yellow-500' : 'bg-red-500'
                                }`}
                                style={{ width: `${energyLevel}%` }}
                            ></div>
                        </div>
                    </div>

                    {/*trener*/}
                    <div className="bg-gray-800 rounded-3xl p-6 border border-gray-700 shadow-lg h-1/3 flex flex-col">
                        <h2 className="text-gray-400 text-sm uppercase tracking-wider mb-4 font-bold flex items-center gap-2">
                            <span className={`w-3 h-3 rounded-full ${isCalibrated ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`}></span>
                            Volleyball AI Coach
                        </h2>
                        <div className="flex-1 flex items-center">
                            <p className="text-lg font-medium text-gray-200 italic leading-relaxed">
                                {!isCalibrated
                                    ? '"Wybierz ćwiczenie i skalibruj postawę..."'
                                    : passType === 'górne'
                                        ? '"Dobry kontakt! Pamiętaj o ułożeniu dłoni w koszyczek."'
                                        : '"Pracuj na nogach! Nie machaj ramionami przy odbiciu dolnym."'}
                            </p>
                        </div>
                    </div>

                </section>
            </main>
        </div>
    );
};

export default Training;