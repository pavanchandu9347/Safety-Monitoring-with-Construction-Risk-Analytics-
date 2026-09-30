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
      data: { access_token: 'tok', manager: { id: 'm1', username: 'pavanchandu', site_id: 'site_riverside_main' } },
    })
  })

  it('renders the brand and the sign-in form', () => {
    renderLogin()
    expect(screen.getByText('BUILDSURE')).toBeInTheDocument()
    expect(screen.getByText('SIGN IN')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('pavanchandu')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument()
  })

  it('does not show any demo credential quick-access card', () => {
    renderLogin()
    expect(screen.queryByText(/DEMO ACCESS/i)).not.toBeInTheDocument()
    expect(screen.queryByText('FILL EMAIL')).not.toBeInTheDocument()
  })

  it('submits the credentials through the auth context', async () => {
    const user = userEvent.setup()
    renderLogin()
    await user.type(screen.getByPlaceholderText('pavanchandu'), 'pavanchandu')
    await user.type(screen.getByPlaceholderText('••••••••'), 'BuildSure')
    await user.click(screen.getByText('SIGN IN'))
    await waitFor(() => expect(api.login).toHaveBeenCalledWith('pavanchandu', 'BuildSure'))
  })

  it('shows a 401 message for invalid credentials', async () => {
    api.login.mockRejectedValue({ response: { status: 401 } })
    const user = userEvent.setup()
    renderLogin()
    await user.type(screen.getByPlaceholderText('pavanchandu'), 'wronguser')
    await user.type(screen.getByPlaceholderText('••••••••'), 'nope')
    await user.click(screen.getByText('SIGN IN'))
    expect(await screen.findByText('Invalid username or password. Contact your site administrator.')).toBeInTheDocument()
  })
})