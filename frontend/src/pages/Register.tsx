/**
 * Public self-service registration is temporarily disabled ("coming soon").
 * Pro (WPA) players are provisioned by admins/directors and sign in with the
 * username and temporary password issued by their tournament director.
 * The signup form returns when PUBLIC_REGISTRATION_ENABLED is turned on server-side.
 */

import { Link } from 'react-router-dom'

export default function Register() {
  return (
    <div className="min-h-[100dvh] flex flex-col items-center justify-center px-4 py-12 bg-slate-950 text-white">
      <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900/95 p-8 shadow-2xl">
        <p className="text-[11px] sm:text-xs text-center text-amber-200/85 uppercase tracking-wide mb-3">
          Pro Billiards Software
        </p>
        <h1 className="text-xl font-bold text-white text-center mb-3">Account creation coming soon</h1>
        <p className="text-slate-300 text-sm leading-relaxed mb-4">
          Self-service signup isn&apos;t open yet — we&apos;re putting the finishing touches on it.
          Please check back soon.
        </p>

        <div className="mb-6 rounded-lg border border-slate-600/80 bg-slate-800/50 p-3 text-xs text-slate-300 leading-relaxed space-y-2">
          <p>
            <strong className="text-slate-200">Professional (WPA) players:</strong> your account is
            already created from your WPA license. Sign in with the username and temporary password
            provided by your tournament director — you&apos;ll set your email and a new password on
            first login. If you don&apos;t have credentials yet, contact your TD.
          </p>
          <p>
            <strong className="text-slate-200">Everyone else:</strong> self-registration will open
            here later.
          </p>
        </div>

        <Link
          to="/"
          className="inline-flex items-center justify-center w-full rounded-lg bg-sky-600 hover:bg-sky-500 font-semibold text-white py-3 px-4 focus:outline-none focus:ring-2 focus:ring-sky-500"
        >
          Back to sign in
        </Link>
      </div>
    </div>
  )
}
