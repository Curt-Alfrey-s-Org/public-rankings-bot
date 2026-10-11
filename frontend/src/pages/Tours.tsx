/**
 * Tours — Tour/Series management UI.
 * List tours, create tour, view stops.
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toursApi, type Tour, type TourStop } from '@/api/tours'
import { useAuth } from '@/contexts/AuthContext'
import { toast } from '@/lib/toast'

export default function Tours() {
  const queryClient = useQueryClient()
  const { isDirector, isAdmin } = useAuth()
  const canEdit = isDirector || isAdmin

  const [createName, setCreateName] = useState('')
  const [createYear, setCreateYear] = useState(new Date().getFullYear())
  const [createDescription, setCreateDescription] = useState('')
  const [selectedTourId, setSelectedTourId] = useState<string | null>(null)
  const [newStopNumber, setNewStopNumber] = useState(1)
  const [newStopTournamentId, setNewStopTournamentId] = useState('')
  const [newStopMultiplier, setNewStopMultiplier] = useState(1)

  const { data: tours = [], isLoading } = useQuery({
    queryKey: ['tours'],
    queryFn: () => toursApi.list(),
  })

  const { data: stops = [], isLoading: stopsLoading } = useQuery({
    queryKey: ['tour-stops', selectedTourId],
    queryFn: () => toursApi.listStops(selectedTourId!),
    enabled: !!selectedTourId,
  })

  const createTourMutation = useMutation({
    mutationFn: () =>
      toursApi.create({
        name: createName.trim(),
        year: createYear,
        description: createDescription.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tours'] })
      setCreateName('')
      setCreateDescription('')
      toast.success('Tour created')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to create tour'),
  })

  const addStopMutation = useMutation({
    mutationFn: () =>
      toursApi.addStop(selectedTourId!, {
        stop_number: newStopNumber,
        tournament_id: newStopTournamentId.trim() || undefined,
        points_multiplier: newStopMultiplier,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tour-stops', selectedTourId] })
      setNewStopNumber((n) => n + 1)
      setNewStopTournamentId('')
      setNewStopMultiplier(1)
      toast.success('Stop added')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to add stop'),
  })

  const selectedTour = tours.find((t) => t.tour_id === selectedTourId)

  return (
    <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="max-w-5xl mx-auto p-4 md:p-6">
        <h1 className="text-3xl font-bold text-white mb-2">Tours</h1>
        <p className="text-slate-400 mb-6">Link several events into one season-long tour and track series points.</p>

        {canEdit && (
          <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4 mb-6">
            <h2 className="text-lg font-semibold text-white mb-3">Create Tour</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input
                type="text"
                placeholder="Tour name"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                className="px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white placeholder-slate-400"
              />
              <input
                type="number"
                placeholder="Year"
                value={createYear}
                onChange={(e) => setCreateYear(parseInt(e.target.value, 10) || new Date().getFullYear())}
                className="px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white"
              />
              <input
                type="text"
                placeholder="Description (optional)"
                value={createDescription}
                onChange={(e) => setCreateDescription(e.target.value)}
                className="md:col-span-2 px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white placeholder-slate-400"
              />
            </div>
            <button
              type="button"
              onClick={() => createTourMutation.mutate()}
              disabled={!createName.trim() || createTourMutation.isPending}
              className="mt-3 px-4 py-2 rounded-lg bg-sky-600 text-white font-medium hover:bg-sky-700 disabled:opacity-50"
            >
              {createTourMutation.isPending ? 'Creating…' : 'Create Tour'}
            </button>
          </div>
        )}

        {isLoading ? (
          <p className="text-slate-400">Loading tours…</p>
        ) : tours.length === 0 ? (
          <p className="text-slate-400">No tours yet. Create one to get started.</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-white">Tours</h2>
              {tours.map((t: Tour) => (
                <button
                  key={t.tour_id}
                  onClick={() => setSelectedTourId(t.tour_id)}
                  className={`w-full text-left p-4 rounded-lg border transition-all ${
                    selectedTourId === t.tour_id
                      ? 'bg-sky-900/30 border-sky-600'
                      : 'bg-slate-700/50 border-slate-600 hover:border-slate-500'
                  }`}
                >
                  <div className="font-semibold text-white">{t.name}</div>
                  <div className="text-sm text-slate-400">{t.year}</div>
                </button>
              ))}
            </div>

            <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
              {selectedTour ? (
                <>
                  <h2 className="text-lg font-semibold text-white mb-3">
                    Stops — {selectedTour.name}
                  </h2>
                  {canEdit && (
                    <div className="space-y-2 mb-4">
                      <div className="flex gap-2">
                        <input
                          type="number"
                          placeholder="Stop #"
                          value={newStopNumber}
                          onChange={(e) =>
                            setNewStopNumber(parseInt(e.target.value, 10) || 1)
                          }
                          className="w-20 px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white"
                        />
                        <input
                          type="text"
                          placeholder="Tournament ID (optional)"
                          value={newStopTournamentId}
                          onChange={(e) => setNewStopTournamentId(e.target.value)}
                          className="flex-1 px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white placeholder-slate-400"
                        />
                        <input
                          type="number"
                          step="0.1"
                          placeholder="Multiplier"
                          value={newStopMultiplier}
                          onChange={(e) =>
                            setNewStopMultiplier(parseFloat(e.target.value) || 1)
                          }
                          className="w-24 px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => addStopMutation.mutate()}
                        disabled={addStopMutation.isPending}
                        className="px-4 py-2 rounded-lg bg-sky-600 text-white font-medium hover:bg-sky-700 disabled:opacity-50"
                      >
                        Add Stop
                      </button>
                    </div>
                  )}
                  {stopsLoading ? (
                    <p className="text-slate-400">Loading stops…</p>
                  ) : stops.length === 0 ? (
                    <p className="text-slate-400">No stops yet.</p>
                  ) : (
                    <ul className="space-y-2">
                      {stops.map((s: TourStop) => (
                        <li
                          key={s.id}
                          className="px-3 py-2 rounded-lg bg-slate-700/50 text-white flex justify-between"
                        >
                          <span>
                            Stop {s.stop_number}
                            {s.tournament_id && (
                              <span className="text-slate-400 ml-2">
                                → {s.tournament_id}
                              </span>
                            )}
                          </span>
                          <span className="text-slate-400">
                            ×{s.points_multiplier}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              ) : (
                <p className="text-slate-400">Select a tour to view stops</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
