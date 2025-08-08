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
  const [prompt, setPrompt] = useState('')
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const pollRef = useRef<number | null>(null)

  const onSelectFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    if (!['image/jpeg', 'image/png'].includes(f.type)) {
      setError('Please upload a JPEG or PNG image')
      return
    }
    if (f.size > 8 * 1024 * 1024) {
      setError('Please upload an image smaller than 8MB')
      return
    }
    setError(null)
    setFile(f)
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

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: 24 }}>
      <h1>Manifest AI</h1>
      <p>Upload a selfie and describe what you want to visualize.</p>

      <div style={{ display: 'grid', gap: 12 }}>
        <input type="file" accept="image/jpeg,image/png" onChange={onSelectFile} />
        <input
          type="text"
          placeholder="E.g., me surfing a big wave at sunset"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <button onClick={submit} disabled={submitting}>
          {submitting ? 'Submitting…' : 'Create video'}
        </button>
      </div>

      {error && (
        <p style={{ color: 'crimson', marginTop: 12 }}>{error}</p>
      )}

      {job && (
        <div style={{ marginTop: 24 }}>
          <h3>Status: {job.status}</h3>
          {job.status === 'succeeded' && (
            <div style={{ display: 'grid', gap: 12 }}>
              {job.video_url?.startsWith('http') ? (
                <a href={job.video_url} target="_blank" rel="noreferrer">
                  Open video
                </a>
              ) : (
                <video controls src={job.video_url || `/api/generations/${job.id}/video`} />
              )}
              <a
                href={job.video_url || `/api/generations/${job.id}/video`}
                target={job.video_url?.startsWith('http') ? '_blank' : '_self'}
                download
              >
                Download
              </a>
            </div>
          )}
          {job.status === 'failed' && (
            <p style={{ color: 'crimson' }}>{job.error || 'Generation failed'}</p>
          )}
        </div>
      )}
    </div>
  )
}

export default App
