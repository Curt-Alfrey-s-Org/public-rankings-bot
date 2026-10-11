/**
 * Settings > System & messages: System info above, Messages & alerts below.
 */

import System from './System'
import SettingsMessages from './SettingsMessages'

export default function SettingsSystemAndMessagesPage() {
  return (
    <div className="flex flex-col gap-8">
      <section aria-label="System">
        <System embedded />
      </section>
      <section aria-label="Messages & alerts" className="border-t border-border pt-6">
        <SettingsMessages />
      </section>
    </div>
  )
}
