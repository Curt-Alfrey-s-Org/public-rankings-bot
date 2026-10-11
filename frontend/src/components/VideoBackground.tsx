import { useState, useEffect, useMemo } from 'react'
import type { BackgroundType } from '@/lib/appearance'

interface VideoBackgroundProps {
  videoPath?: string
  /** When provided, use backgroundUrl + backgroundType instead of videoPath */
  backgroundUrl?: string
  backgroundType?: BackgroundType
  /** When provided and length > 0, cycle through these image URLs as slideshow (ignores single image/video). */
  slideshowUrls?: string[]
  slideshowIntervalMs?: number
  enabled?: boolean
  opacity?: number
  scale?: number
  objectFit?: 'cover' | 'contain' | 'fill' | 'none' | 'scale-down'
  /** Position offset from center (%). Move background around. */
  positionX?: number
  positionY?: number
}

export default function VideoBackground({
  videoPath = '/assets/video/grok-video-a1fee053-2343-4013-a0de-0445458248cf.mp4',
  backgroundUrl,
  backgroundType = 'video',
  slideshowUrls = [],
  slideshowIntervalMs = 6000,
  enabled = true,
  opacity = 0.4,
  scale = 1,
  objectFit = 'cover',
  positionX = 0,
  positionY = 0,
}: VideoBackgroundProps) {
  const [mediaError, setMediaError] = useState(false)
  const validSlideshowUrls = useMemo(
    () => slideshowUrls.filter((u) => u && u.trim()),
    [slideshowUrls]
  )
  const useSlideshow = validSlideshowUrls.length > 0
  const url = backgroundUrl ?? videoPath
  const type = backgroundUrl != null ? backgroundType : 'video'

  // Current slide index for slideshow
  const [slideIndex, setSlideIndex] = useState(0)
  useEffect(() => {
    if (!useSlideshow || validSlideshowUrls.length === 0) return
    const interval = setInterval(() => {
      setSlideIndex((i) => (i + 1) % validSlideshowUrls.length)
    }, slideshowIntervalMs)
    return () => clearInterval(interval)
  }, [useSlideshow, validSlideshowUrls.length, slideshowIntervalMs])

  useEffect(() => {
    if (enabled && !useSlideshow) {
      if (url && type !== 'none') {
        if (type === 'image') {
          const img = document.createElement('img')
          img.src = url
          img.onerror = () => setMediaError(true)
          img.onload = () => setMediaError(false)
        } else {
          const video = document.createElement('video')
          video.src = url
          video.onerror = () => setMediaError(true)
          video.onloadeddata = () => setMediaError(false)
        }
      }
    }
  }, [enabled, url, type, useSlideshow])

  if (!enabled) return null
  if (useSlideshow) {
    const commonStyle: React.CSSProperties = {
      width: `${scale * 100}%`,
      height: `${scale * 100}%`,
      objectFit: objectFit as React.CSSProperties['objectFit'],
      objectPosition: 'center',
      top: '50%',
      left: '50%',
      transform: `translate(-50%, -50%) translate(${positionX}%, ${positionY}%)`,
    }
    return (
      <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
        {validSlideshowUrls.map((src, i) => (
          <img
            key={src}
            src={src}
            alt=""
            className="absolute transition-opacity duration-1000"
            style={{
              ...commonStyle,
              opacity: i === slideIndex ? 1 : 0,
              zIndex: i === slideIndex ? 1 : 0,
            }}
          />
        ))}
        <div className="absolute inset-0 bg-black z-[2]" style={{ opacity }} />
      </div>
    )
  }

  if (type === 'none' || type === 'slideshow' || mediaError) return null

  const commonStyle: React.CSSProperties = {
    width: `${scale * 100}%`,
    height: `${scale * 100}%`,
    objectFit: objectFit as React.CSSProperties['objectFit'],
    objectPosition: 'center',
    top: '50%',
    left: '50%',
    transform: `translate(-50%, -50%) translate(${positionX}%, ${positionY}%)`,
  }

  return (
    <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
      {type === 'image' ? (
        <img
          src={url}
          alt=""
          className="absolute"
          style={commonStyle}
        />
      ) : (
        <video
          autoPlay
          loop
          muted
          playsInline
          className="absolute"
          style={commonStyle}
        >
          <source src={url} type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      )}
      <div className="absolute inset-0 bg-black" style={{ opacity }} />
    </div>
  )
}
