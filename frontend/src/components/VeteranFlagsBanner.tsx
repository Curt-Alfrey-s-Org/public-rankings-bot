/**
 * US flag + disabled veteran credit (splash / shared chrome).
 */

function flagSrc(name: string): string {
  const b = import.meta.env.BASE_URL || '/'
  const base = b.endsWith('/') ? b : `${b}/`
  return `${base}flags/${name}`
}

export default function VeteranFlagsBanner({ className = '' }: { className?: string }) {
  return (
    <aside
      className={`pointer-events-none select-none ${className}`.trim()}
      aria-label="Veteran recognition"
    >
      <div className="flex flex-row items-start">
        <img
          src={flagSrc('us.svg')}
          alt="United States flag"
          className="h-7 w-auto rounded-sm border border-white/20 shadow-md sm:h-9"
          width={90}
          height={47}
          decoding="async"
        />
      </div>
      <p className="mt-1.5 max-w-[11rem] text-[10px] font-semibold uppercase leading-tight tracking-wide text-white/95 drop-shadow-md sm:max-w-[13rem] sm:text-[11px]">
        Created by Disabled Veteran
      </p>
    </aside>
  )
}
