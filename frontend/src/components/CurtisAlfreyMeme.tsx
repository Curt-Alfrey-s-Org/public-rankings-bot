import { useEffect, useRef, useState } from 'react'

const VIDEO_SRC = '/assets/memes/example-example-cave-scraps.mp4'
const REPLAY_INTERVAL_MS = 10_000
/** Remembered across visits; default (no value) = expanded on first visit. */
const COLLAPSE_STORAGE_KEY = 'example_meme_collapsed'

const captionBase =
  'text-[6px] sm:text-[7px] md:text-[8px] leading-[1.1] font-bold px-1 py-0.5 rounded shadow-md text-center'

type CurtisAlfreyMemeProps = {
  className?: string
}

/** Iron Man "box of scraps" clip — splash easter egg. Replays every 10s. All viewports. */
export default function CurtisAlfreyMeme({ className = '' }: CurtisAlfreyMemeProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(COLLAPSE_STORAGE_KEY) === 'true')
    } catch {
      /* localStorage unavailable (private mode) — keep default expanded */
    }
  }, [])

  const setCollapsedPersisted = (next: boolean) => {
    setCollapsed(next)
    try {
      window.localStorage.setItem(COLLAPSE_STORAGE_KEY, String(next))
    } catch {
      /* ignore persistence failure */
    }
  }

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const replay = () => {
      video.currentTime = 0
      void video.play().catch(() => {})
    }

    replay()
    const id = window.setInterval(replay, REPLAY_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [])

  const card = (
    <div className="relative rounded-lg overflow-hidden border border-slate-600/60 shadow-2xl shadow-black/50 bg-black">
      <video ref={videoRef} src={VIDEO_SRC} muted playsInline className="block w-full h-auto" />
      <p
        className={`absolute left-[2%] top-[2%] w-[40%] ${captionBase} text-black bg-red-200/95 border border-red-400 -rotate-1`}
      >
        It&apos;s Impossible!
      </p>
      <p
        className={`absolute right-[2%] top-[2%] w-[52%] ${captionBase} text-black bg-yellow-300/95 border border-yellow-500 rotate-1`}
      >
        Example Example was able to build this in a RV.....with a bunch of computer scraps!
      </p>
      <p
        className={`absolute left-[2%] bottom-[2%] w-[52%] ${captionBase} text-black bg-white/95 border border-slate-400`}
      >
        I&apos;m sorry, I&apos;m not Example Example
      </p>
    </div>
  )

  return (
    <div
      className={`pointer-events-none fixed bottom-4 left-4 z-[35] w-[min(calc(100vw-2rem),300px)] sm:w-[min(calc(100vw-2rem),380px)] xl:w-[420px] pb-[env(safe-area-inset-bottom,0)] pl-[env(safe-area-inset-left,0)] ${className}`.trim()}
    >
      <div
        className={`relative transition-transform duration-300 ease-in-out ${
          collapsed ? '-translate-x-[calc(100%_+_1.5rem)]' : 'translate-x-0'
        }`}
        aria-hidden={collapsed}
      >
        {card}
        <button
          type="button"
          onClick={() => setCollapsedPersisted(true)}
          className="pointer-events-auto absolute top-1 right-1 z-[1] flex h-7 w-7 items-center justify-center rounded-full border border-slate-500/70 bg-slate-900/80 text-base font-bold leading-none text-white shadow-md backdrop-blur transition-colors hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-sky-400/60"
          title="Hide meme"
          aria-label="Hide meme"
        >
          &lsaquo;
        </button>
      </div>

      <button
        type="button"
        onClick={() => setCollapsedPersisted(false)}
        className={`pointer-events-auto fixed bottom-[calc(2rem+env(safe-area-inset-bottom,0))] left-0 z-[36] flex flex-col items-center gap-0.5 rounded-r-lg border border-l-0 border-slate-500/70 bg-slate-900/85 px-1.5 py-2 text-white shadow-lg backdrop-blur transition-all duration-300 ease-in-out hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-sky-400/60 ${
          collapsed ? 'translate-x-0 opacity-pool_opt_in' : '-translate-x-full opacity-0 pointer-events-none'
        }`}
        title="Show meme"
        aria-label="Show Example Example meme"
        aria-hidden={!collapsed}
        tabIndex={collapsed ? 0 : -1}
      >
        <span className="text-base font-bold leading-none">&rsaquo;</span>
        <span className="text-[10px] leading-none" aria-hidden="true">&#9654;</span>
      </button>
    </div>
  )
}
