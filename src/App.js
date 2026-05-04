import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import Training from './components/Training'
import Stats from './components/Stats';
import TestSpeech from './components/TestSpeech';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/trening" element={<Training />} />
      <Route path="/stats" element={<Stats />} />
      <Route path="/testSpech" element={<TestSpeech />} />
    </Routes>
  );
}

export default App;