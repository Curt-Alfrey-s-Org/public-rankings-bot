/**
 * Back to top button — scrolls to top of page (or scroll container) when clicked.
 * Place at the bottom of long pages (e.g. Rankings).
 */

import { useState, useEffect } from 'react'

interface BackToTopProps {
  /** Optional class name for the button container */
  className?: string
  /** Minimum scroll position (px) before showing the button */
  threshold?: number
  /** Optional ref to the scrollable container (e.g. overflow-y-auto div). If not set, uses window. */
  scrollContainerRef?: React.RefObject<HTMLElement | null>
}

export default function BackToTop({ className = '', threshold = 400, scrollContainerRef }: BackToTopProps) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = scrollContainerRef?.current ?? (typeof window !== 'undefined' ? window : null)
    if (!el) return
    const isWindow = el === window
    const getScrollTop = () => (isWindow ? window.scrollY : (el as HTMLElement).scrollTop)
    const onScroll = () => setVisible(getScrollTop() > threshold)
    el.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => el.removeEventListener('scroll', onScroll)
  }, [threshold, scrollContainerRef])

  const scrollToTop = () => {
    const el = scrollContainerRef?.current ?? (typeof window !== 'undefined' ? window : null)
    if (!el) return
    if (el === window) {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } else {
      (el as HTMLElement).scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  if (!visible) return null

  return (
    <div className={`flex justify-center pt-2 pb-10 ${className}`}>
      <button
        type="button"
        onClick={scrollToTop}
        className="min-h-[44px] px-4 py-2.5 rounded-lg bg-card border border-border text-foreground text-sm font-medium hover:bg-accent transition-colors flex items-center gap-2"
        aria-label="Return to top of page"
      >
        <span aria-hidden>↑</span>
        Back to top
      </button>
    </div>
  )
}
