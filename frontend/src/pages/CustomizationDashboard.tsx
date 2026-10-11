/**
 * Customization Dashboard — Super Admin UI Editor
 * Allows editing all customizable text, images, and section visibility across the app
 */

import { useState } from 'react'
import { useUiCustomization } from '@/contexts/UiCustomizationContext'
import { useAuth } from '@/contexts/AuthContext'

interface EditableSection {
  id: string
  title: string
  description: string
  items: EditableItem[]
  category: 'text' | 'images' | 'visibility'
}

interface EditableItem {
  key: string
  label: string
  type: 'text' | 'textarea' | 'url' | 'toggle'
  defaultValue: string | boolean
}

const EDITABLE_SECTIONS: EditableSection[] = [
  {
    id: 'footer',
    title: '📄 Footer',
    description: 'Edit footer legal statement',
    category: 'text',
    items: [
      {
        key: 'footer.legal_statement',
        label: 'Legal Statement',
        type: 'textarea',
        defaultValue: '© 2026 Example Organization LLC. All rights reserved.',
      },
    ],
  },
  {
    id: 'splash',
    title: '🔐 Splash/Login Page',
    description: 'Edit login page greeting and image',
    category: 'text',
    items: [
      {
        key: 'splash.alfa_image_url',
        label: 'ALFa Image URL',
        type: 'url',
        defaultValue: '/branding/alfa-ai-avatar.png',
      },
      {
        key: 'splash.alfa_greeting',
        label: 'ALFa Greeting Message',
        type: 'textarea',
        defaultValue: "I'm your intelligent billiards coach. Log in to access rankings, tournament management, game analysis, and more. I'll guide you every step of the way!",
      },
    ],
  },
  {
    id: 'home',
    title: '🏠 Home Page',
    description: 'Edit home page ALFa Coach section and suggestions',
    category: 'text',
    items: [
      {
        key: 'home.alfa_image_url',
        label: 'ALFa Coach Image URL',
        type: 'url',
        defaultValue: '/branding/alfa-ai-avatar.png',
      },
      {
        key: 'home.alfa_description',
        label: 'ALFa Coach Description',
        type: 'textarea',
        defaultValue: 'Your intelligent billiards coach. Here\'s how to get started:',
      },
      {
        key: 'home.alfa_tip',
        label: 'ALFa Coach Tip/Pro Tip',
        type: 'textarea',
        defaultValue: 'ALFa AI Coach provides contextual guidance throughout the app.',
      },
    ],
  },
  {
    id: 'rankings',
    title: '🏆 Rankings Page',
    description: 'Edit rankings page headers and descriptions',
    category: 'text',
    items: [
      {
        key: 'rankings.page_title',
        label: 'Page Title',
        type: 'text',
        defaultValue: 'Player Rankings',
      },
      {
        key: 'rankings.page_description',
        label: 'Page Description',
        type: 'textarea',
        defaultValue: 'View WPBA Women, WPA Women, WPA Men, and WPA Artistic player rankings with Fargo ratings and ranking history.',
      },
    ],
  },
  {
    id: 'tournament_wizard',
    title: '🎯 Tournament Wizard',
    description: 'Edit tournament creation wizard text',
    category: 'text',
    items: [
      {
        key: 'tournament_wizard.title',
        label: 'Wizard Title',
        type: 'text',
        defaultValue: '🎯 Tournament Wizard',
      },
      {
        key: 'tournament_wizard.intro_text',
        label: 'Introduction Text',
        type: 'textarea',
        defaultValue: 'Create a new tournament in simple steps',
      },
    ],
  },
  {
    id: 'sidebar',
    title: '📋 Sidebar & Navigation',
    description: 'Edit sidebar title and subtitle',
    category: 'text',
    items: [
      {
        key: 'sidebar.title',
        label: 'Sidebar Main Title',
        type: 'text',
        defaultValue: 'Rankings',
      },
      {
        key: 'sidebar.subtitle',
        label: 'Sidebar Subtitle',
        type: 'text',
        defaultValue: 'WPBA & WPA',
      },
    ],
  },
]

