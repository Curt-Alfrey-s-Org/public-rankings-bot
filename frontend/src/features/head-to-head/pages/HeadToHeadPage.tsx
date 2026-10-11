/**
 * HeadToHeadPage - Player comparison with two-column layout.
 * Player 1: current user/player (admin+: searchable). Player 2: searchable autocomplete.
 */

import { useState, useEffect, useMemo, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { PlayerCard } from '../components/PlayerCard'
import { ComparisonStats } from '../components/ComparisonStats'
import { useHeadToHead } from '../hooks/useHeadToHead'
import { useAuth } from '@/contexts/AuthContext'
import { rankingsApi } from '@/api/rankings'
import { useAlfaAskAiRegistration } from '@alfa-ai/chat-widget'

const MAX_SUGGESTIONS = 15

function PlayerAutocomplete({
  value,
  onChange,
  options,
  placeholder = 'Type or select player...',
}: {
  value: string
  onChange: (v: string) => void
  options: string[]
  placeholder?: string
}) {
  const [query, setQuery] = useState(value)
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)

  const matches = useMemo(() => {
    if (!query.trim()) return options.slice(0, MAX_SUGGESTIONS)
    const q = query.toLowerCase()
    return options.filter((n) => n.toLowerCase().includes(q)).slice(0, MAX_SUGGESTIONS)
  }, [options, query])

  useEffect(() => {
    setQuery(value)
  }, [value])

  const handleSelect = (name: string) => {
    onChange(name)
    setQuery(name)
    setOpen(false)
    setHighlight(0)
  }

  const handleBlur = () => {
    setTimeout(() => {
      setOpen(false)
      if (value && query !== value) setQuery(value)
    }, 150)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') setOpen(true)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlight((h) => Math.min(h + 1, matches.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlight((h) => Math.max(h - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (matches[highlight]) handleSelect(matches[highlight])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <input
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
          setHighlight(0)
        }}
        onFocus={() => setOpen(true)}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className="mt-1 w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-white placeholder-slate-500"
        autoComplete="off"
      />
      {open && matches.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md border border-slate-600 bg-slate-800 py-1 shadow-lg">
          {matches.map((name, i) => (
            <li
              key={name}
              className={`cursor-pointer px-3 py-2 text-slate-200 hover:bg-slate-700 ${
                i === highlight ? 'bg-slate-700' : ''
              }`}
              onMouseDown={(e) => {
                e.preventDefault()
                handleSelect(name)
              }}
            >
              {name}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function HeadToHeadPage() {
  const { isAdmin, isSuperAdmin, user: authUser } = useAuth()
  const authHeaders = useMemo((): HeadersInit | undefined => {
    const token = authUser?.token ?? localStorage.getItem('access_token') ?? localStorage.getItem('auth_token')
    try {
      if (!token && localStorage.getItem('rankings_bot_auth')) {
        const raw = JSON.parse(localStorage.getItem('rankings_bot_auth')!)
        if (raw?.token) return { Authorization: `Bearer ${raw.token}` }
      }
    } catch {
      /* ignore */
    }
    return token ? { Authorization: `Bearer ${token}` } : undefined
  }, [authUser?.token])

  const { data: myPlayerInfo } = useQuery<{ player_name: string }>({
    queryKey: ['player-performance-me'],
    queryFn: async () => {
      const r = await fetch('/api/player-performance/me', { headers: authHeaders })
      if (!r.ok) return { player_name: (authUser?.user ?? '').trim() }
      const data = await r.json()
      return { player_name: (data?.player_name ?? authUser?.user ?? '').trim() }
    },
    enabled: !!authHeaders?.Authorization,
  })
  const currentPlayerName = (myPlayerInfo?.player_name ?? authUser?.user ?? '').trim()

  const [searchParams, setSearchParams] = useSearchParams()
  const p1Param = searchParams.get('p1') ?? ''
  const p2Param = searchParams.get('p2') ?? ''
  const [p1, setP1] = useState(p1Param)
  const [p2, setP2] = useState(p2Param)

  const { data: playerNamesData } = useQuery({
    queryKey: ['rankings', 'player-names'],
    queryFn: () => rankingsApi.getPlayerNames(2000),
    staleTime: 1000 * 60 * 5,
  })
  const allPlayerNames: string[] = useMemo(
    () => [...(playerNamesData?.names ?? [])].sort((a, b) => a.localeCompare(b)),
    [playerNamesData?.names]
  )

  // Initialize p1 to current player when empty; sync URL params
  useEffect(() => {
    setP1((prev) => (p1Param || prev || currentPlayerName))
    setP2((prev) => p2Param || prev)
  }, [p1Param, p2Param])

  useEffect(() => {
    if (!p1 && currentPlayerName) setP1(currentPlayerName)
  }, [currentPlayerName])

  const updateUrl = (operator: string, player2: string) => {
    const params = new URLSearchParams()
    if (operator) params.set('p1', operator)
    if (player2) params.set('p2', player2)
    setSearchParams(params, { replace: true })
  }

  const effectiveP1 = p1 || currentPlayerName
  const { data, isLoading, error } = useHeadToHead(effectiveP1 || null, p2 || null)

  const alfaH2hRegistration = useMemo(() => {
    const p1n = (effectiveP1 || '').trim()
    const p2n = (p2 || '').trim()
    if (!p1n || !p2n || !data) return null
    return {
      page: 'head-to-head' as const,
      playerName: p1n,
      context: {
        operator: data.operator,
        player2: data.player2,
        head_to_head: data.head_to_head,
        narrative: data.narrative,
      } as Record<string, unknown>,
    }
  }, [effectiveP1, p2, data])
  useAlfaAskAiRegistration(alfaH2hRegistration)

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4">
      <header>
        <h1 className="text-2xl font-bold text-white">Head-to-head</h1>
        <p className="mt-1 text-slate-400">
          See two players side by side: rank, Fargo rating, and their record against each other.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-slate-300">Player 1</label>
          {(isAdmin || isSuperAdmin) ? (
            <PlayerAutocomplete
              value={effectiveP1}
              onChange={(v) => {
                setP1(v)
                updateUrl(v, p2)
              }}
              options={allPlayerNames}
              placeholder="Type or select player..."
            />
          ) : (
            <div className="mt-1 w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-white">
              {effectiveP1 || '—'}
            </div>
          )}
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-300">Player 2</label>
          <PlayerAutocomplete
            value={p2}
            onChange={(v) => {
              setP2(v)
              updateUrl(effectiveP1, v)
            }}
            options={allPlayerNames}
            placeholder="Type or select player..."
          />
        </div>
      </div>

      {isLoading && effectiveP1 && p2 && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4 text-slate-400">
          Loading comparison...
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-red-800 bg-red-900/30 p-4 text-red-200">
          {error instanceof Error ? error.message : 'Failed to load comparison'}
        </div>
      )}
      {data && !isLoading && (
        <div className="space-y-4">
          {data.narrative && (
            <div className="rounded-xl border border-slate-700 bg-slate-800/40 p-4">
              <div className="border-l-2 border-slate-500 pl-3 space-y-1">
                {data.narrative_unchanged && (
                  <p className="text-xs text-slate-500 uppercase tracking-wide">Summary unchanged</p>
                )}
                <p
                  className={`text-sm ${data.narrative_unchanged ? 'text-slate-400' : 'text-slate-300/95'}`}
                >
                  {data.narrative}
                </p>
              </div>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <PlayerCard player={data.operator} side="left" showAlfa={isAdmin || isSuperAdmin} />
            <PlayerCard player={data.player2} side="right" showAlfa={isAdmin || isSuperAdmin} />
          </div>
          <ComparisonStats
            headToHead={data.head_to_head}
            operator={data.operator}
            player2={data.player2}
            player1Name={data.operator.name}
            player2Name={data.player2.name}
            showAlfa={isAdmin || isSuperAdmin}
          />
        </div>
      )}
    </div>
  )
}
