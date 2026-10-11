/**
 * Export/Import Manager Component
 * Provides comprehensive UI for managing tournament exports, imports, and sharing
 */

import { useState, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { exportImportService, TournamentExport, ScenarioExport, BulkExport } from '@/lib/exportImportService'
import { sharingUtils } from '@/lib/sharingUtils'
import { templateManager, TournamentTemplate } from '@/lib/tournamentTemplates'
import { TournamentWorkflowState } from '@/lib/tournamentPersistence'
import { testCenterLogger } from '@/lib/testCenterLogger'
import { toast } from '@/lib/toast'
import './ExportImportManager.css'

interface ExportImportManagerProps {
  isOpen: boolean
  onClose: () => void
  currentTournamentState?: TournamentWorkflowState
  onImportTournament?: (tournament: any) => void
  onLoadTemplate?: (template: TournamentTemplate) => void
}

type ActiveTab = 'export' | 'import' | 'templates' | 'bulk' | 'sharing'

interface ExportOptions {
  type: 'tournament' | 'scenario' | 'bulk' | 'template'
  includeFullData: boolean
  compress: boolean
  generateChecksum: boolean
}

interface ScenarioCreationData {
  name: string
  description: string
  testSequence: any[]
  expectedResults: any
}

export default function ExportImportManager({
  isOpen,
  onClose,
  currentTournamentState,
  onImportTournament,
  onLoadTemplate
}: ExportImportManagerProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>('export')
  const [exportOptions, setExportOptions] = useState<ExportOptions>({
    type: 'tournament',
    includeFullData: true,
    compress: false,
    generateChecksum: true
  })

  // Export states
  const [exportName, setExportName] = useState('')
  const [exportDescription, setExportDescription] = useState('')
  const [selectedItems, setSelectedItems] = useState<string[]>([])
  const [scenarioData, setScenarioData] = useState<ScenarioCreationData>({
    name: '',
    description: '',
    testSequence: [],
    expectedResults: {}
  })

  // Import states
  const [importData, setImportData] = useState('')
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importResults, setImportResults] = useState<any>(null)

  // Template states
  const [selectedTemplate, setSelectedTemplate] = useState<TournamentTemplate | null>(null)
  const [templateSearch, setTemplateSearch] = useState('')
  const [templateCategory, setTemplateCategory] = useState<string>('all')

  // Sharing states
  const [shareData, setShareData] = useState<any>(null)
  const [shareMethod, setShareMethod] = useState<'clipboard' | 'download' | 'qrcode'>('download')
  const [qrCodeUrl, setQrCodeUrl] = useState<string>('')

  // Mutations
  const exportMutation = useMutation({
    mutationFn: async (options: ExportOptions) => {
      switch (options.type) {
        case 'tournament':
          if (!currentTournamentState) throw new Error('No tournament to export')
          return await exportImportService.exportTournament(
            { state: currentTournamentState } as any,
            options
          )

        case 'scenario':
          if (!scenarioData.name || !scenarioData.testSequence.length) {
            throw new Error('Incomplete scenario data')
          }
          return await exportImportService.exportScenario(
            scenarioData.name,
            currentTournamentState || {} as TournamentWorkflowState,
            scenarioData.testSequence,
            scenarioData.expectedResults,
            options
          )

        case 'bulk':
          // This would need actual tournament/scenario data
          const mockItems: TournamentExport[] = []
          return await exportImportService.exportBulk(mockItems, exportName || 'Bulk Export', options)

        case 'template':
          if (!selectedTemplate) throw new Error('No template selected')
          return await exportImportService.exportTemplate(
            selectedTemplate.name,
            selectedTemplate.baseWorkflowState,
            {
              isTemplate: true,
              category: selectedTemplate.category,
              difficulty: selectedTemplate.difficulty,
              estimatedDuration: selectedTemplate.estimatedDuration,
              recommendedPlayers: selectedTemplate.recommendedPlayers,
              customizationHints: selectedTemplate.customizationHints,
              presetConfigurations: selectedTemplate.presetConfigurations
            },
            options
          )

        default:
          throw new Error('Unknown export type')
      }
    },
    onSuccess: (data) => {
      setShareData(data)
      toast.success(`${exportOptions.type} exported successfully`)
      testCenterLogger.userInteraction('export_completed', {
        type: exportOptions.type,
        name: exportName || data.metadata?.name
      })
    },
    onError: (error: any) => {
      toast.error(`Export failed: ${error.message}`)
      testCenterLogger.criticalError(error, {
        operation: 'export_mutation_failed',
        type: exportOptions.type
      })
    }
  })

  const importMutation = useMutation({
    mutationFn: async (jsonData: string) => {
      const data = JSON.parse(jsonData)

      switch (data.type) {
        case 'tournament':
          return await exportImportService.importTournament(jsonData)
        case 'scenario':
          return await exportImportService.importScenario(jsonData)
        case 'bulk':
          return await exportImportService.importBulk(jsonData)
        case 'template':
          return await exportImportService.importTemplate(jsonData)
        default:
          throw new Error(`Unknown import type: ${data.type}`)
      }
    },
    onSuccess: (result) => {
      setImportResults(result)
      if (result.success && result.importedId && onImportTournament) {
        // For tournament imports, notify parent
        toast.success('Import completed successfully')
      }
      testCenterLogger.userInteraction('import_completed', {
        type: result.metadata.type,
        success: result.success
      })
    },
    onError: (error: any) => {
      toast.error(`Import failed: ${error.message}`)
      testCenterLogger.criticalError(error, {
        operation: 'import_mutation_failed'
      })
    }
  })

  const shareMutation = useMutation({
    mutationFn: async ({ data, method }: { data: any; method: string }) => {
      return await sharingUtils.shareTournamentExport(data, {
        method: method as any,
        filename: `tournament_export_${new Date().toISOString().split('T')[0]}.json`
      })
    },
    onSuccess: (result, { method }) => {
      if (method === 'qrcode' && result.result) {
        setQrCodeUrl(result.result)
      }
      toast.success(`Shared via ${method}`)
      testCenterLogger.userInteraction('share_completed', {
        method,
        success: result.success
      })
    },
    onError: (error: any) => {
      toast.error(`Share failed: ${error.message}`)
      testCenterLogger.criticalError(error, {
        operation: 'share_mutation_failed',
        method: shareMethod
      })
    }
  })

  // Effects
  useEffect(() => {
    if (currentTournamentState?.tournamentSetup?.name) {
      setExportName(`${currentTournamentState.tournamentSetup.name} Export`)
    }
  }, [currentTournamentState])

  useEffect(() => {
    if (shareData && shareMethod === 'qrcode') {
      shareMutation.mutate({ data: shareData, method: 'qrcode' })
    }
  }, [shareData, shareMethod])

  // Handlers
  const handleExport = () => {
    if (!exportName.trim()) {
      toast.error('Please provide a name for the export')
      return
    }
    exportMutation.mutate(exportOptions)
  }

  const handleImport = () => {
    let jsonData = importData

    if (importFile) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const content = e.target?.result as string
        importMutation.mutate(content)
      }
      reader.readAsText(importFile)
    } else if (jsonData.trim()) {
      importMutation.mutate(jsonData)
    } else {
      toast.error('Please provide import data or select a file')
    }
  }

  const handleShare = (method: typeof shareMethod) => {
    if (!shareData) {
      toast.error('No data to share. Please export something first.')
      return
    }
    setShareMethod(method)
    if (method !== 'qrcode') {
      shareMutation.mutate({ data: shareData, method })
    }
  }

  const handleLoadTemplate = (template: TournamentTemplate) => {
    if (onLoadTemplate) {
      onLoadTemplate(template)
      toast.success(`Template "${template.name}" loaded`)
      testCenterLogger.userInteraction('template_loaded', {
        templateId: template.id,
        templateName: template.name
      })
    }
  }

  const filteredTemplates = templateManager.getAllTemplates().filter(template => {
    const matchesSearch = template.name.toLowerCase().includes(templateSearch.toLowerCase()) ||
                         template.description.toLowerCase().includes(templateSearch.toLowerCase()) ||
                         template.tags.some(tag => tag.toLowerCase().includes(templateSearch.toLowerCase()))

    const matchesCategory = templateCategory === 'all' || template.category === templateCategory

    return matchesSearch && matchesCategory
  })

  if (!isOpen) return null

  return (
    <div className="export-import-modal-overlay">
      <div className="export-import-modal">
        <div className="modal-header">
          <h2>📤📥 Export/Import Manager</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="modal-tabs">
          {[
            { id: 'export', label: 'Export', icon: '📤' },
            { id: 'import', label: 'Import', icon: '📥' },
            { id: 'templates', label: 'Templates', icon: '📋' },
            { id: 'bulk', label: 'Bulk Operations', icon: '📦' },
            { id: 'sharing', label: 'Sharing', icon: '🔗' }
          ].map(tab => (
            <button
              key={tab.id}
              className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id as ActiveTab)}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>

        <div className="modal-content">
          {activeTab === 'export' && (
            <div className="export-tab">
              <h3>Export Tournament Data</h3>

              <div className="form-group">
                <label>Export Type</label>
                <select
                  value={exportOptions.type}
                  onChange={(e) => setExportOptions(prev => ({ ...prev, type: e.target.value as any }))}
                  className="form-select"
                >
                  <option value="tournament">Tournament Configuration</option>
                  <option value="scenario">Test Scenario</option>
                  <option value="template">Tournament Template</option>
                  <option value="bulk">Bulk Export</option>
                </select>
              </div>

              <div className="form-group">
                <label>Name</label>
                <input
                  type="text"
                  value={exportName}
                  onChange={(e) => setExportName(e.target.value)}
                  placeholder="Enter export name"
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label>Description (optional)</label>
                <textarea
                  value={exportDescription}
                  onChange={(e) => setExportDescription(e.target.value)}
                  placeholder="Brief description of this export"
                  className="form-textarea"
                  rows={2}
                />
              </div>

              <div className="export-options">
                <label className="checkbox-option">
                  <input
                    type="checkbox"
                    checked={exportOptions.includeFullData}
                    onChange={(e) => setExportOptions(prev => ({ ...prev, includeFullData: e.target.checked }))}
                  />
                  <span>Include full tournament data (players, matches, results)</span>
                </label>

                <label className="checkbox-option">
                  <input
                    type="checkbox"
                    checked={exportOptions.compress}
                    onChange={(e) => setExportOptions(prev => ({ ...prev, compress: e.target.checked }))}
                  />
                  <span>Compress data for smaller file size</span>
                </label>

                <label className="checkbox-option">
                  <input
                    type="checkbox"
                    checked={exportOptions.generateChecksum}
                    onChange={(e) => setExportOptions(prev => ({ ...prev, generateChecksum: e.target.checked }))}
                  />
                  <span>Generate checksum for data integrity</span>
                </label>
              </div>

              {exportOptions.type === 'scenario' && (
                <div className="scenario-config">
                  <h4>Test Scenario Configuration</h4>
                  <div className="form-group">
                    <label>Scenario Name</label>
                    <input
                      type="text"
                      value={scenarioData.name}
                      onChange={(e) => setScenarioData(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Enter scenario name"
                      className="form-input"
                    />
                  </div>
                  <p className="help-text">Test scenarios will be configured in the TestCenter workflow</p>
                </div>
              )}

              <div className="action-buttons">
                <button
                  className="action-button primary"
                  onClick={handleExport}
                  disabled={exportMutation.isPending}
                >
                  {exportMutation.isPending ? 'Exporting...' : '📤 Export'}
                </button>
              </div>
            </div>
          )}

          {activeTab === 'import' && (
            <div className="import-tab">
              <h3>Import Tournament Data</h3>

              <div className="import-methods">
                <div className="method-tabs">
                  <button
                    className={`method-tab ${!importFile ? 'active' : ''}`}
                    onClick={() => setImportFile(null)}
                  >
                    📝 Paste JSON
                  </button>
                  <button
                    className={`method-tab ${importFile ? 'active' : ''}`}
                    onClick={() => document.getElementById('file-input')?.click()}
                  >
                    📁 Upload File
                  </button>
                </div>

                {!importFile ? (
                  <div className="form-group">
                    <label>JSON Data</label>
                    <textarea
                      value={importData}
                      onChange={(e) => setImportData(e.target.value)}
                      placeholder="Paste exported JSON data here"
                      className="form-textarea"
                      rows={10}
                    />
                  </div>
                ) : (
                  <div className="file-info">
                    <p>📁 Selected file: {importFile.name}</p>
                    <p>Size: {(importFile.size / 1024).toFixed(1)} KB</p>
                  </div>
                )}

                <input
                  id="file-input"
                  type="file"
                  accept=".json"
                  onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                  style={{ display: 'none' }}
                />
              </div>

              <div className="action-buttons">
                <button
                  className="action-button primary"
                  onClick={handleImport}
                  disabled={importMutation.isPending || (!importData.trim() && !importFile)}
                >
                  {importMutation.isPending ? 'Importing...' : '📥 Import'}
                </button>
              </div>

              {importResults && (
                <div className="import-results">
                  <h4>Import Results</h4>
                  <div className={`result-status ${importResults.success ? 'success' : 'error'}`}>
                    {importResults.success ? '✅ Import Successful' : '❌ Import Failed'}
                  </div>

                  {importResults.metadata && (
                    <div className="result-details">
                      <p><strong>Type:</strong> {importResults.metadata.type}</p>
                      <p><strong>Imported At:</strong> {new Date(importResults.metadata.importedAt).toLocaleString()}</p>
                      {importResults.importedId && (
                        <p><strong>ID:</strong> {importResults.importedId}</p>
                      )}
                    </div>
                  )}

                  {importResults.warnings && importResults.warnings.length > 0 && (
                    <div className="result-warnings">
                      <h5>Warnings:</h5>
                      <ul>
                        {importResults.warnings.map((warning: string, index: number) => (
                          <li key={index}>⚠️ {warning}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {importResults.errors && importResults.errors.length > 0 && (
                    <div className="result-errors">
                      <h5>Errors:</h5>
                      <ul>
                        {importResults.errors.map((error: string, index: number) => (
                          <li key={index}>❌ {error}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'templates' && (
            <div className="templates-tab">
              <h3>Tournament Templates</h3>

              <div className="template-filters">
                <div className="form-group">
                  <label>Search Templates</label>
                  <input
                    type="text"
                    value={templateSearch}
                    onChange={(e) => setTemplateSearch(e.target.value)}
                    placeholder="Search by name, description, or tags"
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Category</label>
                  <select
                    value={templateCategory}
                    onChange={(e) => setTemplateCategory(e.target.value)}
                    className="form-select"
                  >
                    <option value="all">All Categories</option>
                    {templateManager.getTemplateCategories().map(cat => (
                      <option key={cat.value} value={cat.value}>{cat.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="templates-grid">
                {filteredTemplates.map(template => (
                  <div key={template.id} className="template-card">
                    <div className="template-header">
                      <h4>{template.name}</h4>
                      <div className="template-badges">
                        <span className={`badge ${template.difficulty}`}>
                          {template.difficulty}
                        </span>
                        <span className={`badge ${template.category}`}>
                          {template.category.replace('_', ' ')}
                        </span>
                      </div>
                    </div>

                    <p className="template-description">{template.description}</p>

                    <div className="template-meta">
                      <span>👥 {template.recommendedPlayers} players</span>
                      <span>⏱️ {Math.floor(template.estimatedDuration / 60)}h {template.estimatedDuration % 60}m</span>
                    </div>

                    <div className="template-tags">
                      {template.tags.slice(0, 3).map(tag => (
                        <span key={tag} className="tag">#{tag}</span>
                      ))}
                    </div>

                    <div className="template-actions">
                      <button
                        className="action-button small primary"
                        onClick={() => handleLoadTemplate(template)}
                      >
                        📂 Load
                      </button>
                      <button
                        className="action-button small secondary"
                        onClick={() => {
                          setSelectedTemplate(template)
                          setActiveTab('export')
                          setExportOptions(prev => ({ ...prev, type: 'template' }))
                        }}
                      >
                        📤 Export
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {filteredTemplates.length === 0 && (
                <div className="empty-state">
                  <p>No templates found matching your criteria.</p>
                  <p>Try adjusting your search or category filter.</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'bulk' && (
            <div className="bulk-tab">
              <h3>Bulk Operations</h3>
              <p className="coming-soon">Bulk export/import operations will be available in a future update.</p>

              <div className="bulk-features">
                <div className="feature-item">
                  <h4>📦 Bulk Export</h4>
                  <p>Export multiple tournaments, scenarios, and templates at once</p>
                </div>
                <div className="feature-item">
                  <h4>📥 Bulk Import</h4>
                  <p>Import multiple items with progress tracking and error handling</p>
                </div>
                <div className="feature-item">
                  <h4>🔄 Migration Tools</h4>
                  <p>Convert and migrate data between different versions</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'sharing' && (
            <div className="sharing-tab">
              <h3>Share Tournament Data</h3>

              {!shareData ? (
                <div className="empty-state">
                  <p>No data to share. Please export something first.</p>
                  <button
                    className="action-button primary"
                    onClick={() => setActiveTab('export')}
                  >
                    Go to Export
                  </button>
                </div>
              ) : (
                <div className="sharing-options">
                  <div className="share-methods">
                    <button
                      className="share-method"
                      onClick={() => handleShare('clipboard')}
                      disabled={shareMutation.isPending}
                    >
                      📋 Copy to Clipboard
                    </button>
                    <button
                      className="share-method"
                      onClick={() => handleShare('download')}
                      disabled={shareMutation.isPending}
                    >
                      💾 Download File
                    </button>
                    <button
                      className="share-method"
                      onClick={() => handleShare('qrcode')}
                      disabled={shareMutation.isPending}
                    >
                      📱 Generate QR Code
                    </button>
                  </div>

                  {qrCodeUrl && (
                    <div className="qr-code-display">
                      <h4>QR Code</h4>
                      <img src={qrCodeUrl} alt="QR Code for tournament data" className="qr-code" />
                      <p className="qr-help">Scan this QR code to import the tournament data</p>
                    </div>
                  )}

                  <div className="share-info">
                    <h4>Sharing Information</h4>
                    <div className="share-details">
                      <p><strong>Type:</strong> {shareData.type}</p>
                      <p><strong>Name:</strong> {shareData.metadata?.name}</p>
                      <p><strong>Size:</strong> {(JSON.stringify(shareData).length / 1024).toFixed(1)} KB</p>
                      <p><strong>Exported:</strong> {new Date(shareData.exportedAt).toLocaleString()}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}