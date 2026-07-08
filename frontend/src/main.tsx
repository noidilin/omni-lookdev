import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import { StreamingProvider } from './streaming/StreamingProvider';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <StreamingProvider>
    <App />
  </StreamingProvider>,
);

