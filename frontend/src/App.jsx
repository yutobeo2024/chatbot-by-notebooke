import React, { useState, useEffect, useRef } from 'react'
import { auth } from './firebase'
import {
  signInWithEmailAndPassword,
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
  const authFileRef = useRef(null)

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8042'
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
      const response = await fetch(`${API_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <h1>Y Dược Sài Gòn</h1>
          {user ? (
            <div className="user-info">
              <span>{user.email}</span>
              <button onClick={() => setShowAdmin(!showAdmin)} className="admin-btn">
                {showAdmin ? 'Về Chat' : 'Admin'}
              </button>
              <button onClick={handleLogout} className="logout-link">Thoát</button>
            </div>
          ) : (
            <form onSubmit={handleLogin} className="login-form">
              <input type="email" placeholder="Email" value={loginEmail} onChange={e => setLoginEmail(e.target.value)} required />
              <input type="password" placeholder="Pass" value={loginPassword} onChange={e => setLoginPassword(e.target.value)} required />
              <button type="submit">OK</button>
            </form>
          )}
        </div>

        {!showAdmin && (
          <ul className="module-list">
            {Object.entries(modules).map(([id, module]) => (
              <li
                key={id}
                className={`module-item ${activeModuleId === id ? 'active' : ''}`}
                onClick={() => setActiveModuleId(id)}
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
        {showAdmin ? (
          <div className="admin-dashboard">
            <div className="chat-header">
              <h2>Quản lý Notebook IDs</h2>
              <div>
                <button onClick={handleReauth} disabled={isReauthing} className="save-btn" style={{ marginRight: '10px', backgroundColor: '#e2e8f0', color: '#1e293b' }}>
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
                  style={{ marginRight: '10px', backgroundColor: '#d1fae5', color: '#065f46' }}
                >
                  {isUploadingAuth ? 'Đang upload...' : '📂 Upload auth.json'}
                </button>
                <button onClick={handleUpdateConfig} className="save-btn">Lưu thay đổi</button>
              </div>
            </div>
            {authUploadMsg && (
              <div style={{ padding: '8px 16px', margin: '0 16px', borderRadius: '8px', backgroundColor: authUploadMsg.startsWith('❌') ? '#fee2e2' : '#d1fae5', color: authUploadMsg.startsWith('❌') ? '#991b1b' : '#065f46', fontSize: '14px' }}>
                {authUploadMsg}
              </div>
            )}
            <div className="admin-content">
              {Object.entries(newConfigs).map(([id, config]) => (
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
        ) : (
          <>
            <div className="chat-header">
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
