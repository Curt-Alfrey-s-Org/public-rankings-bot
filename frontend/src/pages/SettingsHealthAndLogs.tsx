/**
 * Settings > Health & logs: Health & monitoring section above, Logs section below.
 */

import { HealthDashboard } from '@/features/admin/pages/HealthDashboard'
import Logs from './Logs'

export default function SettingsHealthAndLogsPage() {
  return (
    <div className="flex flex-col gap-8">
      <section aria-label="Health & monitoring">
        <HealthDashboard />
      </section>
      <section aria-label="Logs" className="border-t border-border pt-6">
        <Logs embedded />
      </section>
    </div>
  )
}
