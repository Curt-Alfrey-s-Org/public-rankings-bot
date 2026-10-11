/**
 * Payment method / subscription status — styled to match Admin sections.
 */

import { Link } from 'react-router-dom'

export function PaymentMethod() {
  return (
    <section title="Add or update the payment method used for paid features (e.g. AI Coach).">
      <h3 className="text-sm font-semibold mb-2">Payment Method</h3>
      <p className="text-xs text-muted-foreground mb-3">
        Manage your AI Coach subscription and payment methods.
      </p>
      <Link
        to="/ai-coach"
        className="min-h-[44px] inline-flex items-center justify-center px-4 py-2.5 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
      >
        Go to AI Coach →
      </Link>
    </section>
  )
}
