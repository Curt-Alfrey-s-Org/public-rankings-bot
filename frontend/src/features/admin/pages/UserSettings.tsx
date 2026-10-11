/**
 * User Settings - Profile, change password (admin/super_admin), and notification preferences.
 * API keys and Payment method are under Settings > Admin.
 */

import { NotificationPreferences } from '../components/NotificationPreferences'
import { ProfileSettings } from '../components/ProfileSettings'
import { ChangePasswordSettings } from '../components/ChangePasswordSettings'
import { EmailVerificationSettings } from '../components/EmailVerificationSettings'

export function UserSettings() {
  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-bold text-white">User Settings</h1>
        <p className="mt-1 text-slate-400">
          Manage your profile, password, and notification preferences.
        </p>
        <p className="mt-3 text-sm text-slate-500 max-w-2xl">
          Use the cards below to view your profile, verify your email, change your password, and control how you are notified (e.g. when a player&apos;s ranking changes). Changes are saved when you click Save or update the relevant field.
        </p>
      </header>

      <div className="grid gap-6 sm:grid-cols-1 lg:grid-cols-2">
        <div title="View your account role and profile details. Your role determines which features you can access.">
          <ProfileSettings />
        </div>
        <div title="Choose how and when you receive notifications (e.g. email when a player's ranking changes). Enable or disable each type and save.">
          <NotificationPreferences />
        </div>
        <div title="View email verification status and resend verification email.">
          <EmailVerificationSettings />
        </div>
        <div className="lg:col-span-2" title="Change your login password.">
          <ChangePasswordSettings />
        </div>
      </div>
    </div>
  )
}
