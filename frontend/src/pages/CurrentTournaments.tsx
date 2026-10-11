import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tournamentsApi } from '@/api/tournaments'
import type { Tournament } from '@/api/tournaments'
import { toast } from '@/lib/toast'

type EditData = { tournament_name: string; tournament_date: string; location: string; notes: string }

function EditTournamentForm({
  tournament,
  onSave,
  onCancel,
  isSaving,
}: {
  tournament: Tournament
  onSave: (data: EditData) => void
  onCancel: () => void
  isSaving: boolean
}) {
  const [name, setName] = useState(tournament.tournament_name)
  const [date, setDate] = useState(tournament.tournament_date?.toString().slice(0, 10) ?? '')
  const [location, setLocation] = useState(tournament.location ?? '')
  const [notes, setNotes] = useState(tournament.notes ?? '')
  useEffect(() => {
    setName(tournament.tournament_name)
    setDate(tournament.tournament_date?.toString().slice(0, 10) ?? '')
    setLocation(tournament.location ?? '')
    setNotes(tournament.notes ?? '')
  }, [tournament])
  return (
    <div className="mt-2 p-4 rounded-lg border border-slate-600 bg-slate-800/80 space-y-4">
      <h4 className="text-sm font-medium text-slate-300">Edit tournament</h4>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 rounded border border-slate-600 bg-slate-700 text-white text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Date</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full px-3 py-2 rounded border border-slate-600 bg-slate-700 text-white text-sm"
          />
        </div>
      </div>
      <div>
        <label className="block text-xs text-slate-500 mb-1">Location</label>
        <input
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          className="w-full px-3 py-2 rounded border border-slate-600 bg-slate-700 text-white text-sm"
        />
      </div>
      <div>
        <label className="block text-xs text-slate-500 mb-1">Notes</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className="w-full px-3 py-2 rounded border border-slate-600 bg-slate-700 text-white text-sm"
        />
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onSave({ tournament_name: name, tournament_date: date, location, notes })}
          disabled={isSaving}
          className="px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 disabled:opacity-50"
        >
          {isSaving ? 'Saving...' : 'Save'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={isSaving}
          className="px-3 py-2 rounded-lg bg-slate-600 text-white text-sm font-medium hover:bg-slate-500 disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

export default function CurrentTournaments() {
  const queryClient = useQueryClient()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)

  const { data: tournaments = [], isLoading } = useQuery({
    queryKey: ['tournaments'],
    queryFn: () => tournamentsApi.getTournaments(),
  })

  const deleteMutation = useMutation({
    mutationFn: (tournamentId: string) => tournamentsApi.deleteTournament(tournamentId),
    onSuccess: (_, _tournamentId) => {
      queryClient.invalidateQueries({ queryKey: ['tournaments'] })
      setDeleteConfirmId(null)
      toast.success('Tournament deleted')
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : 'Failed to delete tournament')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<{ tournament_name: string; tournament_date: string; location: string; notes: string }> }) =>
      tournamentsApi.updateTournament(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tournaments'] })
      setEditingId(null)
      toast.success('Tournament updated')
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : 'Failed to update tournament')
    },
  })

  const handleDelete = (t: Tournament) => {
    if (deleteConfirmId === t.tournament_id) {
      deleteMutation.mutate(t.tournament_id)
    } else {
      setDeleteConfirmId(t.tournament_id)
    }
  }

  const editingTournament = editingId ? tournaments.find((t) => t.tournament_id === editingId) : null

  return (
    <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="max-w-5xl mx-auto p-4 md:p-6">
        <h1 className="text-3xl font-bold text-white mb-2">Current Tournaments</h1>
        <p className="text-slate-400 mb-6">View, edit, or delete current tournaments.</p>

        {isLoading ? (
          <p className="text-slate-400">Loading tournaments...</p>
        ) : tournaments.length === 0 ? (
          <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-8 text-center text-slate-400">
            No tournaments yet. <Link to="/tournaments/new" className="text-primary hover:underline">Create one</Link>.
          </div>
        ) : (
          <div className="space-y-4">
            {tournaments.map((t) => (
              <div key={t.tournament_id} className="space-y-0">
                <div
                  className="bg-slate-800/50 backdrop-blur rounded-lg border border-slate-700 p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
                >
                  <div className="min-w-0 flex-1">
                    <h3 className="font-semibold text-white truncate">{t.tournament_name}</h3>
                    <div className="text-sm text-slate-400 mt-1 flex flex-wrap gap-x-4 gap-y-1">
                      <span>📅 {new Date(t.tournament_date).toLocaleDateString()}</span>
                      <span>👥 {t.actual_players} / {t.max_players}</span>
                      <span>🎯 {t.elimination_type === 'round_robin' ? 'Round Robin' : t.elimination_type === 'single' ? 'Single' : 'Double'} Elimination</span>
                      {t.location && <span>📍 {t.location}</span>}
                      <span className="capitalize">{t.status}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <Link
                      to="/tournaments/bracket"
                      state={{ tournamentId: t.tournament_id }}
                      className="px-3 py-2 rounded-lg bg-slate-700 text-white text-sm font-medium hover:bg-slate-600"
                    >
                      Bracket
                    </Link>
                    <button
                      type="button"
                      onClick={() => setEditingId(editingId === t.tournament_id ? null : t.tournament_id)}
                      className="px-3 py-2 rounded-lg bg-blue-700 text-white text-sm font-medium hover:bg-blue-600"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(t)}
                      className="px-3 py-2 rounded-lg bg-red-700 text-white text-sm font-medium hover:bg-red-600"
                    >
                      {deleteConfirmId === t.tournament_id ? 'Confirm delete?' : 'Delete'}
                    </button>
                  </div>
                </div>
                {editingId === t.tournament_id && editingTournament && (
                  <EditTournamentForm
                    tournament={editingTournament}
                    onSave={(data) => updateMutation.mutate({ id: t.tournament_id, data })}
                    onCancel={() => setEditingId(null)}
                    isSaving={updateMutation.isPending}
                  />
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
