// netguard/frontend/src/main.tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useThemeStore } from '@/store/themeStore'
import App from './App'
import './index.css'

// Apply saved theme on load
const darkMode = useThemeStore.getState().darkMode
document.documentElement.classList.toggle('dark', darkMode)

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
      <Toaster
        position="top-right"
        toastOptions={{
          className: '!bg-white dark:!bg-surface-800 !text-surface-900 dark:!text-surface-100 !shadow-lg !border !border-surface-200 dark:!border-surface-700',
          duration: 4000,
        }}
      />
    </BrowserRouter>
  </React.StrictMode>,
)
