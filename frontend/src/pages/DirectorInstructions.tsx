/**
 * Director Instructions — How it works for Tournament Directors.
 * WPBA/WPA-based overview, official sources, roles, and key rules.
 */

import { Link } from 'react-router-dom'

export default function DirectorInstructions() {
  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-foreground">How it works</h1>
      <p className="text-muted-foreground">
        A quick reference for Tournament Directors using Pro Billiards Software.
      </p>

      <section className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">Overview</h2>
        <p className="text-sm text-muted-foreground">
          Use the Tournament Director tools to enter rankings and tournament data, manage brackets, run timers, and enter scores. The system supports WPBA and WPA formats and rules.
        </p>
      </section>

      <section className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">Official sources</h2>
        <ul className="space-y-2 text-sm text-muted-foreground">
          <li>
            <strong className="text-foreground">WPBA:</strong>{' '}
            <a href="https://wpba.com/rules" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">wpba.com/rules</a>, events-official, rankings
          </li>
          <li>
            <strong className="text-foreground">WPA:</strong> World Pool-Billiard Association rules and regulations
          </li>
        </ul>
      </section>

      <section className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">Roles</h2>
        <ul className="space-y-2 text-sm text-muted-foreground">
          <li><strong className="text-foreground">Director:</strong> Oversees bracket, tables, call table, DQ, assigns matches, enters scores</li>
          <li><strong className="text-foreground">Time keeper:</strong> Runs shot clock per table</li>
          <li><strong className="text-foreground">Score keeper:</strong> My table — enter scores and run timers for assigned table(s)</li>
        </ul>
        <p className="text-sm text-muted-foreground mt-2">
          Use <Link to="/director/bracket" className="text-primary hover:underline">Director mode</Link> for bracket and table management, and <Link to="/director/scorekeeper" className="text-primary hover:underline">Score keeper mode</Link> for per-table entry.
        </p>
      </section>

      <section className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">Before the tournament</h2>
        <ul className="space-y-1 text-sm text-muted-foreground list-disc list-inside">
          <li>Create the tournament via <Link to="/director/new" className="text-primary hover:underline">New Tournament</Link></li>
          <li>Enter or import rankings and player data in <Link to="/director/data-input" className="text-primary hover:underline">Data input</Link></li>
          <li>Manage players in <Link to="/director/players" className="text-primary hover:underline">Tournament Player Management</Link></li>
          <li>Configure shot clock and other settings before the event</li>
        </ul>
      </section>

      <section className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">On the day</h2>
        <ul className="space-y-1 text-sm text-muted-foreground list-disc list-inside">
          <li>Run bracket and call table from Director mode</li>
          <li>Assign score keepers to tables in Score keeper mode</li>
          <li>Enter match results as games complete</li>
          <li>Use shot clock for timed matches (see Key rules below)</li>
        </ul>
      </section>

      <section className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">Key rules</h2>
        <div className="space-y-3 text-sm text-muted-foreground">
          <div>
            <strong className="text-foreground">Shot clock (WPA Reg 19):</strong> 35 seconds per shot, warning at 10 seconds, one 25-second extension per rack.
          </div>
          <div>
            <strong className="text-foreground">3-foul rule (9-ball):</strong> Three consecutive fouls = loss of rack. Referee warns between 2nd and 3rd foul.
          </div>
          <div>
            <strong className="text-foreground">WPBA format:</strong> Double elimination, 64 players max, races to 8 (final to 10).
          </div>
        </div>
      </section>
    </div>
  )
}
