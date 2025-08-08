import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'

type Job = {
  id: string
  status: 'queued' | 'processing' | 'succeeded' | 'failed'
  prompt?: string
  image_url?: string | null
  video_url?: string | null
  error?: string | null
}

function App() {
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [prompt, setPrompt] = useState('')
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const pollRef = useRef<number | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

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
    fileInputRef.current?.click()
  }

  const resetForm = () => {
    setFile(null)
    setPreviewUrl(null)
    setPrompt('')
    setJob(null)
    setError(null)
  }

  const submit = async () => {
    if (!file || !prompt.trim()) {
      setError('Upload a selfie and enter a prompt')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('prompt', prompt)
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

  return (
    <div className="app-container">
      <h1>Manifest AI</h1>
      <p>Upload a selfie and describe what you want to visualize.</p>

      <div className="upload-form">
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
              {job.video_url?.startsWith('http') ? (
                <a href={job.video_url} target="_blank" rel="noreferrer" className="video-link">
                  Open video in new tab
                </a>
              ) : (
                <video controls src={job.video_url || `/api/generations/${job.id}/video`} className="video-preview" />
              )}
              <div className="media-actions">
                <a
                  href={job.video_url || `/api/generations/${job.id}/video`}
                  target={job.video_url?.startsWith('http') ? '_blank' : '_self'}
                  download
                  className="download-button"
                >
                  Download Video
                </a>
                <button onClick={handleFileButtonClick} className="change-image-button">
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
        
        <div className="text-input-container">
          <input
            type="text"
            className="styled-text-input"
            placeholder="E.g., me surfing a big wave at sunset"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !submitting) {
                submit()
              }
            }}
          />
        </div>
        
        <button className="submit-button" onClick={submit} disabled={submitting}>
          {submitting ? 'Submitting…' : 'Create video'}
        </button>
      </div>

      {error && (
        <p className="error-message">{error}</p>
      )}

      {job && job.status !== 'succeeded' && (
        <div className="job-status">
          <h3>Status: {job.status}</h3>
          {job.status === 'failed' && (
            <p className="error-message">{job.error || 'Generation failed'}</p>
          )}
        </div>
      )}
    </div>
  )
}

export default App
