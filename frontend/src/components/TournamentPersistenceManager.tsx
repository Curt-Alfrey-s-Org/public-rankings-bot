/**
 * Tournament Persistence Manager Component
 * Provides UI for managing saved tournament configurations and persistence settings
 */

import { useState } from 'react'
import { SavedTournament, PersistenceSettings } from '@/lib/tournamentPersistence'
import {
  useSavedTournaments,
  useDeleteTournament,
  useExportTournament,
  useImportTournament,
  usePersistenceSettings,
  useClearAllTournamentData
} from '@/hooks/useTournamentPersistence'
import { testCenterLogger } from '@/lib/testCenterLogger'
import './TournamentPersistenceManager.css'

interface TournamentPersistenceManagerProps {
  isOpen: boolean
  onClose: () => void
  onLoadTournament?: (tournament: SavedTournament) => void
  currentTournamentState?: any
}

export default function TournamentPersistenceManager({
  isOpen,
  onClose,
  onLoadTournament,
  currentTournamentState
}: TournamentPersistenceManagerProps) {
  const [activeTab, setActiveTab] = useState<'saved' | 'settings'>('saved')
  const [saveName, setSaveName] = useState('')
  const [saveDescription, setSaveDescription] = useState('')
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [importData, setImportData] = useState('')
  const [showImportDialog, setShowImportDialog] = useState(false)

  const { data: savedTournaments = [], isLoading: loadingTournaments } = useSavedTournaments()
  const { settings, updateSettings, isUpdating } = usePersistenceSettings()

  const deleteMutation = useDeleteTournament()
  const exportMutation = useExportTournament()
  const importMutation = useImportTournament()
  const clearAllMutation = useClearAllTournamentData()

  if (!isOpen) return null

  const handleSaveCurrent = () => {
    if (!currentTournamentState) return

    // This would trigger the save mutation from the parent component
    // The actual save logic is handled in the TestCenter component
    testCenterLogger.userInteraction('save_current_tournament_requested', {
      tournamentName: saveName || currentTournamentState.tournamentSetup?.name
    })
    setShowSaveDialog(false)
    setSaveName('')
    setSaveDescription('')
  }

  const handleLoadTournament = (tournament: SavedTournament) => {
    if (onLoadTournament) {
      onLoadTournament(tournament)
      testCenterLogger.userInteraction('load_tournament_requested', {
        tournamentId: tournament.id,
        tournamentName: tournament.name
      })
      onClose()
    }
  }

  const handleDeleteTournament = (id: string) => {
    if (confirm('Are you sure you want to delete this tournament? This action cannot be undone.')) {
      deleteMutation.mutate(id)
    }
  }

  const handleExportTournament = (id: string) => {
    exportMutation.mutate(id)
  }

  const handleImportTournament = () => {
    if (importData.trim()) {
      importMutation.mutate(importData)
      setImportData('')
      setShowImportDialog(false)
    }
  }

  const handleClearAllData = () => {
    if (confirm('Are you sure you want to clear ALL saved tournament data? This action cannot be undone.')) {
      clearAllMutation.mutate()
    }
  }

  const handleSettingsChange = (key: keyof PersistenceSettings, value: any) => {
    if (settings) {
      updateSettings({ [key]: value })
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const getTournamentStatus = (tournament: SavedTournament) => {
    const step = tournament.state.currentStep
    switch (step) {
      case 'setup': return 'Not Started'
      case 'registration': return 'Registration Open'
      case 'brackets': return 'Bracket Setup'
      case 'matches': return 'In Progress'
      case 'results': return 'Completed'
      default: return 'Unknown'
    }
  }

  return (
    <div className="persistence-modal-overlay">
      <div className="persistence-modal">
        <div className="persistence-modal-header">
          <h2>🏆 Tournament Persistence Manager</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="persistence-modal-tabs">
          <button
            className={`tab-button ${activeTab === 'saved' ? 'active' : ''}`}
            onClick={() => setActiveTab('saved')}
          >
            💾 Saved Tournaments ({savedTournaments.length})
          </button>
          <button
            className={`tab-button ${activeTab === 'settings' ? 'active' : ''}`}
            onClick={() => setActiveTab('settings')}
          >
            ⚙️ Settings
          </button>
        </div>

        <div className="persistence-modal-content">
          {activeTab === 'saved' && (
            <div className="saved-tournaments-tab">
              <div className="tab-header">
                <h3>Saved Tournament Configurations</h3>
                <div className="tab-actions">
                  <button
                    className="action-button primary"
                    onClick={() => setShowSaveDialog(true)}
                    disabled={!currentTournamentState}
                  >
                    💾 Save Current
                  </button>
                  <button
                    className="action-button secondary"
                    onClick={() => setShowImportDialog(true)}
                  >
                    📥 Import
                  </button>
                  <button
                    className="action-button danger"
                    onClick={handleClearAllData}
                    disabled={clearAllMutation.isPending}
                  >
                    🗑️ Clear All
                  </button>
                </div>
              </div>

              {loadingTournaments ? (
                <div className="loading-state">Loading saved tournaments...</div>
              ) : savedTournaments.length === 0 ? (
                <div className="empty-state">
                  <p>No saved tournaments found.</p>
                  <p>Create and save tournament configurations to see them here.</p>
                </div>
              ) : (
                <div className="tournaments-list">
                  {savedTournaments.map((tournament) => (
                    <div key={tournament.id} className="tournament-item">
                      <div className="tournament-info">
                        <h4>{tournament.name}</h4>
                        {tournament.description && (
                          <p className="tournament-description">{tournament.description}</p>
                        )}
                        <div className="tournament-meta">
                          <span className="meta-item">
                            Status: {getTournamentStatus(tournament)}
                          </span>
                          <span className="meta-item">
                            Players: {tournament.state.tournamentSetup.maxPlayers}
                          </span>
                          <span className="meta-item">
                            Format: {tournament.state.tournamentSetup.format.replace('_', ' ')}
                          </span>
                          <span className="meta-item">
                            Created: {formatDate(tournament.createdAt)}
                          </span>
                          <span className="meta-item">
                            Last Accessed: {formatDate(tournament.lastAccessedAt)}
                          </span>
                        </div>
                      </div>
                      <div className="tournament-actions">
                        <button
                          className="action-button small primary"
                          onClick={() => handleLoadTournament(tournament)}
                        >
                          📂 Load
                        </button>
                        <button
                          className="action-button small secondary"
                          onClick={() => handleExportTournament(tournament.id)}
                          disabled={exportMutation.isPending}
                        >
                          📤 Export
                        </button>
                        <button
                          className="action-button small danger"
                          onClick={() => handleDeleteTournament(tournament.id)}
                          disabled={deleteMutation.isPending}
                        >
                          🗑️ Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'settings' && (
            <div className="settings-tab">
              <h3>Persistence Settings</h3>

              {settings && (
                <div className="settings-form">
                  <div className="setting-group">
                    <label className="setting-item">
                      <input
                        type="checkbox"
                        checked={settings.autoSave}
                        onChange={(e) => handleSettingsChange('autoSave', e.target.checked)}
                        disabled={isUpdating}
                      />
                      <div className="setting-info">
                        <span className="setting-label">Auto-save current tournament</span>
                        <span className="setting-description">
                          Automatically save tournament state as you work
                        </span>
                      </div>
                    </label>
                  </div>

                  <div className="setting-group">
                    <label className="setting-item">
                      <span className="setting-label">Storage Type</span>
                      <select
                        value={settings.storageType}
                        onChange={(e) => handleSettingsChange('storageType', e.target.value)}
                        disabled={isUpdating}
                        className="setting-select"
                      >
                        <option value="indexeddb">IndexedDB (Recommended)</option>
                        <option value="localstorage">LocalStorage (Fallback)</option>
                      </select>
                      <span className="setting-description">
                        IndexedDB provides better performance and storage capacity
                      </span>
                    </label>
                  </div>

                  <div className="setting-group">
                    <label className="setting-item">
                      <span className="setting-label">Max Saved Tournaments</span>
                      <input
                        type="number"
                        min="1"
                        max="50"
                        value={settings.maxSavedTournaments}
                        onChange={(e) => handleSettingsChange('maxSavedTournaments', parseInt(e.target.value))}
                        disabled={isUpdating}
                        className="setting-input"
                      />
                      <span className="setting-description">
                        Automatically delete oldest tournaments when limit is reached
                      </span>
                    </label>
                  </div>

                  <div className="setting-group">
                    <label className="setting-item">
                      <input
                        type="checkbox"
                        checked={settings.enableCompression}
                        onChange={(e) => handleSettingsChange('enableCompression', e.target.checked)}
                        disabled={isUpdating}
                      />
                      <div className="setting-info">
                        <span className="setting-label">Enable data compression</span>
                        <span className="setting-description">
                          Compress tournament data to save storage space (experimental)
                        </span>
                      </div>
                    </label>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Save Current Tournament Dialog */}
        {showSaveDialog && (
          <div className="dialog-overlay">
            <div className="dialog">
              <h3>💾 Save Current Tournament</h3>
              <div className="dialog-content">
                <div className="form-group">
                  <label>Name</label>
                  <input
                    type="text"
                    value={saveName}
                    onChange={(e) => setSaveName(e.target.value)}
                    placeholder={currentTournamentState?.tournamentSetup?.name || 'Tournament name'}
                    className="dialog-input"
                  />
                </div>
                <div className="form-group">
                  <label>Description (optional)</label>
                  <textarea
                    value={saveDescription}
                    onChange={(e) => setSaveDescription(e.target.value)}
                    placeholder="Brief description of this tournament configuration"
                    className="dialog-textarea"
                    rows={3}
                  />
                </div>
              </div>
              <div className="dialog-actions">
                <button
                  className="dialog-button secondary"
                  onClick={() => setShowSaveDialog(false)}
                >
                  Cancel
                </button>
                <button
                  className="dialog-button primary"
                  onClick={handleSaveCurrent}
                  disabled={!saveName.trim()}
                >
                  💾 Save
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Import Tournament Dialog */}
        {showImportDialog && (
          <div className="dialog-overlay">
            <div className="dialog">
              <h3>📥 Import Tournament</h3>
              <div className="dialog-content">
                <div className="form-group">
                  <label>JSON Data</label>
                  <textarea
                    value={importData}
                    onChange={(e) => setImportData(e.target.value)}
                    placeholder="Paste exported tournament JSON data here"
                    className="dialog-textarea"
                    rows={10}
                  />
                </div>
                <div className="import-info">
                  <p><strong>Expected format:</strong> JSON data exported from the Tournament Persistence Manager</p>
                  <p><strong>Note:</strong> Imported tournaments will get a new ID to avoid conflicts</p>
                </div>
              </div>
              <div className="dialog-actions">
                <button
                  className="dialog-button secondary"
                  onClick={() => setShowImportDialog(false)}
                >
                  Cancel
                </button>
                <button
                  className="dialog-button primary"
                  onClick={handleImportTournament}
                  disabled={!importData.trim()}
                >
                  📥 Import
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}