/**
 * Simple month calendar: shows a month grid and marks days that have tournaments.
 * No external calendar lib; uses native Date.
 */

import { useState, useMemo } from 'react'

export interface CalendarItem {
  id: string
  date: string // YYYY-MM-DD or ISO
  title: string
  location?: string
  status?: string
}

function getMonthDays(year: number, month: number): (number | null)[] {
  const first = new Date(year, month, 1)
  const last = new Date(year, month + 1, 0)
  const startPad = first.getDay()
  const daysInMonth = last.getDate()
  const total = startPad + daysInMonth
  const rows = Math.ceil(total / 7)
  const grid: (number | null)[] = []
  for (let i = 0; i < startPad; i++) grid.push(null)
  for (let d = 1; d <= daysInMonth; d++) grid.push(d)
  while (grid.length < rows * 7) grid.push(null)
  return grid
}

function toDateKey(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function parseTournamentDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) {
    return ''
  }
  return toDateKey(d)
}

interface MonthCalendarProps {
  items: CalendarItem[]
  onSelectItem?: (item: CalendarItem) => void
  getItemUrl?: (item: CalendarItem) => string
  className?: string
}

export default function MonthCalendar({
  items,
  onSelectItem,
  getItemUrl,
  className = '',
}: MonthCalendarProps) {
  const [viewDate, setViewDate] = useState(() => new Date())
  const year = viewDate.getFullYear()
  const month = viewDate.getMonth()

  const daysWithItems = useMemo(() => {
    const map: Record<string, CalendarItem[]> = {}
    items.forEach((item) => {
      const key = parseTournamentDate(item.date)
      if (!key) return
      if (!map[key]) map[key] = []
      map[key].push(item)
    })
    return map
  }, [items])

  const grid = useMemo(() => getMonthDays(year, month), [year, month])
  const monthLabel = viewDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

  const goPrev = () => setViewDate((d) => new Date(d.getFullYear(), d.getMonth() - 1, 1))
  const goNext = () => setViewDate((d) => new Date(d.getFullYear(), d.getMonth() + 1, 1))
  const goToday = () => setViewDate(new Date())

  const weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

  return (
    <div className={className}>
      <div className="flex items-center justify-between mb-3">
        <button
          type="button"
          onClick={goPrev}
          className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/50"
          aria-label="Previous month"
        >
          ←
        </button>
        <h3 className="text-lg font-semibold text-white tabular-nums">{monthLabel}</h3>
        <button
          type="button"
          onClick={goNext}
          className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/50"
          aria-label="Next month"
        >
          →
        </button>
      </div>
      <button
        type="button"
        onClick={goToday}
        className="text-xs text-slate-500 hover:text-slate-300 mb-2"
      >
        Today
      </button>
      <div className="grid grid-cols-7 gap-0.5 text-center">
        {weekDays.map((day) => (
          <div key={day} className="text-xs text-slate-500 py-1 font-medium">
            {day}
          </div>
        ))}
        {grid.map((day, i) => {
          if (day === null) return <div key={`e-${i}`} className="min-h-[2.5rem]" />
          const dateKey = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
          const count = daysWithItems[dateKey]?.length ?? 0
          const hasTournament = count > 0
          const isToday =
            viewDate.getMonth() === new Date().getMonth() &&
            viewDate.getFullYear() === new Date().getFullYear() &&
            day === new Date().getDate()
          return (
            <div
              key={dateKey}
              className={`min-h-[2.5rem] flex flex-col items-center justify-center rounded-lg ${
                isToday ? 'bg-primary/30 text-white font-semibold' : 'text-slate-300'
              } ${hasTournament ? 'bg-slate-600/50' : ''}`}
            >
              <span>{day}</span>
              {hasTournament && (
                <span className="w-1.5 h-1.5 rounded-full bg-primary mt-0.5" title={`${count} tournament(s)`} />
              )}
            </div>
          )
        })}
      </div>
      {/* List tournaments for this month */}
      <ul className="mt-4 space-y-2">
        {items
          .filter((item) => {
            const key = parseTournamentDate(item.date)
            if (!key) return false
            const [y, m] = key.split('-')
            return parseInt(y, 10) === year && parseInt(m, 10) === month + 1
          })
          .sort((a, b) => parseTournamentDate(a.date).localeCompare(parseTournamentDate(b.date)))
          .map((item) => (
            <li key={item.id}>
              {getItemUrl ? (
                <a
                  href={getItemUrl(item)}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 p-2 rounded-lg bg-slate-800/60 border border-slate-700 hover:border-slate-500 hover:bg-slate-800/80 transition-colors text-left"
                >
                  <span className="text-sm text-slate-400 font-mono">{parseTournamentDate(item.date)}</span>
                  <span className="font-medium text-white">{item.title}</span>
                  {item.location && <span className="text-xs text-slate-500">📍 {item.location}</span>}
                  {item.status && (
                    <span className="text-xs px-2 py-0.5 rounded bg-slate-600 text-slate-300">
                      {item.status.replace('_', ' ')}
                    </span>
                  )}
                  <span className="text-slate-500 ml-auto" aria-hidden>↗</span>
                </a>
              ) : (
                <button
                  type="button"
                  onClick={() => onSelectItem?.(item)}
                  className="w-full flex flex-wrap items-center gap-x-3 gap-y-1 p-2 rounded-lg bg-slate-800/60 border border-slate-700 hover:border-slate-500 hover:bg-slate-800/80 transition-colors text-left"
                >
                  <span className="text-sm text-slate-400 font-mono">{parseTournamentDate(item.date)}</span>
                  <span className="font-medium text-white">{item.title}</span>
                  {item.location && <span className="text-xs text-slate-500">📍 {item.location}</span>}
                  {item.status && (
                    <span className="text-xs px-2 py-0.5 rounded bg-slate-600 text-slate-300">
                      {item.status.replace('_', ' ')}
                    </span>
                  )}
                </button>
              )}
            </li>
          ))}
      </ul>
    </div>
  )
}
