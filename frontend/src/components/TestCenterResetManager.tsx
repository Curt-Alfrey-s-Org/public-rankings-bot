/**
 * Test Center Reset Manager
 * Comprehensive reset and cleanup functionality for TestCenter
 */

import React, { useState, useEffect } from 'react'
import { useTestCenterReset, useResetUI, ResetType, SelectiveResetOptions } from '@/hooks/useTestCenterReset'
import { toast } from '@/lib/toast'
import './TestCenterResetManager.css'

interface TestCenterResetManagerProps {
  onResetComplete?: () => void
}

export default function TestCenterResetManager({ onResetComplete }: TestCenterResetManagerProps) {
  const { resetStatus, performReset, restoreFromBackup, getAvailableBackups, clearOldBackups } = useTestCenterReset()
  const { showConfirmDialog, pendingReset, requestReset, cancelReset, confirmReset } = useResetUI()

  const [selectiveOptions, setSelectiveOptions] = useState<SelectiveResetOptions>({
    keepSettings: true,
    keepSavedTournaments: false,
    clearApiCache: true,
    clearLocalStorage: true,
    clearIndexedDB: true
  })
  const [showSelectiveOptions, setShowSelectiveOptions] = useState(false)
  const [availableBackups, setAvailableBackups] = useState(getAvailableBackups())

  // Refresh backups list when needed
  useEffect(() => {
    setAvailableBackups(getAvailableBackups())
  }, [resetStatus.phase, getAvailableBackups])

  // Handle reset execution
  const handleResetExecute = async () => {
    const resetRequest = confirmReset()
    if (!resetRequest) return

    try {
      const result = await performReset(
        resetRequest.type,
        resetRequest.type === 'selective' ? selectiveOptions : undefined,
        resetRequest.skipBackup
      )

      if (result.success) {
        toast.success(`${resetRequest.type.charAt(0).toUpperCase() + resetRequest.type.slice(1)} reset completed successfully`)

        if (result.backupCreated && result.backupId) {
          toast.info(`Backup created: ${result.backupId}`)
        }

        // Refresh backups list
        setAvailableBackups(getAvailableBackups())

        onResetComplete?.()
      } else {
        toast.error(`Reset failed: ${result.errors.join(', ')}`)
      }
    } catch (error) {
      toast.error(`Reset operation failed: ${error.message}`)
    }
  }

  // Handle backup restoration
  const handleRestoreBackup = async (backupId: string) => {
    const confirmed = window.confirm(
      'Are you sure you want to restore from this backup? This will overwrite current data.'
    )

    if (!confirmed) return

    try {
      const success = await restoreFromBackup(backupId)
      if (success) {
        toast.success('Backup restored successfully')
        onResetComplete?.()
      } else {
        toast.error('Failed to restore backup')
      }
    } catch (error) {
      toast.error(`Restore failed: ${error.message}`)
    }
  }

  // Get reset type description and warnings
  const getResetInfo = (type: ResetType) => {
    switch (type) {
      case 'workflow':
        return {
          title: 'Reset Tournament Workflow',
          description: 'Reset the current tournament back to the setup step',
          warning: 'This will clear your current tournament progress and return to the beginning of the workflow.',
          dangerLevel: 'low' as const,
          icon: '🔄'
        }
      case 'database':
        return {
          title: 'Clear Database Data',
          description: 'Remove all test tournament data from the database',
          warning: 'This will permanently delete all tournament, player, match, and leaderboard data from the test database.',
          dangerLevel: 'high' as const,
          icon: '🗄️'
        }
      case 'cache':
        return {
          title: 'Clear Cached Data',
          description: 'Clear all cached data, localStorage, and IndexedDB',
          warning: 'This will clear all cached tournament data, saved tournaments, and local browser storage.',
          dangerLevel: 'medium' as const,
          icon: '🧹'
        }
      case 'factory':
        return {
          title: 'Factory Reset',
          description: 'Complete reset to initial TestCenter state',
          warning: 'This will perform a complete reset of all TestCenter data and return it to its initial state. All data will be lost.',
          dangerLevel: 'critical' as const,
          icon: '🏭'
        }
      case 'selective':
        return {
          title: 'Selective Reset',
          description: 'Choose specific data to clear while preserving others',
          warning: 'Configure which data to clear and what to preserve.',
          dangerLevel: 'medium' as const,
          icon: '🎯'
        }
      default:
        return {
          title: 'Unknown Reset',
          description: 'Unknown reset type',
          warning: 'Unknown reset operation',
          dangerLevel: 'low' as const,
          icon: '❓'
        }
    }
  }

  const resetInfo = pendingReset ? getResetInfo(pendingReset.type) : null

  return (
    <div className="reset-manager">
      <div className="reset-header">
        <h3>🛠️ TestCenter Reset & Cleanup</h3>
        <p>Safe and comprehensive reset functionality for TestCenter data and state</p>
      </div>

      {/* Reset Status */}
      {resetStatus.phase !== 'idle' && (
        <div className="reset-status">
          <div className="status-header">
            <span className="status-icon">
              {resetStatus.phase === 'completed' ? '✅' :
               resetStatus.phase === 'failed' ? '❌' :
               resetStatus.phase === 'executing' ? '⚡' :
               resetStatus.phase === 'backing_up' ? '💾' : '⏳'}
            </span>
            <span className="status-title">
              {resetStatus.phase === 'confirming' ? 'Confirming Reset' :
               resetStatus.phase === 'backing_up' ? 'Creating Backup' :
               resetStatus.phase === 'executing' ? 'Executing Reset' :
               resetStatus.phase === 'completed' ? 'Reset Complete' :
               resetStatus.phase === 'failed' ? 'Reset Failed' : 'Ready'}
            </span>
            <span className="status-progress">{resetStatus.progress}%</span>
          </div>

          <div className="progress-bar">
            <div
              className={`progress-fill ${resetStatus.phase}`}
              style={{ width: `${resetStatus.progress}%` }}
            />
          </div>

          <p className="status-message">{resetStatus.message}</p>

          {resetStatus.error && (
            <div className="status-error">
              <strong>Error:</strong> {resetStatus.error}
            </div>
          )}

          {resetStatus.startTime && resetStatus.endTime && (
            <div className="status-timing">
              Duration: {((resetStatus.endTime.getTime() - resetStatus.startTime.getTime()) / 1000).toFixed(1)}s
            </div>
          )}
        </div>
      )}

      {/* Reset Options */}
      <div className="reset-options">
        <h4>Reset Options</h4>

        <div className="reset-buttons">
          <button
            className="reset-btn workflow"
            onClick={() => requestReset('workflow')}
            disabled={resetStatus.phase !== 'idle'}
          >
            <span className="btn-icon">🔄</span>
            <span className="btn-text">Reset Workflow</span>
            <span className="btn-desc">Back to setup step</span>
          </button>

          <button
            className="reset-btn database"
            onClick={() => requestReset('database')}
            disabled={resetStatus.phase !== 'idle'}
          >
            <span className="btn-icon">🗄️</span>
            <span className="btn-text">Clear Database</span>
            <span className="btn-desc">Remove all test data</span>
          </button>

          <button
            className="reset-btn cache"
            onClick={() => requestReset('cache')}
            disabled={resetStatus.phase !== 'idle'}
          >
            <span className="btn-icon">🧹</span>
            <span className="btn-text">Clear Cache</span>
            <span className="btn-desc">Clear cached data</span>
          </button>

          <button
            className="reset-btn factory"
            onClick={() => requestReset('factory')}
            disabled={resetStatus.phase !== 'idle'}
          >
            <span className="btn-icon">🏭</span>
            <span className="btn-text">Factory Reset</span>
            <span className="btn-desc">Complete reset</span>
          </button>

          <button
            className="reset-btn selective"
            onClick={() => setShowSelectiveOptions(!showSelectiveOptions)}
            disabled={resetStatus.phase !== 'idle'}
          >
            <span className="btn-icon">🎯</span>
            <span className="btn-text">Selective Reset</span>
            <span className="btn-desc">Custom options</span>
          </button>
        </div>

        {/* Selective Reset Options */}
        {showSelectiveOptions && (
          <div className="selective-options">
            <h5>Selective Reset Options</h5>

            <div className="option-group">
              <label className="option-checkbox">
                <input
                  type="checkbox"
                  checked={selectiveOptions.keepSettings}
                  onChange={(e) => setSelectiveOptions(prev => ({
                    ...prev,
                    keepSettings: e.target.checked
                  }))}
                />
                <span>Keep persistence settings</span>
              </label>

              <label className="option-checkbox">
                <input
                  type="checkbox"
                  checked={selectiveOptions.keepSavedTournaments}
                  onChange={(e) => setSelectiveOptions(prev => ({
                    ...prev,
                    keepSavedTournaments: e.target.checked
                  }))}
                />
                <span>Keep saved tournaments</span>
              </label>
            </div>

            <div className="option-group">
              <h6>Data to Clear:</h6>

              <label className="option-checkbox">
                <input
                  type="checkbox"
                  checked={selectiveOptions.clearApiCache}
                  onChange={(e) => setSelectiveOptions(prev => ({
                    ...prev,
                    clearApiCache: e.target.checked
                  }))}
                />
                <span>API cache (React Query)</span>
              </label>

              <label className="option-checkbox">
                <input
                  type="checkbox"
                  checked={selectiveOptions.clearLocalStorage}
                  onChange={(e) => setSelectiveOptions(prev => ({
                    ...prev,
                    clearLocalStorage: e.target.checked
                  }))}
                />
                <span>LocalStorage data</span>
              </label>

              <label className="option-checkbox">
                <input
                  type="checkbox"
                  checked={selectiveOptions.clearIndexedDB}
                  onChange={(e) => setSelectiveOptions(prev => ({
                    ...prev,
                    clearIndexedDB: e.target.checked
                  }))}
                />
                <span>IndexedDB data</span>
              </label>
            </div>

            <div className="selective-actions">
              <button
                className="action-btn primary"
                onClick={() => requestReset('selective', selectiveOptions)}
                disabled={resetStatus.phase !== 'idle'}
              >
                Execute Selective Reset
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Backup Management */}
      <div className="backup-section">
        <h4>💾 Backup Management</h4>

        <div className="backup-info">
          <p>Backups are automatically created before most reset operations for safety.</p>

          {availableBackups.length > 0 ? (
            <div className="backups-list">
              <h5>Available Backups ({availableBackups.length})</h5>
              {availableBackups.slice(0, 5).map(backup => (
                <div key={backup.id} className="backup-item">
                  <div className="backup-info">
                    <span className="backup-type">{backup.type}</span>
                    <span className="backup-date">
                      {new Date(backup.createdAt).toLocaleString()}
                    </span>
                    <span className="backup-operations">
                      {backup.operations.join(', ')}
                    </span>
                  </div>
                  <button
                    className="restore-btn"
                    onClick={() => handleRestoreBackup(backup.id)}
                    disabled={resetStatus.phase !== 'idle'}
                  >
                    Restore
                  </button>
                </div>
              ))}

              {availableBackups.length > 5 && (
                <p className="more-backups">... and {availableBackups.length - 5} more</p>
              )}

              <div className="backup-actions">
                <button
                  className="action-btn secondary small"
                  onClick={() => clearOldBackups(3)}
                  disabled={resetStatus.phase !== 'idle'}
                >
                  Keep Only Last 3
                </button>
              </div>
            </div>
          ) : (
            <p className="no-backups">No backups available</p>
          )}
        </div>
      </div>

      {/* Safety Notice */}
      <div className="safety-notice">
        <h4>🛡️ Safety Information</h4>
        <ul>
          <li><strong>Backups:</strong> Automatic backups are created before destructive operations</li>
          <li><strong>Isolation:</strong> TestCenter data is separate from live tournament data</li>
          <li><strong>Recovery:</strong> Use backups to restore previous states if needed</li>
          <li><strong>Confirmation:</strong> All reset operations require explicit confirmation</li>
        </ul>
      </div>

      {/* Confirmation Dialog */}
      {showConfirmDialog && resetInfo && (
        <div className="confirm-dialog-overlay">
          <div className="confirm-dialog">
            <div className="dialog-header">
              <span className="dialog-icon">{resetInfo.icon}</span>
              <h3>{resetInfo.title}</h3>
            </div>

            <div className="dialog-content">
              <p className="dialog-description">{resetInfo.description}</p>

              <div className={`warning-box ${resetInfo.dangerLevel}`}>
                <strong>⚠️ Warning:</strong> {resetInfo.warning}
              </div>

              <div className="backup-notice">
                <p><strong>Backup:</strong> A backup will be created automatically before this operation.</p>
                {pendingReset?.skipBackup && (
                  <p className="skip-backup-warning">
                    ⚠️ Backup creation is disabled for this operation.
                  </p>
                )}
              </div>

              {pendingReset?.type === 'selective' && (
                <div className="selective-preview">
                  <h5>Selective Reset Preview:</h5>
                  <ul>
                    {selectiveOptions.keepSettings && <li>✓ Keep persistence settings</li>}
                    {selectiveOptions.keepSavedTournaments && <li>✓ Keep saved tournaments</li>}
                    {selectiveOptions.clearApiCache && <li>✗ Clear API cache</li>}
                    {selectiveOptions.clearLocalStorage && <li>✗ Clear LocalStorage</li>}
                    {selectiveOptions.clearIndexedDB && <li>✗ Clear IndexedDB</li>}
                  </ul>
                </div>
              )}
            </div>

            <div className="dialog-actions">
              <button
                className="dialog-btn cancel"
                onClick={cancelReset}
              >
                Cancel
              </button>

              <button
                className="dialog-btn confirm"
                onClick={handleResetExecute}
              >
                {pendingReset?.skipBackup ? 'Reset Without Backup' : 'Create Backup & Reset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}