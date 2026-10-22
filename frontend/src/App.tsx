import { LoginPage } from './components/auth/LoginPage'
import { AppShell } from './components/layout/AppShell'
import { Spinner } from './components/ui/Spinner'
import { ToastProvider } from './components/ui/Toast'
import { AuthProvider, useAuth } from './context/AuthContext'
import { SettingsProvider } from './context/SettingsContext'

function Gate() {
  const { user, checking } = useAuth()
  if (checking) {
    return (
      <div className="flex h-full items-center justify-center text-zinc-400">
        <Spinner />
      </div>
    )
  }
  // Keyed by account: switching accounts starts from a clean state.
  return user ? <AppShell key={user.username} /> : <LoginPage />
}

export default function App() {
  return (
    <SettingsProvider>
      <ToastProvider>
        <AuthProvider>
          <Gate />
        </AuthProvider>
      </ToastProvider>
    </SettingsProvider>
  )
}
