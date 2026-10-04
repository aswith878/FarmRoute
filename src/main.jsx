import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { StoreProvider } from './hooks/useStore';
import App from './App';
import './styles.css';
import './agritech.css';
createRoot(document.getElementById('root')).render(<React.StrictMode><BrowserRouter><StoreProvider><App /></StoreProvider></BrowserRouter></React.StrictMode>);
