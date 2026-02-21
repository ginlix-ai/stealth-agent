import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider, theme as antdTheme } from 'antd'
import { ThemeProvider, useTheme } from './contexts/ThemeContext'
import { AuthProvider } from './contexts/AuthContext'
import App from './App.jsx'
import './i18n'
import './index.css'
import { Toaster } from './components/ui/toaster'

function AntdThemeProvider({ children }) {
  const { theme } = useTheme()
  return (
    <ConfigProvider
      theme={{
        algorithm: theme === 'light' ? antdTheme.defaultAlgorithm : antdTheme.darkAlgorithm,
      }}
    >
      {children}
    </ConfigProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
    <ThemeProvider>
      <AntdThemeProvider>
        <AuthProvider>
          <App />
          <Toaster />
        </AuthProvider>
      </AntdThemeProvider>
    </ThemeProvider>
  </BrowserRouter>,
)
