/**
 * PaymentCheckout - Stripe payment flow for AI Coach 1-hour pass
 * @module features/ai-coach/components/PaymentCheckout
 */

import { useState, useEffect } from 'react'
import { loadStripe } from '@stripe/stripe-js'
import type { Stripe } from '@stripe/stripe-js'
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js'
import {
  usePaymentIntent,
  useConfirmPayment,
} from '../hooks'
import type { PaymentIntentResponse } from '@/features/ai-coach/types/api'

const DEFAULT_AMOUNT_CENTS = 999

/** Inner form that uses Stripe hooks */
function PaymentForm({
  intentId,
  onSuccess,
  onError,
}: {
  intentId: string
  onSuccess: () => void
  onError: (msg: string) => void
}) {
  const stripe = useStripe()
  const elements = useElements()
  const { mutate: confirmPayment, isPending: isConfirming } = useConfirmPayment({
    onSuccess: () => onSuccess(),
    onError: (err) => onError(err instanceof Error ? err.message : 'Confirmation failed'),
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!stripe || !elements) return
    const { error } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: window.location.href,
      },
    })
    if (error) {
      onError(error.message ?? 'Payment failed')
      return
    }
    // Stripe confirmed; now tell our backend to record success and add hours
    confirmPayment({ payment_intent_id: intentId })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <PaymentElement
        options={{
          layout: 'tabs',
        }}
      />
      <button
        type="submit"
        disabled={!stripe || isConfirming}
        className="w-full rounded-lg bg-sky-600 px-4 py-2 font-medium text-white hover:bg-sky-500 disabled:opacity-50"
      >
        {isConfirming ? 'Confirming...' : 'Pay now'}
      </button>
    </form>
  )
}

/** Main PaymentCheckout component */
function PaymentCheckoutInner({
  stripePromise,
}: {
  stripePromise: Promise<Stripe | null> | null
}) {
  const [amountCents, setAmountCents] = useState(DEFAULT_AMOUNT_CENTS)
  const [intentData, setIntentData] = useState<PaymentIntentResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const { mutate: createIntent, isPending: isCreating } = usePaymentIntent({
    onSuccess: (data) => setIntentData(data),
    onError: (err) => setError(err instanceof Error ? err.message : 'Failed to create payment'),
  })

  const handleCreateIntent = () => {
    setError(null)
    setIntentData(null)
    createIntent({ amount_cents: amountCents, hours: 1 })
  }

  const handleSuccess = () => {
    setSuccess(true)
    setIntentData(null)
  }

  if (success) {
    return (
      <div className="rounded-lg border border-green-800 bg-green-900/20 p-4 text-green-200">
        Payment successful. Your AI Coach hours have been added.
      </div>
    )
  }

  return (
    <div className="space-y-4 rounded-lg border border-slate-700 bg-slate-800/50 p-4">
      <h3 className="text-lg font-semibold text-sky-400">Purchase 1-Hour AI Coach Pass</h3>

      {!intentData ? (
        <>
          <div>
            <label htmlFor="amount" className="block text-sm font-medium text-slate-300">
              Amount (cents)
            </label>
            <input
              id="amount"
              type="number"
              min={100}
              max={99999}
              value={amountCents}
              onChange={(e) => setAmountCents(Number(e.target.value) || 100)}
              className="mt-1 w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-white"
            />
            <p className="mt-1 text-xs text-slate-500">Default: $9.99 (999 cents)</p>
          </div>

          {error && (
            <div className="rounded-md border border-red-800 bg-red-900/30 p-3 text-sm text-red-200">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={handleCreateIntent}
            disabled={isCreating}
            className="rounded-lg bg-sky-600 px-4 py-2 font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          >
            {isCreating ? 'Creating...' : 'Proceed to payment'}
          </button>
        </>
      ) : (
        <Elements
          stripe={stripePromise}
          options={{
            clientSecret: intentData.client_secret,
            appearance: {
              theme: 'night',
              variables: { colorPrimary: '#0ea5e9' },
            },
          }}
        >
          <PaymentForm
            intentId={intentData.intent_id}
            onSuccess={handleSuccess}
            onError={setError}
          />
        </Elements>
      )}

      {error && intentData && (
        <div className="rounded-md border border-red-800 bg-red-900/30 p-3 text-sm text-red-200">
          {error}
        </div>
      )}
    </div>
  )
}

/** Wrapper to load Stripe provider */
export default function PaymentCheckout() {
  const [stripePromise, setStripePromise] = useState<Promise<Stripe | null> | null>(null)

  useEffect(() => {
    const key = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || 'pk_test_placeholder'
    setStripePromise(loadStripe(key))
  }, [])

  if (!stripePromise) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4 text-slate-400">
        Loading payment...
      </div>
    )
  }

  return <PaymentCheckoutInner stripePromise={stripePromise} />
}
