import React, { useState, useEffect, useRef } from 'react'
import { auth } from './firebase'
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signOut
} from 'firebase/auth'

// TypingEffect types text character-by-character.
// Uses a ref for fullText so the interval always sees the latest value (avoids stale closure bug).
const TypingEffect = ({ fullText, isStreaming }) => {
  const [displayedText, setDisplayedText] = useState('');
  const typedLengthRef = useRef(0);
  const intervalRef = useRef(null);
  const fullTextRef = useRef(fullText); // Always current - avoids stale closure

  // Keep ref synced on every render
  fullTextRef.current = fullText;

  useEffect(() => {
    // New text arrived - start interval if not already running
    if (typedLengthRef.current < fullText.length && !intervalRef.current) {
      intervalRef.current = setInterval(() => {
        const current = fullTextRef.current; // Always reads latest text
        if (typedLengthRef.current < current.length) {
          typedLengthRef.current = Math.min(typedLengthRef.current + 4, current.length);
          setDisplayedText(current.slice(0, typedLengthRef.current));
        } else {
          // Fully caught up - stop interval
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }, 16); // ~60 fps
    }

    return () => { }; // Don't clear interval on re-render - let it keep running
  }, [fullText]);

  // Auto-scroll as text types out
  useEffect(() => {
    const el = document.querySelector('.chat-messages');
    if (el) el.scrollTop = el.scrollHeight;
  }, [displayedText]);

  // Cursor blinks while streaming OR still typing
  const isCursorVisible = isStreaming || (intervalRef.current !== null);

  return (
    <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
      {displayedText}
      {isCursorVisible && <span style={{ opacity: 0.7 }}>▋</span>}
    </span>
  );
};

function App() {
  const [modules, setModules] = useState({})
  const [activeModuleId, setActiveModuleId] = useState('')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [user, setUser] = useState(null)
  const [showAdmin, setShowAdmin] = useState(false)
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [newConfigs, setNewConfigs] = useState({})
  const [isReauthing, setIsReauthing] = useState(false)
  const [isUploadingAuth, setIsUploadingAuth] = useState(false)
  const [authUploadMsg, setAuthUploadMsg] = useState('')
  const [testStatus, setTestStatus] = useState({ state: 'idle', message: '' })
  const [authStatus, setAuthStatus] = useState({ exists: false, last_updated: null })
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const [showBrowser, setShowBrowser] = useState(false)
  const [browserUrl, setBrowserUrl] = useState('')
  const [isBrowserLoading, setIsBrowserLoading] = useState(false)
  const [browserLogs, setBrowserLogs] = useState('')
  const [showLogs, setShowLogs] = useState(false)
  const [whitelist, setWhitelist] = useState([])
  const [newWhitelistEmail, setNewWhitelistEmail] = useState('')
  const authFileRef = useRef(null)

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8042'
  const ADMIN_EMAIL = 'yduoc407@gmail.com'
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser)
      if (currentUser) {
        if (currentUser.email === ADMIN_EMAIL) {
          fetchAuthStatus()
          fetchWhitelist()
        } else {
          setShowAdmin(false)
        }
      }
    })
    return () => unsubscribe()
  }, [])

  const fetchModules = () => {
    fetch(`${API_URL}/api/modules`)
      .then(res => res.json())
      .then(data => {
        setModules(data)
        setNewConfigs(data)
        if (Object.keys(data).length > 0 && !activeModuleId) {
          setActiveModuleId(Object.keys(data)[0])
        }
      })
      .catch(err => console.error('Error fetching modules:', err))
  }

  useEffect(() => {
    fetchModules()
  }, [])

  const fetchAuthStatus = async () => {
    if (!auth.currentUser) return
    try {
      const response = await fetch(`${API_URL}/api/admin/auth-status`, {
        headers: {
          'Authorization': `Bearer ${await auth.currentUser.getIdToken()}`
        }
      })
      const data = await response.json()
      setAuthStatus(data)
    } catch (err) {
      console.error('Failed to fetch auth status', err)
    }
  }


  const fetchWhitelist = async () => {
    if (!auth.currentUser) return
    try {
      const response = await fetch(`${API_URL}/api/admin/whitelist`, {
        headers: {
          'Authorization': `Bearer ${await auth.currentUser.getIdToken()}`
        }
      })
      const data = await response.json()
      if (Array.isArray(data)) {
        setWhitelist(data)
      } else {
        console.error('Whitelist data is not an array:', data)
      }
    } catch (err) {
      console.error('Failed to fetch whitelist', err)
    }
  }

  const addToWhitelist = async () => {
    if (!newWhitelistEmail.trim()) return
    try {
      const response = await fetch(`${API_URL}/api/admin/whitelist`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await auth.currentUser.getIdToken()}`
        },
        body: JSON.stringify({ email: newWhitelistEmail })
      })
      if (response.ok) {
        setNewWhitelistEmail('')
        fetchWhitelist()
      }
    } catch (err) {
      console.error('Add whitelist failed', err)
    }
  }

  const removeFromWhitelist = async (email) => {
    try {
      const response = await fetch(`${API_URL}/api/admin/whitelist/${encodeURIComponent(email)}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${await auth.currentUser.getIdToken()}`
        }
      })
      if (response.ok) fetchWhitelist()
    } catch (err) {
      console.error('Remove whitelist failed', err)
    }
  }

  const handleTestAuth = async () => {
    setTestStatus({ state: 'testing', message: 'Đang kiểm tra...' })
    try {
      const token = await user.getIdToken()
      const res = await fetch(`${API_URL}/api/admin/test-auth`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const data = await res.json()
      if (data.status === 'success') {
        setTestStatus({ state: 'success', message: data.message })
        fetchAuthStatus() // Refresh last updated time
      } else {
        setTestStatus({ state: 'error', message: data.message })
      }
    } catch (err) {
      setTestStatus({ state: 'error', message: 'Lỗi kết nối máy chủ.' })
    }
  }

  const startRemoteBrowser = async () => {
    setIsBrowserLoading(true)
    try {
      const token = await user.getIdToken()
      const res = await fetch(`${API_URL}/api/admin/browser/start`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const data = await res.json()
      if (data.status === 'success') {
        const token = await user.getIdToken()
        setBrowserUrl(`${API_URL}/api/admin/browser/view?token=${token}`)
        setShowBrowser(true)
      } else {
        alert('Lỗi khởi động trình duyệt: ' + data.detail)
      }
    } catch (err) {
      alert('Lỗi kết nối máy chủ.')
    } finally {
      setIsBrowserLoading(false)
    }
  }

  const stopRemoteBrowser = async () => {
    try {
      const token = await user.getIdToken()
      await fetch(`${API_URL}/api/admin/browser/stop`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      setShowBrowser(false)
      setBrowserUrl('')
    } catch (err) {
      console.error(err)
    }
  }

  const extractBrowserCookies = async () => {
    setAuthUploadMsg('⏳ Đang lấy chìa khóa...')
    setBrowserLogs('')
    try {
      const token = await user.getIdToken()
      const res = await fetch(`${API_URL}/api/admin/browser/extract`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const data = await res.json()
      setAuthUploadMsg(data.status === 'success' ? data.message : '❌ Thất bại.')
      if (data.status === 'success') {
        fetchAuthStatus()
      } else if (data.message.includes('Debug Logs:')) {
        setBrowserLogs(data.message.split('Debug Logs:')[1])
      }
    } catch (err) {
      setAuthUploadMsg('❌ Lỗi kết nối.')
    }
  }

  const fetchBrowserLogs = async () => {
    try {
      const token = await user.getIdToken()
      const res = await fetch(`${API_URL}/api/admin/browser/logs`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const data = await res.json()
      setBrowserLogs(data.logs)
      setShowLogs(true)
    } catch (err) {
      alert('Lỗi tải nhật ký.')
    }
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    try {
      await signInWithEmailAndPassword(auth, loginEmail, loginPassword)
      setLoginEmail('')
      setLoginPassword('')
    } catch (err) {
      alert('Đăng nhập thất bại: ' + err.message)
    }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    try {
      // 1. Check if email is in whitelist
      const checkRes = await fetch(`${API_URL}/api/check-whitelist?email=${encodeURIComponent(loginEmail)}`)
      const checkData = await checkRes.json()

      if (!checkData.allowed) {
        alert('Email này không nằm trong danh sách được phép đăng ký. Vui lòng liên hệ Admin!')
        return
      }

      // 2. Perform Firebase registration
      await createUserWithEmailAndPassword(auth, loginEmail, loginPassword)
      alert('Đăng ký thành công!')
      setLoginEmail('')
      setLoginPassword('')
      setIsRegistering(false)
    } catch (err) {
      alert('Đăng ký thất bại: ' + err.message)
    }
  }

  const handleLogout = () => {
    signOut(auth)
    setShowAdmin(false)
  }

  const handleUpdateConfig = async () => {
    if (!user) return
    const idToken = await user.getIdToken()

    try {
      const response = await fetch(`${API_URL}/api/admin/modules`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${idToken}`
        },
        body: JSON.stringify({ modules: newConfigs })
      })
      const data = await response.json()
      if (data.status === 'success') {
        alert('Cập nhật thành công!')
        fetchModules()
      } else {
        alert('Lỗi: ' + data.detail)
      }
    } catch (err) {
      alert('Lỗi kết nối server')
    }
  }

  const handleReauth = async () => {
    if (!user) return
    const idToken = await user.getIdToken()
    setIsReauthing(true)

    try {
      const response = await fetch(`${API_URL}/api/admin/reauth`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${idToken}`
        }
      })
      const data = await response.json()
      if (data.status === 'success') {
        alert(data.message)
      } else {
        alert('Lỗi: ' + data.message)
      }
    } catch (err) {
      alert('Lỗi kết nối server khi xác thực lại')
    } finally {
      setIsReauthing(false)
    }
  }

  const handleAuthUpload = async (e) => {
    const file = e.target.files[0]
    if (!file || !user) return
    setIsUploadingAuth(true)
    setAuthUploadMsg('')
    try {
      const idToken = await user.getIdToken()
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch(`${API_URL}/api/admin/upload-auth`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${idToken}` },
        body: formData
      })
      const data = await response.json()
      if (response.ok) {
        setAuthUploadMsg(data.message)
        fetchAuthStatus() // Refresh status
      } else {
        setAuthUploadMsg('❌ Lỗi: ' + (data.detail || data.message))
      }
    } catch (err) {
      setAuthUploadMsg('❌ Lỗi kết nối server')
    } finally {
      setIsUploadingAuth(false)
      // Reset file input so same file can be re-uploaded
      if (authFileRef.current) authFileRef.current.value = ''
    }
  }

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = { role: 'user', content: input }
    // Initialize bot message with empty content, isStreaming=true
    setMessages(prev => [...prev, userMessage, { role: 'bot', content: '', isStreaming: true }])
    setInput('')
    setIsLoading(true)

    try {
      const idToken = await auth.currentUser.getIdToken()
      const response = await fetch(`${API_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${idToken}`
        },
        body: JSON.stringify({
          module_id: activeModuleId,
          message: input
        })
      })

      if (!response.body) {
        throw new Error('No readable stream available')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let done = false
      let buffer = ''

      while (!done) {
        const { value, done: readerDone } = await reader.read()
        done = readerDone
        if (value) {
          buffer += decoder.decode(value, { stream: true })

          // Process all complete SSE events in the buffer
          const parts = buffer.split('\n\n')
          // Keep the last (potentially incomplete) part in the buffer
          buffer = parts.pop()

          for (const part of parts) {
            const line = part.trim()
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))

                if (data.type === 'chunk' && data.delta) {
                  // Append delta to content — TypingEffect will animate it
                  setMessages(prev => {
                    const newMessages = [...prev]
                    const lastIdx = newMessages.length - 1
                    newMessages[lastIdx] = {
                      ...newMessages[lastIdx],
                      content: newMessages[lastIdx].content + data.delta
                    }
                    return newMessages
                  })
                } else if (data.type === 'error') {
                  setMessages(prev => {
                    const newMessages = [...prev]
                    const lastIdx = newMessages.length - 1
                    newMessages[lastIdx] = {
                      ...newMessages[lastIdx],
                      content: `Lỗi: ${data.error}`,
                      isStreaming: false
                    }
                    return newMessages
                  })
                } else if (data.type === 'done') {
                  // Mark streaming as done so cursor disappears
                  setMessages(prev => {
                    const newMessages = [...prev]
                    const lastIdx = newMessages.length - 1
                    newMessages[lastIdx] = {
                      ...newMessages[lastIdx],
                      isStreaming: false
                    }
                    return newMessages
                  })
                }
              } catch (parseErr) {
                console.error('Parse error on SSE line', line, parseErr)
              }
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => {
        const newMessages = [...prev]
        const lastIdx = newMessages.length - 1
        newMessages[lastIdx] = {
          ...newMessages[lastIdx],
          content: 'Lỗi kết nối đến server.',
          isStreaming: false
        }
        return newMessages
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="app-container">
      {/* Mobile Overlay */}
      {isSidebarOpen && <div className="sidebar-overlay" onClick={() => setIsSidebarOpen(false)}></div>}

      {/* Sidebar */}
      <div className={`sidebar ${isSidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h1>Y Dược Sài Gòn</h1>
          {user ? (
            <div className="user-info">
              <span>{user.email}</span>
              {user.email === ADMIN_EMAIL && (
                <button onClick={() => setShowAdmin(!showAdmin)} className="admin-btn">
                  {showAdmin ? 'Về Chat' : 'Admin'}
                </button>
              )}
              <button onClick={handleLogout} className="logout-link">Thoát</button>
            </div>
          ) : (
            <div className="login-container">
              <h2>{isRegistering ? 'Đăng ký tài khoản' : 'Đăng nhập'}</h2>
              <form onSubmit={isRegistering ? handleRegister : handleLogin} className="login-form">
                <input type="email" placeholder="Email" value={loginEmail} onChange={e => setLoginEmail(e.target.value)} required />
                <input type="password" placeholder="Mật khẩu" value={loginPassword} onChange={e => setLoginPassword(e.target.value)} required />
                <button type="submit">{isRegistering ? 'Đăng ký' : 'Đăng nhập'}</button>
              </form>
              <button
                onClick={() => setIsRegistering(!isRegistering)}
                className="toggle-auth-btn"
              >
                {isRegistering ? 'Đã có tài khoản? Đăng nhập' : 'Chưa có tài khoản? Đăng ký'}
              </button>
              {!isRegistering && (
                <p style={{ fontSize: '12px', color: '#64748b', marginTop: '10px' }}>
                  * Chỉ email trong Whitelist mới có thể đăng ký.
                </p>
              )}
            </div>
          )}
        </div>

        {!showAdmin && (
          <ul className="module-list">
            {modules && Object.entries(modules).map(([id, module]) => (
              <li
                key={id}
                className={`module-item ${activeModuleId === id ? 'active' : ''}`}
                onClick={() => {
                  setActiveModuleId(id)
                  setIsSidebarOpen(false)
                }}
              >
                <span className="module-name">{module.name}</span>
                <span className="module-desc">{module.description}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Main Chat Area or Admin Dashboard */}
      <div className="chat-area">
        {showAdmin && user?.email === ADMIN_EMAIL ? (
          <div className="admin-dashboard">
            <div className="chat-header">
              <button className="menu-toggle" onClick={() => setIsSidebarOpen(true)}>
                <span></span>
                <span></span>
                <span></span>
              </button>
              <h2>Quản lý Notebook IDs</h2>
              <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                Trạng thái Auth: {authStatus.exists ?
                  <span style={{ color: '#059669', fontWeight: 'bold' }}>✅ Đã có (Cập nhật lúc: {authStatus.last_updated})</span> :
                  <span style={{ color: '#dc2626' }}>❌ Chưa có file auth.json</span>
                }
              </div>
              <div style={{ marginTop: '10px', display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                <button onClick={handleTestAuth} disabled={testStatus.state === 'testing'} className="save-btn" style={{ backgroundColor: '#f1f5f9', color: '#475569' }}>
                  {testStatus.state === 'testing' ? '⏳ Đang kiểm tra...' : '⚡ Kiểm tra kết nối'}
                </button>
                <button
                  onClick={startRemoteBrowser}
                  disabled={isBrowserLoading || showBrowser}
                  className="save-btn"
                  style={{ backgroundColor: '#eff6ff', color: '#1e40af' }}
                >
                  {isBrowserLoading ? '⏳ Đang mở...' : '🔐 Đăng nhập từ xa (Mobile)'}
                </button>
                <button onClick={handleReauth} disabled={isReauthing} className="save-btn" style={{ backgroundColor: '#e2e8f0', color: '#1e293b' }}>
                  {isReauthing ? 'Đang kết nối...' : 'Kết nối lại NotebookLM'}
                </button>
                <input
                  type="file"
                  accept=".json"
                  ref={authFileRef}
                  style={{ display: 'none' }}
                  onChange={handleAuthUpload}
                />
                <button
                  onClick={() => authFileRef.current?.click()}
                  disabled={isUploadingAuth}
                  className="save-btn"
                  style={{ backgroundColor: '#d1fae5', color: '#065f46' }}
                >
                  {isUploadingAuth ? 'Đang upload...' : '📂 Upload auth.json'}
                </button>
                <button onClick={handleUpdateConfig} className="save-btn">Lưu thay đổi</button>
              </div>
              {testStatus.message && (
                <div style={{ marginTop: '8px', fontSize: '13px', color: testStatus.state === 'success' ? '#059669' : '#dc2626' }}>
                  {testStatus.message}
                </div>
              )}
            </div>
            {authUploadMsg && (
              <div style={{ padding: '8px 16px', margin: '0 16px', borderRadius: '8px', backgroundColor: authUploadMsg.startsWith('❌') ? '#fee2e2' : '#d1fae5', color: authUploadMsg.startsWith('❌') ? '#991b1b' : '#065f46', fontSize: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>{authUploadMsg}</span>
                {authUploadMsg.startsWith('❌') && !showLogs && (
                  <button onClick={fetchBrowserLogs} style={{ background: 'none', border: '1px solid #991b1b', color: '#991b1b', padding: '2px 8px', borderRadius: '4px', fontSize: '12px', cursor: 'pointer' }}>Xem nhật ký lỗi</button>
                )}
              </div>
            )}

            {showLogs && (
              <div style={{ margin: '10px 16px', padding: '10px', backgroundColor: '#0f172a', color: '#38bdf8', borderRadius: '8px', fontSize: '12px', maxHeight: '200px', overflow: 'auto', fontFamily: 'monospace' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                  <strong>VPS Logs:</strong>
                  <button onClick={() => setShowLogs(false)} style={{ color: '#fff', background: 'none', border: 'none', cursor: 'pointer' }}>Đóng</button>
                </div>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{browserLogs || "Đang tải hoặc không có nhật ký..."}</pre>
              </div>
            )}

            {showBrowser && (
              <div className="browser-modal" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.9)', zIndex: 1000, display: 'flex', flexDirection: 'column' }}>
                <div className="browser-toolbar" style={{ padding: '10px', backgroundColor: '#fff', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <button onClick={extractBrowserCookies} className="save-btn" style={{ padding: '8px 15px' }}>🎯 Lấy chìa khóa</button>
                  <button onClick={() => { const url = browserUrl; setBrowserUrl(''); setTimeout(() => setBrowserUrl(url), 100); }} className="save-btn" style={{ backgroundColor: '#f1f5f9', color: '#475569' }}>🔄 Tải lại trang</button>
                  <button onClick={stopRemoteBrowser} className="save-btn" style={{ backgroundColor: '#fee2e2', color: '#991b1b' }}>Đóng trình duyệt</button>
                  <span style={{ fontSize: '11px', color: '#64748b' }}>
                    Đăng nhập Google xong hãy bấm "Lấy chìa khóa". <br />
                    *Nếu màn hình đen lâu, hãy bấm "Tải lại trang".
                  </span>
                </div>
                <div style={{ flex: 1, position: 'relative', backgroundColor: '#fff' }}>
                  {!browserUrl && <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}>Đang tải màn hình ảo...</div>}
                  <iframe src={browserUrl} style={{ width: '100%', height: '100%', border: 'none', backgroundColor: '#fff' }} title="Remote Browser"></iframe>
                </div>
              </div>
            )}

            <div className="admin-section">
              <h3>Whitelist Người dùng</h3>
              <div className="whitelist-manager">
                <div className="add-whitelist">
                  <input
                    type="email"
                    placeholder="Thêm email vào whitelist"
                    value={newWhitelistEmail}
                    onChange={e => setNewWhitelistEmail(e.target.value)}
                  />
                  <button onClick={addToWhitelist}>Thêm</button>
                </div>
                <ul className="whitelist-list">
                  {whitelist.map(email => (
                    <li key={email}>
                      {email}
                      <button onClick={() => removeFromWhitelist(email)}>Xóa</button>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="admin-section">
              <h3>Cấu hình Module</h3>
              <div className="admin-content">
                {newConfigs && Object.entries(newConfigs).map(([id, config]) => (
                  <div key={id} className="admin-card">
                    <h3>{config.name}</h3>
                    <label>Notebook ID:</label>
                    <input
                      type="text"
                      value={config.notebook_id}
                      onChange={(e) => {
                        setNewConfigs({
                          ...newConfigs,
                          [id]: { ...config, notebook_id: e.target.value }
                        })
                      }}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="chat-header">
              <button className="menu-toggle" onClick={() => setIsSidebarOpen(true)}>
                <span></span>
                <span></span>
                <span></span>
              </button>
              <h2>Trợ lý: {modules[activeModuleId]?.name || 'Đang tải...'}</h2>
            </div>

            <div className="chat-messages">
              {messages.length === 0 && (
                <div className="message bot">
                  Xin chào! Tôi có thể giúp gì cho bạn tại chuyên khoa {modules[activeModuleId]?.name}?
                </div>
              )}
              {messages.map((msg, index) => (
                <div key={index} className={`message ${msg.role}`}>
                  {msg.role === 'bot' ? (
                    msg.content === '' && msg.isStreaming ? (
                      <span className="thinking-dots">Đang suy nghĩ<span>.</span><span>.</span><span>.</span></span>
                    ) : (
                      <TypingEffect fullText={msg.content} isStreaming={msg.isStreaming} />
                    )
                  ) : (
                    <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{msg.content}</span>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-container">
              <form className="chat-form" onSubmit={handleSend}>
                <input
                  type="text"
                  className="chat-input"
                  placeholder="Nhập câu hỏi của bạn..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  disabled={isLoading}
                />
                <button type="submit" className="send-button" disabled={isLoading || !input.trim()}>
                  Gửi
                </button>
              </form>
            </div>
          </>
        )}
      </div>
    </div >
  )
}

export default App
