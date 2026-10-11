/**
 * Leagues — League management UI.
 * List leagues, create league, view teams.
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { leaguesApi, type League, type LeagueTeam } from '@/api/leagues'
import { useAuth } from '@/contexts/AuthContext'
import { toast } from '@/lib/toast'

export default function Leagues() {
  const queryClient = useQueryClient()
  const { isDirector, isAdmin } = useAuth()
  const canEdit = isDirector || isAdmin

  const [createName, setCreateName] = useState('')
  const [createOrgCode, setCreateOrgCode] = useState('')
  const [createSeasonStart, setCreateSeasonStart] = useState('')
  const [createSeasonEnd, setCreateSeasonEnd] = useState('')
  const [selectedLeagueId, setSelectedLeagueId] = useState<string | null>(null)
  const [newTeamName, setNewTeamName] = useState('')

  const { data: leagues = [], isLoading } = useQuery({
    queryKey: ['leagues'],
    queryFn: () => leaguesApi.list(),
  })

  const { data: teams = [], isLoading: teamsLoading } = useQuery({
    queryKey: ['league-teams', selectedLeagueId],
    queryFn: () => leaguesApi.listTeams(selectedLeagueId!),
    enabled: !!selectedLeagueId,
  })

  const createLeagueMutation = useMutation({
    mutationFn: () =>
      leaguesApi.create({
        name: createName.trim(),
        org_code: createOrgCode.trim() || undefined,
        season_start: createSeasonStart || undefined,
        season_end: createSeasonEnd || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leagues'] })
      setCreateName('')
      setCreateOrgCode('')
      setCreateSeasonStart('')
      setCreateSeasonEnd('')
      toast.success('League created')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to create league'),
  })

  const createTeamMutation = useMutation({
    mutationFn: () =>
      leaguesApi.createTeam(selectedLeagueId!, { team_name: newTeamName.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['league-teams', selectedLeagueId] })
      setNewTeamName('')
      toast.success('Team added')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to add team'),
  })

  const selectedLeague = leagues.find((l) => l.league_id === selectedLeagueId)

  return (
    <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="max-w-5xl mx-auto p-4 md:p-6">
        <h1 className="text-3xl font-bold text-white mb-2">Leagues</h1>
        <p className="text-slate-400 mb-6">Create a league, add teams, and keep track of how they rank.</p>

        {canEdit && (
          <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4 mb-6">
            <h2 className="text-lg font-semibold text-white mb-3">Create League</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input
                type="text"
                placeholder="League name"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                className="px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white placeholder-slate-400"
              />
              <input
                type="text"
                placeholder="Org code (optional)"
                value={createOrgCode}
                onChange={(e) => setCreateOrgCode(e.target.value)}
                className="px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white placeholder-slate-400"
              />
              <input
                type="date"
                placeholder="Season start"
                value={createSeasonStart}
                onChange={(e) => setCreateSeasonStart(e.target.value)}
                className="px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white"
              />
              <input
                type="date"
                placeholder="Season end"
                value={createSeasonEnd}
                onChange={(e) => setCreateSeasonEnd(e.target.value)}
                className="px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white"
              />
            </div>
            <button
              type="button"
              onClick={() => createLeagueMutation.mutate()}
              disabled={!createName.trim() || createLeagueMutation.isPending}
              className="mt-3 px-4 py-2 rounded-lg bg-sky-600 text-white font-medium hover:bg-sky-700 disabled:opacity-50"
            >
              {createLeagueMutation.isPending ? 'Creating…' : 'Create League'}
            </button>
          </div>
        )}

        {isLoading ? (
          <p className="text-slate-400">Loading leagues…</p>
        ) : leagues.length === 0 ? (
          <p className="text-slate-400">No leagues yet. Create one to get started.</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-white">Leagues</h2>
              {leagues.map((l: League) => (
                <button
                  key={l.league_id}
                  onClick={() => setSelectedLeagueId(l.league_id)}
                  className={`w-full text-left p-4 rounded-lg border transition-all ${
                    selectedLeagueId === l.league_id
                      ? 'bg-sky-900/30 border-sky-600'
                      : 'bg-slate-700/50 border-slate-600 hover:border-slate-500'
                  }`}
                >
                  <div className="font-semibold text-white">{l.name}</div>
                  <div className="text-sm text-slate-400">
                    {l.org_code && <span>{l.org_code}</span>}
                    {l.season_start && (
                      <span>
                        {' '}
                        {l.season_start} – {l.season_end || '…'}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>

            <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
              {selectedLeague ? (
                <>
                  <h2 className="text-lg font-semibold text-white mb-3">
                    Teams — {selectedLeague.name}
                  </h2>
                  {canEdit && (
                    <div className="flex gap-2 mb-4">
                      <input
                        type="text"
                        placeholder="Team name"
                        value={newTeamName}
                        onChange={(e) => setNewTeamName(e.target.value)}
                        className="flex-1 px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white placeholder-slate-400"
                      />
                      <button
                        type="button"
                        onClick={() => createTeamMutation.mutate()}
                        disabled={!newTeamName.trim() || createTeamMutation.isPending}
                        className="px-4 py-2 rounded-lg bg-sky-600 text-white font-medium hover:bg-sky-700 disabled:opacity-50"
                      >
                        Add
                      </button>
                    </div>
                  )}
                  {teamsLoading ? (
                    <p className="text-slate-400">Loading teams…</p>
                  ) : teams.length === 0 ? (
                    <p className="text-slate-400">No teams yet.</p>
                  ) : (
                    <ul className="space-y-2">
                      {teams.map((t: LeagueTeam) => (
                        <li
                          key={t.id}
                          className="px-3 py-2 rounded-lg bg-slate-700/50 text-white"
                        >
                          {t.team_name}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              ) : (
                <p className="text-slate-400">Select a league to view teams</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