export default function CustomizationDashboard() {
  const { isSuperAdmin } = useAuth()
  const { getText, setDraftText, isEditing } = useUiCustomization()
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['footer', 'splash', 'home']))

  if (!isSuperAdmin) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-400 text-lg">Access Denied — Super Admin only</p>
      </div>
    )
  }

  const filteredSections = EDITABLE_SECTIONS.filter(
    (section) =>
      section.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      section.items.some((item) => item.label.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  const toggleSection = (id: string) => {
    const newExpanded = new Set(expandedSections)
    if (newExpanded.has(id)) {
      newExpanded.delete(id)
    } else {
      newExpanded.add(id)
    }
    setExpandedSections(newExpanded)
  }

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-white mb-2">🎨 UI Customization Dashboard</h1>
        <p className="text-slate-400">Edit all text, images, and content across the application</p>
      </div>

      {/* Mode Indicator */}
      <div className={`p-4 rounded-lg border ${
        isEditing
          ? 'border-yellow-500/50 bg-yellow-500/10'
          : 'border-sky-500/50 bg-sky-500/10'
      }`}>
        <p className="text-sm">
          {isEditing ? (
            <span className="text-yellow-300">✎ <strong>Edit Mode Active</strong> — Click "Save" when done</span>
          ) : (
            <span className="text-sky-300"><strong>View Mode</strong> — Click "Edit" to make changes</span>
          )}
        </p>
      </div>

      {/* Search */}
      <div className="relative">
        <input
          type="text"
          placeholder="Search customization sections..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full px-4 py-3 rounded-lg bg-slate-800 border border-slate-700 text-white placeholder-slate-400 focus:outline-none focus:border-sky-500"
        />
      </div>

      {/* Customization Sections */}
      <div className="space-y-4">
        {filteredSections.map((section) => (
          <div key={section.id} className="bg-slate-900/50 border border-slate-800 rounded-lg overflow-hidden">
            {/* Section Header */}
            <button
              onClick={() => toggleSection(section.id)}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-800/50 transition-colors"
            >
              <div className="text-left">
                <h2 className="text-lg font-semibold text-white">{section.title}</h2>
                <p className="text-sm text-slate-400">{section.description}</p>
              </div>
              <div className="text-2xl flex-shrink-0">
                {expandedSections.has(section.id) ? '▼' : '▶'}
              </div>
            </button>

            {/* Section Content */}
            {expandedSections.has(section.id) && (
              <div className="border-t border-slate-800 px-6 py-4 space-y-4 bg-slate-950/30">
                {section.items.map((item) => {
                  const value = getText(item.key, String(item.defaultValue))

                  return (
                    <div key={item.key} className="space-y-2">
                      <label className="block text-sm font-medium text-slate-200">{item.label}</label>

                      {isEditing ? (
                        <>
                          {item.type === 'textarea' ? (
                            <textarea
                              value={value}
                              onChange={(e) => setDraftText(item.key, e.target.value)}
                              rows={4}
                              className="w-full px-4 py-3 rounded-lg bg-slate-800 border border-sky-500/50 text-white placeholder-slate-400 focus:outline-none focus:border-sky-400 font-mono text-sm"
                              placeholder={`Enter ${item.label.toLowerCase()}...`}
                            />
                          ) : item.type === 'url' ? (
                            <input
                              type="url"
                              value={value}
                              onChange={(e) => setDraftText(item.key, e.target.value)}
                              className="w-full px-4 py-3 rounded-lg bg-slate-800 border border-sky-500/50 text-white placeholder-slate-400 focus:outline-none focus:border-sky-400 font-mono text-sm"
                              placeholder="https://example.com/image.png or /assets/image.png"
                            />
                          ) : item.type === 'toggle' ? (
                            <button
                              onClick={() => setDraftText(item.key, String(value === 'true' ? false : true))}
                              className={`px-4 py-2 rounded-lg font-semibold transition-colors ${
                                value === 'true'
                                  ? 'bg-green-600 text-white'
                                  : 'bg-slate-700 text-slate-300'
                              }`}
                            >
                              {value === 'true' ? '✓ Enabled' : '✗ Disabled'}
                            </button>
                          ) : (
                            <input
                              type="text"
                              value={value}
                              onChange={(e) => setDraftText(item.key, e.target.value)}
                              className="w-full px-4 py-3 rounded-lg bg-slate-800 border border-sky-500/50 text-white placeholder-slate-400 focus:outline-none focus:border-sky-400"
                              placeholder={`Enter ${item.label.toLowerCase()}...`}
                            />
                          )}
                        </>
                      ) : (
                        <div className="px-4 py-3 rounded-lg bg-slate-800/50 border border-slate-700 text-slate-300 whitespace-pre-wrap text-sm break-words max-h-32 overflow-y-auto">
                          {typeof value === 'string' ? value : String(value)}
                        </div>
                      )}

                      {item.type === 'url' && !isEditing && value && (
                        <div className="mt-2">
                          <img
                            src={value}
                            alt={item.label}
                            className="max-h-32 rounded-lg border border-slate-700"
                            onError={(e) => {
                              ;(e.target as HTMLImageElement).src = '/assets/avatar-default.png'
                            }}
                          />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* No Results */}
      {filteredSections.length === 0 && (
        <div className="text-center py-12">
          <p className="text-slate-400">No customization sections found matching "{searchTerm}"</p>
        </div>
      )}

      {/* Info Box */}
      <div className="bg-blue-950/30 border border-blue-500/30 rounded-lg p-4 text-sm text-blue-200">
        <p className="font-semibold mb-2">💡 Tips:</p>
        <ul className="list-disc list-inside space-y-1 text-xs">
          <li>For image URLs, use full URLs (https://...) or paths (/assets/...)</li>
          <li>Changes are saved to the database and persist immediately</li>
          <li>All edits are live — no page refresh needed</li>
          <li>Reset button on the toolbar reverts unsaved changes</li>
        </ul>
      </div>
    </div>
  )
}
