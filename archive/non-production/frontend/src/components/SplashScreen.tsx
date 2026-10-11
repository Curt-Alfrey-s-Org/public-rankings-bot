/**
 * Splash screen — same pattern as Contracts Bot: full-screen video, overlay, title, LoginForm.
 * Dismisses only on successful login (onEnter called).
 */

import { useState, useEffect } from 'react'
import type { SplashType } from '@/lib/appearance'
import { useAuth } from '@/contexts/AuthContext'
import LoginForm from './LoginForm'

const DEFAULT_SPLASH_VIDEO = '/assets/video/grok-video-a1fee053-2343-4013-a0de-0445458248cf.mp4'

interface SplashScreenProps {
  splashUrl?: string
  splashType?: SplashType
  onEnter?: () => void
}

export default function SplashScreen({
  splashUrl = DEFAULT_SPLASH_VIDEO,
  splashType = 'video',
  onEnter,
}: SplashScreenProps) {
  const [showSplash, setShowSplash] = useState(true)
  const [mediaError, setMediaError] = useState(false)
  const { login } = useAuth()

  useEffect(() => {
    if (splashUrl && splashType !== 'none') {
      if (splashType === 'video') {
        const video = document.createElement('video')
        video.src = splashUrl
        video.onerror = () => setMediaError(true)
        video.onloadeddata = () => setMediaError(false)
      } else {
        const img = document.createElement('img')
        img.src = splashUrl
        img.onerror = () => setMediaError(true)
        img.onload = () => setMediaError(false)
      }
    }
  }, [splashUrl, splashType])

  const handleLoginSuccess = () => {
    setShowSplash(false)
    onEnter?.()
  }

  if (!showSplash) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black">
      <div className="absolute inset-0 overflow-hidden">
        {!mediaError && splashUrl && splashType !== 'none' && (
          splashType === 'image' ? (
            <img src={splashUrl} alt="Splash" className="w-full h-full object-contain" style={{ objectPosition: 'center' }} />
          ) : (
            <video autoPlay loop muted playsInline className="w-full h-full object-contain" style={{ objectFit: 'contain', objectPosition: 'center' }}>
              <source src={splashUrl} type="video/mp4" />
              Your browser does not support the video tag.
            </video>
          )
        )}
        <div className="absolute inset-0 bg-black/40" />
      </div>
      <div className="relative z-10 flex flex-col items-center justify-center text-center px-6 w-full max-w-md">
        <h1 className="text-5xl font-bold text-white mb-2 drop-shadow-2xl">Rankings Bot</h1>
        <p className="text-lg text-white/90 mb-6 drop-shadow-lg">WPBA & WPA Rankings</p>
        <p className="text-sm uppercase tracking-[0.3em] text-white/80 mb-6 drop-shadow-lg">
          New site is in work, may be ready by April 2026
        </p>
        <LoginForm onSubmit={login} onSuccess={handleLoginSuccess} />
      </div>
    </div>
  )
}
