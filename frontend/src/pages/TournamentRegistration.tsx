/**
 * Tournament Registration - Register for tournaments with optional payment and waitlist.
 */

import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { loadStripe } from '@stripe/stripe-js'
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js'
import { tournamentsApi, type Player, type Tournament } from '@/api/tournaments'
import { toast } from '@/lib/toast'
import { useAuth } from '@/contexts/AuthContext'

export default function TournamentRegistration() {
  const queryClient = useQueryClient()
  useAuth()
  const [searchParams] = useSearchParams()
  const [selectedTournamentId, setSelectedTournamentId] = useState<string | null>(null)
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null)
  const [paymentClientSecret, setPaymentClientSecret] = useState<string | null>(null)
  const [paymentIntentId, setPaymentIntentId] = useState<string | null>(null)

  const { data: tournaments = [] } = useQuery({
    queryKey: ['tournaments'],
    queryFn: () => tournamentsApi.getTournaments(),
  })

  const openTournaments = tournaments.filter(
    (t: Tournament) => t.status === 'setup' || t.status === 'registration'
  )

  useEffect(() => {
    if (!openTournaments.length || selectedTournamentId) return

    const tournamentIdParam = searchParams.get('tournamentId')?.trim()
    const eventNameParam = searchParams.get('eventName')?.trim().toLowerCase()

    if (tournamentIdParam) {
      const exact = openTournaments.find((t: Tournament) => t.tournament_id === tournamentIdParam)
      if (exact) {
        setSelectedTournamentId(exact.tournament_id)
        return
      }
    }

    if (eventNameParam) {
      const byName = openTournaments.find((t: Tournament) =>
        t.tournament_name?.trim().toLowerCase() === eventNameParam
      )
      if (byName) {
        setSelectedTournamentId(byName.tournament_id)
      }
    }
  }, [openTournaments, searchParams, selectedTournamentId])

  const { data: players = [] } = useQuery<Player[]>({
    queryKey: ['players'],
    queryFn: () => tournamentsApi.getPlayers(),
  })

  const { data: tournamentPlayers = [] } = useQuery({
    queryKey: ['tournament-players', selectedTournamentId],
    queryFn: () => tournamentsApi.getTournamentPlayers(selectedTournamentId!),
    enabled: !!selectedTournamentId,
  })

  const { data: regSettings = { entry_fee_cents: 0 } } = useQuery({
    queryKey: ['registration-settings', selectedTournamentId],
    queryFn: () => tournamentsApi.getRegistrationSettings(selectedTournamentId!),
    enabled: !!selectedTournamentId,
  })

  const selectedTournament = openTournaments.find((t: Tournament) => t.tournament_id === selectedTournamentId)
  const isFull = selectedTournament && tournamentPlayers.length >= (selectedTournament.max_players || 32)
  const entryFeeCents = regSettings.entry_fee_cents || 0
  const entryFeeDollars = (entryFeeCents / 100).toFixed(2)

  const registerMutation = useMutation({
    mutationFn: ({ tid, pid }: { tid: string; pid: string }) =>
      tournamentsApi.registerPlayer(tid, pid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tournament-players', selectedTournamentId] })
      queryClient.invalidateQueries({ queryKey: ['tournaments'] })
      toast.success('Registered successfully!')
      setSelectedPlayerId(null)
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Registration failed'),
  })

  const waitlistMutation = useMutation({
    mutationFn: ({ tid, pid }: { tid: string; pid: string }) =>
      tournamentsApi.addToWaitlist(tid, pid),
    onSuccess: (data) => {
      toast.success(`Added to waitlist. Position: ${data.position}`)
      setSelectedPlayerId(null)
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Waitlist failed'),
  })

  const paymentIntentMutation = useMutation({
    mutationFn: ({ tid, pid }: { tid: string; pid: string }) =>
      tournamentsApi.createRegistrationPaymentIntent(tid, pid),
    onSuccess: (data) => {
      setPaymentClientSecret(data.client_secret)
      setPaymentIntentId(data.intent_id)
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Payment failed'),
  })

  const handleRegister = () => {
    if (!selectedTournamentId || !selectedPlayerId) {
      toast.error('Select a tournament and player')
      return
    }
    if (isFull) {
      waitlistMutation.mutate({ tid: selectedTournamentId, pid: selectedPlayerId })
    } else if (entryFeeCents > 0) {
      paymentIntentMutation.mutate({ tid: selectedTournamentId, pid: selectedPlayerId })
    } else {
      registerMutation.mutate({ tid: selectedTournamentId, pid: selectedPlayerId })
    }
  }

  const handlePaymentSuccess = async () => {
    if (!selectedTournamentId || !paymentIntentId) return
    try {
      await tournamentsApi.confirmRegistrationPayment(
        selectedTournamentId,
        paymentIntentId,
        true
      )
      setPaymentClientSecret(null)
      setPaymentIntentId(null)
      queryClient.invalidateQueries({ queryKey: ['tournament-players', selectedTournamentId] })
      toast.success('Payment confirmed! You are registered.')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Confirmation failed')
    }
  }

  const alreadyRegistered = selectedPlayerId && tournamentPlayers.some(
    (p: { player_id: string }) => p.player_id === selectedPlayerId
  )

  return (
    <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4 md:p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-2">📋 Tournament Registration</h1>
        <p className="text-slate-400 mb-6">Register for open tournaments. Pay entry fee if required, or join the waitlist when full.</p>

        <div className="space-y-6">
          <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
            <label className="block text-sm font-medium text-slate-200 mb-2">Tournament</label>
            <select
              value={selectedTournamentId || ''}
              onChange={(e) => {
                setSelectedTournamentId(e.target.value || null)
                setPaymentClientSecret(null)
                setPaymentIntentId(null)
              }}
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
            >
              <option value="">Select tournament</option>
              {openTournaments.map((t: Tournament) => (
                <option key={t.tournament_id} value={t.tournament_id}>
                  {t.tournament_name} — {t.actual_players}/{t.max_players} players
                  {regSettings.entry_fee_cents > 0 && selectedTournamentId === t.tournament_id
                    ? ` — $${entryFeeDollars}`
                    : ''}
                </option>
              ))}
            </select>
          </div>

          {selectedTournamentId && (
            <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
              <label className="block text-sm font-medium text-slate-200 mb-2">Register as</label>
              <select
                value={selectedPlayerId || ''}
                onChange={(e) => setSelectedPlayerId(e.target.value || null)}
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
              >
                <option value="">Select player</option>
                {players.map((p) => (
                  <option key={p.player_id} value={p.player_id}>
                    {p.first_name} {p.last_name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {paymentClientSecret && selectedTournamentId && paymentIntentId ? (
            <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
              <p className="text-slate-300 mb-4">Pay ${entryFeeDollars} to complete registration.</p>
              <TournamentPaymentForm
                clientSecret={paymentClientSecret}
                intentId={paymentIntentId}
                tournamentId={selectedTournamentId}
                onSuccess={handlePaymentSuccess}
                onCancel={() => {
                  setPaymentClientSecret(null)
                  setPaymentIntentId(null)
                }}
              />
            </div>
          ) : (
            selectedTournamentId &&
            selectedPlayerId &&
            !alreadyRegistered && (
              <div className="flex gap-2">
                <button
                  onClick={handleRegister}
                  disabled={registerMutation.isPending || waitlistMutation.isPending || paymentIntentMutation.isPending}
                  className="px-4 py-2 rounded-lg bg-sky-600 text-white font-medium hover:bg-sky-500 disabled:opacity-50"
                >
                  {isFull
                    ? 'Join waitlist'
                    : entryFeeCents > 0
                      ? `Pay $${entryFeeDollars} & register`
                      : 'Register'}
                </button>
              </div>
            )
          )}

          {alreadyRegistered && (
            <p className="text-amber-400">This player is already registered for this tournament.</p>
          )}
        </div>
      </div>
    </div>
  )
}

function TournamentPaymentForm({
  clientSecret,
  intentId,
  tournamentId,
  onSuccess,
  onCancel,
}: {
  clientSecret: string
  intentId: string
  tournamentId: string
  onSuccess: () => void
  onCancel: () => void
}) {
  const [stripePromise, setStripePromise] = useState<ReturnType<typeof loadStripe> | null>(null)
  useEffect(() => {
    const key = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || ''
    setStripePromise(key ? loadStripe(key) : null)
  }, [])
  if (!stripePromise) return <p className="text-slate-400">Loading payment...</p>
  return (
    <Elements
      stripe={stripePromise}
      options={{
        clientSecret,
        appearance: { theme: 'night', variables: { colorPrimary: '#0ea5e9' } },
      }}
    >
      <TournamentPaymentFormInner
        intentId={intentId}
        tournamentId={tournamentId}
        onSuccess={onSuccess}
        onCancel={onCancel}
      />
    </Elements>
  )
}

function TournamentPaymentFormInner({
  intentId,
  tournamentId,
  onSuccess,
  onCancel,
}: {
  intentId: string
  tournamentId: string
  onSuccess: () => void
  onCancel: () => void
}) {
  const [error, setError] = useState<string | null>(null)
  const stripe = useStripe()
  const elements = useElements()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!stripe || !elements) return
    setError(null)
    const { error: err } = await stripe.confirmPayment({
      elements,
      confirmParams: { return_url: window.location.href },
    })
    if (err) {
      setError(err.message ?? 'Payment failed')
      return
    }
    try {
      await tournamentsApi.confirmRegistrationPayment(tournamentId, intentId, true)
      onSuccess()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Confirmation failed')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <PaymentElement options={{ layout: 'tabs' }} />
      {error && <p className="text-red-400 text-sm">{error}</p>}
      <div className="flex gap-2">
        <button type="button" onClick={onCancel} className="px-4 py-2 rounded-lg bg-slate-600 text-slate-200 hover:bg-slate-500">
          Cancel
        </button>
        <button type="submit" disabled={!stripe} className="px-4 py-2 rounded-lg bg-sky-600 text-white hover:bg-sky-500 disabled:opacity-50">
          Pay now
        </button>
      </div>
    </form>
  )
}
