import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import Login from '../Login.jsx'
import { AuthProvider } from '../../contexts/AuthContext'
import { ThemeProvider } from '../../contexts/ThemeContext'

vi.mock('../../services/api', () => ({
  api: {
    getMe: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    liveWsUrl: () => 'ws://localhost/ws',
  },
}))

const { api } = await import('../../services/api')

const renderLogin = () =>
  render(
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )

describe('Login page', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    api.getMe.mockResolvedValue({ data: {} })
    api.login.mockResolvedValue({
      data: { access_token: 'tok', manager: { id: 'm1', site_id: 'site_riverside_main' } },
    })
    import.meta.env.VITE_DEMO_MODE = 'true'
  })

  it('renders the brand and the sign-in form', () => {
    renderLogin()
    expect(screen.getByText('BUILDSURE')).toBeInTheDocument()
    expect(screen.getByText('SIGN IN')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('BuildSure@gmail.com')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument()
  })

  it('shows the demo credential quick-access card when demo mode is on', () => {
    renderLogin()
    expect(screen.getByText(/DEMO ACCESS/i)).toBeInTheDocument()
    expect(screen.getByText('FILL EMAIL')).toBeInTheDocument()
  })

  it('hides the demo credential card when VITE_DEMO_MODE=false', () => {
    import.meta.env.VITE_DEMO_MODE = 'false'
    renderLogin()
    expect(screen.queryByText(/DEMO ACCESS/i)).not.toBeInTheDocument()
  })

  it('submits the credentials through the auth context', async () => {
    const user = userEvent.setup()
    renderLogin()
    await user.type(screen.getByPlaceholderText('BuildSure@gmail.com'), 'BuildSure@gmail.com')
    await user.type(screen.getByPlaceholderText('••••••••'), '123456')
    await user.click(screen.getByText('SIGN IN'))
    await waitFor(() => expect(api.login).toHaveBeenCalledWith('BuildSure@gmail.com', '123456'))
  })

  it('shows a 401 message for invalid credentials', async () => {
    api.login.mockRejectedValue({ response: { status: 401 } })
    const user = userEvent.setup()
    renderLogin()
    await user.type(screen.getByPlaceholderText('BuildSure@gmail.com'), 'bad@corp.com')
    await user.type(screen.getByPlaceholderText('••••••••'), 'nope')
    await user.click(screen.getByText('SIGN IN'))
    expect(await screen.findByText('Invalid email or password. Contact your site administrator.')).toBeInTheDocument()
  })
})