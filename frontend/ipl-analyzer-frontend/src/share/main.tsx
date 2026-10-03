import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '../fonts';
import '../index.css';
import SharePage from './SharePage.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SharePage />
  </StrictMode>,
)
