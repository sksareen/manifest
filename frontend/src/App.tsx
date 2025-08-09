import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import { posthog } from './analytics'

type Job = {
  id: string
  status: 'queued' | 'processing' | 'succeeded' | 'failed'
  prompt?: string
  image_url?: string | null
  video_url?: string | null
  error?: string | null
  progress_stage?: string | null
  estimated_remaining_seconds?: number | null
}



function App() {
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [prompt, setPrompt] = useState('')
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [isDarkMode, setIsDarkMode] = useState(true)
  const [paidSessionId, setPaidSessionId] = useState<string | null>(null)
  const pollRef = useRef<number | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const formRef = useRef<HTMLDivElement>(null)

  const formatETA = (seconds: number | null | undefined): string => {
    if (!seconds || seconds <= 0) return ''
    
    if (seconds < 60) {
      return `~${Math.ceil(seconds)} seconds`
    } else {
      const minutes = Math.ceil(seconds / 60)
      return `~${minutes} minute${minutes > 1 ? 's' : ''}`
    }
  }

  const validateFile = (f: File) => {
    if (!['image/jpeg', 'image/png'].includes(f.type)) {
      setError('Please upload a JPEG or PNG image')
      return false
    }
    if (f.size > 8 * 1024 * 1024) {
      setError('Please upload an image smaller than 8MB')
      return false
    }
    setError(null)
    return true
  }

  const setFileWithPreview = (f: File) => {
    setFile(f)
    // Create preview URL
    const url = URL.createObjectURL(f)
    setPreviewUrl(url)
  }

  const onSelectFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    if (validateFile(f)) {
      setFileWithPreview(f)
    }
  }

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    const f = e.dataTransfer.files?.[0]
    if (f && validateFile(f)) {
      setFileWithPreview(f)
    }
  }

  const handleFileButtonClick = () => {
    posthog.capture('click_choose_file')
    fileInputRef.current?.click()
  }

  const resetForm = () => {
    setFile(null)
    setPreviewUrl(null)
    setPrompt('')
    setJob(null)
    setError(null)
  }

  const toggleTheme = () => {
    const newMode = !isDarkMode
    setIsDarkMode(newMode)
    document.documentElement.setAttribute('data-theme', newMode ? 'dark' : 'light')
  }

  const submitGeneration = async (mode: 'preview' | 'full', sessionId?: string) => {
    if (!file || !prompt.trim()) {
      setError('Upload a selfie and enter a prompt')
      return
    }
    posthog.capture('submit_generation', { mode, has_session: Boolean(sessionId) })
    setSubmitting(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('prompt', prompt)
      form.append('mode', mode)
      if (sessionId) form.append('session_id', sessionId)
      const res = await fetch('/api/generations', { method: 'POST', body: form })
      if (!res.ok) throw new Error(await res.text())
      const data = (await res.json()) as { id: string; status: Job['status'] }
      setJob({ id: data.id, status: data.status })
    } catch (e: any) {
      setError(e?.message || 'Failed to create job')
    } finally {
      setSubmitting(false)
    }
  }

  const createCheckout = async () => {
    posthog.capture('click_manifest_full_dreams')
    try {
      const res = await fetch('/api/payments/create-session', { method: 'POST' })
      if (!res.ok) throw new Error(await res.text())
      const data = (await res.json()) as { url: string }
      window.location.href = data.url
    } catch (e: any) {
      setError(e?.message || 'Failed to start checkout')
    }
  }

  const poll = useCallback(async (id: string) => {
    try {
      const res = await fetch(`/api/generations/${id}`)
      if (!res.ok) throw new Error(await res.text())
      const data = (await res.json()) as Job
      setJob(data)
      if (data.status === 'succeeded' || data.status === 'failed') {
        if (pollRef.current) window.clearInterval(pollRef.current)
        pollRef.current = null
      }
    } catch (e: any) {
      setError(e?.message || 'Polling error')
    }
  }, [])

  useEffect(() => {
    if (job?.id && (job.status === 'queued' || job.status === 'processing')) {
      if (pollRef.current) window.clearInterval(pollRef.current)
      pollRef.current = window.setInterval(() => poll(job.id), 1500)
      // immediate fetch
      poll(job.id)
    }
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current)
    }
  }, [job?.id])

  // Cleanup preview URL when component unmounts or file changes
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  // Initialize theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light')
  }, [])

  // Capture Stripe success URL session_id
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const sessionId = params.get('session_id')
    const checkout = params.get('checkout')
    if (checkout === 'success' && sessionId) {
      setPaidSessionId(sessionId)
    }
  }, [])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'i') {
        e.preventDefault()
        toggleTheme()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isDarkMode])

  return (
    <div data-theme={isDarkMode ? 'dark' : 'light'}>
      <header className="main-header">
        <div className="header-content">
          <div className="header-text">
            <h1 className="header-logo">Manifest AI</h1>
            <p className="header-subtitle">Upload a selfie and visualize your goals coming true</p>
          </div>
          <div className="header-buttons">
            {(file || job) && (
              <button
                className="new-video-btn"
                onClick={resetForm}
                aria-label="Create new video"
              >
                New Video
              </button>
            )}
            <button 
              type="button" 
              className="theme-toggle" 
              onClick={toggleTheme}
              aria-label="Toggle theme"
            >
              <i className={`fas ${isDarkMode ? 'fa-sun' : 'fa-moon'}`}></i>
            </button>
          </div>
        </div>
      </header>
      
      <div className="app-container">

        <div className="sample-showcase">
          <video 
            className="sample-video" 
            src="https://www.w3schools.com/html/mov_bbb.mp4"
            poster="https://peach.blender.org/wp-content/uploads/title_anouncement.jpg?x11217"
            muted
            playsInline 
            loop 
            autoPlay
          />
          {/* <div className="sample-caption">Sample: "me as a flower, achieving my dreams"</div> */}
        </div>

        <div className="main-content">

      {job && job.status !== 'succeeded' && job.status !== 'failed' && (
        <div className="status-indicator">
          <div className="spinner"></div>
          <div className="status-content">
            <span className="status-main">
              {job.progress_stage || 'Processing your video...'}
            </span>
            {job.estimated_remaining_seconds && job.estimated_remaining_seconds > 0 && (
              <span className="status-eta">
                Estimated time remaining: {formatETA(job.estimated_remaining_seconds)}
              </span>
            )}
          </div>
        </div>
      )}

      {job && job.status !== 'succeeded' && job.status !== 'failed' && (job.prompt || prompt) && (
        <div className="prompt-display processing">
          <div className="prompt-label">Your Prompt:</div>
          <div className="prompt-text">{job.prompt || prompt}</div>
        </div>
      )}

      <div className="upload-form" ref={formRef}>
        <div
          className={`media-container ${dragActive ? 'drag-active' : ''} ${file ? 'has-content' : ''} ${job?.status === 'succeeded' ? 'has-video' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={!job || job.status === 'failed' ? handleFileButtonClick : undefined}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png"
            onChange={onSelectFile}
            className="hidden-file-input"
            aria-label="Upload image file"
            title="Upload an image file (JPEG or PNG, up to 8MB)"
          />
          
          {/* Video Preview (when generation succeeded) */}
          {job?.status === 'succeeded' ? (
            <div className="video-preview-content">
              <div className="media-header">Generated Video</div>
              <video 
                controls 
                src={job.video_url || `/api/generations/${job.id}/video`} 
                className="video-preview"
              />
              {job.prompt && (
                <div className="prompt-display">
                  <div className="prompt-label">Your Prompt:</div>
                  <div className="prompt-text">{job.prompt}</div>
                </div>
              )}
              <div className="media-actions">
                <a
                  href={job.video_url || `/api/generations/${job.id}/video`}
                  target={job.video_url?.startsWith('http') ? '_blank' : '_self'}
                  download
                  className="download-button"
                >
                  Download
                </a>
                <button onClick={resetForm} className="change-image-button">
                  Create Another Video
                </button>
              </div>
            </div>
          ) : 
          /* Image Preview (when file is uploaded) */
          file && previewUrl ? (
            <div className="image-preview-content">
              <div className="media-header">Image Preview</div>
              <img 
                src={previewUrl} 
                alt="Selected image preview" 
                className="image-preview"
              />
              <div className="media-actions">
                <button onClick={handleFileButtonClick} className="change-image-button">
                  Change Image
                </button>
              </div>
            </div>
          ) : 
          /* Upload State (no file) */
          (
            <div className="upload-content">
              <div className="upload-icon">📁</div>
              <div className="upload-text">
                <strong>Choose a file</strong> or drag and drop
              </div>
              <div className="upload-subtext">JPEG or PNG, up to 8MB</div>
            </div>
          )}
        </div>
        
        {/* Hide form inputs during processing */}
        {!job || job.status === 'failed' ? (
          <>
            <div className="text-input-container">
              <input
                type="text"
                className="styled-text-input"
                placeholder="E.g., me surfing a big wave at sunset"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !submitting) {
                    submitGeneration('preview')
                  }
                }}
              />
            </div>
            <div className="prompt-chips">
              {[
                'me confidently giving a keynote speech to thousands', 
                'me in my dream home, successful and peaceful', 
                'me crossing the finish line of my first marathon'
              ].map((text, idx) => (
                <button key={idx} className="chip" onClick={() => setPrompt(text)}>
                  {text}
                </button>
              ))}
            </div>
            <div className="actions-row">
              {paidSessionId ? (
                <button className="submit-button primary manifest-cta" onClick={() => submitGeneration('full', paidSessionId)} disabled={submitting}>
                  {submitting ? 'Manifesting…' : '✨ Manifest Full Dreams (20s HD)'}
                </button>
              ) : (
                <button className="submit-button primary manifest-cta" onClick={createCheckout} disabled={submitting}>
                  ✨ Manifest Full Dreams (20s HD)
                </button>
              )}
              <button className="submit-button secondary preview-btn" onClick={() => submitGeneration('preview')} disabled={submitting}>
                {submitting ? 'Loading…' : 'Quick Preview (3s)'}
              </button>
            </div>
          </>
        ) : null}
      </div>

      {error && (
        <p className="error-message">{error}</p>
      )}

      {job && job.status === 'failed' && (
        <p className="error-message">{job.error || 'Generation failed'}</p>
      )}
        </div>
      </div>


    </div>
  )
}

export default App
