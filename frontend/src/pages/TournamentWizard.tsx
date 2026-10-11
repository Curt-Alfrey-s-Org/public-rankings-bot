import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { tournamentsApi, type Player, type BracketTemplate, type PlayerCreate } from '@/api/tournaments'
import { tournamentHistoryApi } from '@/api/tournamentHistory'
import { usersApi } from '@/api/users'
import { useUiCustomization } from '@/contexts/UiCustomizationContext'
import { useAuth } from '@/contexts/AuthContext'
import { toast } from '@/lib/toast'
import {
  buildPrefillFromUpcomingEvent,
  upcomingEventKey,
  type PrefillSource,
} from '@/lib/upcomingEventPrefill'

const DEFAULT_AVATAR = '/assets/avatar-default.png'

function isWpbaAssociation(tag: string): boolean {
  return (tag || '').toUpperCase().includes('WPBA')
}

function upcomingMatchesDirectorAssociation(
  event: { association?: string; name?: string },
  directorAssoc: string,
): boolean {
  if (!directorAssoc) return true
  const d = directorAssoc.toUpperCase()
  const evAssoc = (event.association || '').toUpperCase()
  const title = (event.name || '').toUpperCase()
  if (d.includes('WPBA')) {
    return evAssoc.includes('WPBA') || title.includes('WPBA') || evAssoc === 'WPBA'
  }
  if (d.includes('WPA') && !d.includes('WPBA')) {
    if (evAssoc.includes('WPBA') || title.includes('WPBA')) return false
    return evAssoc.includes('WPA') || title.includes('WPA') || !evAssoc
  }
  return !evAssoc || evAssoc === d || d.startsWith(evAssoc) || evAssoc.startsWith(d)
}

function buildSeRounds(drawSize: number): Array<{ round: number; matches: number }> {
  const out: Array<{ round: number; matches: number }> = []
  let m = Math.floor(drawSize / 2)
  let r = 1
  while (m >= 1) {
    out.push({ round: r, matches: m })
    m = Math.floor(m / 2)
    r += 1
  }
  return out
}

type Step = 1 | 2 | 3 | 4

/** Entry flow before the 4-step wizard. */
type WizardEntryMode = 'choose' | 'pick-scheduled' | 'wizard'

type WizardSource = 'new' | 'scheduled' | null

/** AI coach panel urgency: only `error` uses red (real problems). */
type CoachPriority = 'welcome' | 'medium' | 'high' | 'error' | 'low'

function resolveEntryMode(params: URLSearchParams): WizardEntryMode {
  if (params.get('event')?.trim()) return 'wizard'
  const mode = params.get('mode')
  if (mode === 'new') return 'wizard'
  if (mode === 'scheduled') return 'pick-scheduled'
  return 'choose'
}

function resolveWizardSource(params: URLSearchParams): WizardSource {
  if (params.get('event')?.trim()) return 'scheduled'
  if (params.get('mode') === 'new') return 'new'
  return null
}

function formatEventDateLabel(evt: { date?: string | null; start_date?: string | null; end_date?: string | null }) {
  const start = evt.start_date ?? evt.date
  const end = evt.end_date ?? start
  if (!start) return ''
  if (end && end !== start) return `${start} – ${end}`
  return start
}

interface FormData {
  // Step 1: Basic Info
  tournament_name: string
  tournament_date: string
  tournament_end_date: string
  location: string
  elimination_type: 'single' | 'double' | 'round_robin' | 'group_stage'
  max_players: number
  tables_available: number
  entry_fee_cents: number

  // Group Stage specific fields
  num_groups?: number
  players_per_group?: number
  group_advance_count?: number
  group_format?: 'round_robin' | 'single_elimination'

  // Step 2: Point Structure
  selectedTemplate?: number
  useCustomPoints: boolean
  points_structure: Record<string, string>

  // Step 3: Player Registration
  selectedPlayers: string[]

  // Step 4: Review
  notes: string
}

const initialFormData: FormData = {
  tournament_name: '',
  tournament_date: new Date().toISOString().split('T')[0],
  tournament_end_date: new Date().toISOString().split('T')[0],
  location: '',
  elimination_type: 'single',
  max_players: 32,
  tables_available: 1,
  entry_fee_cents: 0,
  useCustomPoints: false,
  points_structure: {
    '1': '2880',
    '2': '3600',
    '3': '2160',
    '4': '1440',
  },
  selectedPlayers: [],
  notes: '',
}

export default function TournamentWizard() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const { getText } = useUiCustomization()
  const { isSuperAdmin, isAdmin } = useAuth()
  const avatarUrl = DEFAULT_AVATAR
  const [currentStep, setCurrentStep] = useState<Step>(1)
  const [formData, setFormData] = useState<FormData>(initialFormData)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [useCompetitorsImport, setUseCompetitorsImport] = useState(false)
  const [competitorsSlug, setCompetitorsSlug] = useState('2026-wpba-classics-players-championship')
  const [competitorsRaceTo, setCompetitorsRaceTo] = useState(7)
  const [competitorsGenerateBracket, setCompetitorsGenerateBracket] = useState(true)
  const [showAIAssistant, setShowAIAssistant] = useState(true)
  const [aiDismissed, setAiDismissed] = useState(false)

  const [selectedAssociation, setSelectedAssociation] = useState('')
  const [bracketTemplateId, setBracketTemplateId] = useState<number | null>(null)
  const [showCustomBracket, setShowCustomBracket] = useState(false)
  const [customDrawSize, setCustomDrawSize] = useState(32)
  const [customEntrantCount, setCustomEntrantCount] = useState(32)
  const [customFormat, setCustomFormat] = useState<'single_elimination' | 'double_elimination'>('single_elimination')
  const [customByeStrategy, setCustomByeStrategy] = useState('top_seed')
  const [saveTemplateName, setSaveTemplateName] = useState('')
  const [playerSearch, setPlayerSearch] = useState('')
  const [showNewPlayerForm, setShowNewPlayerForm] = useState(false)
  const [newPlayerFirst, setNewPlayerFirst] = useState('')
  const [newPlayerLast, setNewPlayerLast] = useState('')
  const [newPlayerCountry, setNewPlayerCountry] = useState('')
  const [newPlayerLicense, setNewPlayerLicense] = useState('')
  const [gameType, setGameType] = useState('9_ball')
  const [prefillSources, setPrefillSources] = useState<PrefillSource[]>([])
  const [selectedUpcomingKey, setSelectedUpcomingKey] = useState<string>('')
  const [entryMode, setEntryMode] = useState<WizardEntryMode>(() => resolveEntryMode(searchParams))
  const [wizardSource, setWizardSource] = useState<WizardSource>(() => resolveWizardSource(searchParams))

  const { data: myAssociationsData } = useQuery({
    queryKey: ['my-associations'],
    queryFn: usersApi.getMyAssociations,
  })

  const { data: templates = [] } = useQuery({
    queryKey: ['tournament-templates'],
    queryFn: tournamentsApi.getTemplates,
  })

  const { data: bracketTemplates = [] } = useQuery({
    queryKey: ['bracket-templates', selectedAssociation],
    queryFn: () => tournamentsApi.getBracketTemplates(selectedAssociation || undefined),
    enabled: !!selectedAssociation,
  })

  const { data: players = [] } = useQuery<Player[]>({
    queryKey: ['players', selectedAssociation, isAdmin, isSuperAdmin],
    queryFn: async () => {
      const scoped = await tournamentsApi.getPlayers(true, selectedAssociation || undefined)
      if (scoped.length > 0 || (!isAdmin && !isSuperAdmin)) {
        return scoped
      }
      // First event for this association: admins see full active roster
      return tournamentsApi.getPlayers(true)
    },
    enabled: !!selectedAssociation,
  })

  const { data: historyPlayers = [] } = useQuery<Player[]>({
    queryKey: ['players-history', selectedAssociation],
    queryFn: () => tournamentsApi.getPlayersFromHistory(selectedAssociation),
    enabled: !!selectedAssociation,
  })

  const { data: upcomingEventsData } = useQuery({
    queryKey: ['upcoming-events'],
    queryFn: () => tournamentHistoryApi.getUpcomingEvents(undefined, 500),
    staleTime: 300_000, // 5 minutes
  })
  const upcomingEvents = upcomingEventsData?.events ?? []
  const filteredUpcoming = useMemo(
    () => upcomingEvents.filter((e) => upcomingMatchesDirectorAssociation(e, selectedAssociation)),
    [upcomingEvents, selectedAssociation],
  )

  const directorUpcoming = useMemo(() => {
    const assocs = myAssociationsData?.associations ?? []
    if (!assocs.length) return upcomingEvents
    return upcomingEvents.filter((e) => assocs.some((a) => upcomingMatchesDirectorAssociation(e, a)))
  }, [upcomingEvents, myAssociationsData?.associations])

  const { data: inProgressTournaments = [] } = useQuery({
    queryKey: ['tournaments-in-setup'],
    queryFn: async () => {
      const all = await tournamentsApi.getTournaments()
      return all.filter((t) => t.status === 'setup' || t.status === 'registration')
    },
    enabled: entryMode === 'pick-scheduled' || entryMode === 'choose',
  })

  const historyPlayerIds = useMemo(
    () => new Set(historyPlayers.map((p) => p.player_id)),
    [historyPlayers],
  )

  const historyFiltered = useMemo(() => {
    const q = playerSearch.trim().toLowerCase()
    const match = (p: Player) =>
      !q ||
      `${p.first_name} ${p.last_name}`.toLowerCase().includes(q) ||
      (p.nickname || '').toLowerCase().includes(q)
    return historyPlayers.filter(match)
  }, [historyPlayers, playerSearch])

  const otherPlayersFiltered = useMemo(() => {
    const q = playerSearch.trim().toLowerCase()
    const match = (p: Player) =>
      !q ||
      `${p.first_name} ${p.last_name}`.toLowerCase().includes(q) ||
      (p.nickname || '').toLowerCase().includes(q)
    return players.filter((p) => !historyPlayerIds.has(p.player_id) && match(p))
  }, [players, historyPlayerIds, playerSearch])

  const activeBracketTemplate = bracketTemplates.find((t) => t.id === bracketTemplateId)

  useEffect(() => {
    const list = myAssociationsData?.associations
    if (list?.length && !selectedAssociation) {
      setSelectedAssociation(list[0])
    }
  }, [myAssociationsData, selectedAssociation])

  useEffect(() => {
    if (isWpbaAssociation(selectedAssociation) && !(isAdmin || isSuperAdmin)) {
      setGameType('9_ball')
    }
  }, [selectedAssociation, isAdmin, isSuperAdmin])

  const saveBracketTemplateMutation = useMutation({
    mutationFn: () =>
      tournamentsApi.createBracketTemplate({
        name: saveTemplateName.trim() || `Custom ${customEntrantCount} (${customDrawSize} draw)`,
        player_count: customEntrantCount,
        bracket_draw_size: customDrawSize,
        format: customFormat,
        bye_strategy: customByeStrategy,
        rounds: buildSeRounds(customDrawSize),
        association: selectedAssociation || null,
      }),
    onSuccess: (tpl) => {
      toast.success('Bracket template saved for next time.')
      setBracketTemplateId(tpl.id)
      setFormData((prev) => ({
        ...prev,
        max_players: customEntrantCount,
        elimination_type: customFormat === 'double_elimination' ? 'double' : 'single',
      }))
      queryClient.invalidateQueries({ queryKey: ['bracket-templates', selectedAssociation] })
      setSaveTemplateName('')
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      toast.error(err?.response?.data?.detail || err?.message || 'Could not save template')
    },
  })

  const createPlayerMutation = useMutation({
    mutationFn: (body: PlayerCreate) => tournamentsApi.createPlayer(body),
    onSuccess: (p) => {
      toast.success(`Added ${p.first_name} ${p.last_name}`)
      queryClient.invalidateQueries({ queryKey: ['players', selectedAssociation] })
      queryClient.invalidateQueries({ queryKey: ['players-history', selectedAssociation] })
      setFormData((prev) => ({
        ...prev,
        selectedPlayers: prev.selectedPlayers.includes(p.player_id)
          ? prev.selectedPlayers
          : [...prev.selectedPlayers, p.player_id],
      }))
      setShowNewPlayerForm(false)
      setNewPlayerFirst('')
      setNewPlayerLast('')
      setNewPlayerCountry('')
      setNewPlayerLicense('')
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      toast.error(err?.response?.data?.detail || err?.message || 'Could not create player')
    },
  })

  const findBracketPreset = (pc: number, fmt: 'single_elimination' | 'double_elimination') =>
    bracketTemplates.find((t) => t.is_system && t.player_count === pc && t.format === fmt)

  const applyBracketTemplate = (t: BracketTemplate) => {
    setBracketTemplateId(t.id)
    setShowCustomBracket(false)
    setFormData((prev) => ({
      ...prev,
      max_players: t.player_count,
      elimination_type: t.format === 'double_elimination' ? 'double' : 'single',
    }))
  }

  const applyCustomDrawToForm = () => {
    setBracketTemplateId(null)
    setFormData((prev) => ({
      ...prev,
      max_players: Math.max(2, Math.min(256, customEntrantCount)),
      elimination_type: customFormat === 'double_elimination' ? 'double' : 'single',
    }))
    toast.success('Custom field size applied. Save as template if you want to reuse it.')
  }

  const lastPrefilledName = useRef<string | null>(null)
  const appliedEventParam = useRef<string | null>(null)

  const resetWizardForm = useCallback(() => {
    setFormData(initialFormData)
    setCurrentStep(1)
    setErrors({})
    setPrefillSources([])
    setSelectedUpcomingKey('')
    setBracketTemplateId(null)
    lastPrefilledName.current = null
  }, [])

  const beginNewTournament = useCallback(() => {
    resetWizardForm()
    setWizardSource('new')
    setEntryMode('wizard')
  }, [resetWizardForm])

  const beginScheduledPicker = useCallback(() => {
    setEntryMode('pick-scheduled')
  }, [])

  const applyUpcomingEventPrefill = useCallback((eventId: string) => {
    const event = upcomingEvents.find(
      (e) => upcomingEventKey(e) === eventId || e.event_id === eventId || e.id?.toString() === eventId,
    )
    if (!event) return false

    const prefill = buildPrefillFromUpcomingEvent(event)
    setFormData((prev) => ({
      ...prev,
      tournament_name: prefill.tournament_name || prev.tournament_name,
      tournament_date: prefill.tournament_date || prev.tournament_date,
      tournament_end_date: prefill.tournament_end_date || prev.tournament_end_date,
      location: prefill.location || prev.location,
      max_players: prefill.max_players ?? prev.max_players,
      elimination_type: prefill.elimination_type ?? prev.elimination_type,
      notes: prefill.notes || prev.notes,
    }))
    setPrefillSources(prefill.sources)
    setSelectedUpcomingKey(upcomingEventKey(event))

    if (prefill.association) {
      const list = myAssociationsData?.associations ?? []
      const match = list.find(
        (a) =>
          a.toUpperCase() === prefill.association!.toUpperCase()
          || prefill.association!.toUpperCase().includes(a.toUpperCase())
          || a.toUpperCase().includes(prefill.association!.toUpperCase()),
      )
      if (match) setSelectedAssociation(match)
      else if (isSuperAdmin || isAdmin) setSelectedAssociation(prefill.association)
    }

    if (prefill.max_players) {
      const tpl = bracketTemplates.find(
        (t) => t.player_count === prefill.max_players || t.bracket_draw_size === prefill.max_players,
      )
      if (tpl) setBracketTemplateId(tpl.id)
    }

    toast.success(`Prefilled from ${event.association || 'upcoming'} event — review and edit any field.`)
    return true
  }, [upcomingEvents, myAssociationsData?.associations, isSuperAdmin, isAdmin, bracketTemplates])

  const beginScheduledEvent = useCallback(
    (eventId: string) => {
      if (!applyUpcomingEventPrefill(eventId)) return
      setWizardSource('scheduled')
      setEntryMode('wizard')
      setCurrentStep(1)
    },
    [applyUpcomingEventPrefill],
  )

  const handlePrefillFromEvent = (eventId: string) => {
    applyUpcomingEventPrefill(eventId)
    setWizardSource('scheduled')
    setEntryMode('wizard')
  }

  useEffect(() => {
    const param = searchParams.get('event')?.trim()
    if (!param || !upcomingEvents.length || appliedEventParam.current === param) return
    if (applyUpcomingEventPrefill(param)) {
      appliedEventParam.current = param
      setWizardSource('scheduled')
      setEntryMode('wizard')
    }
  }, [searchParams, upcomingEvents, applyUpcomingEventPrefill])

  useEffect(() => {
    const name = formData.tournament_name?.trim()
    if (currentStep !== 2 || !name || lastPrefilledName.current === name) return
    lastPrefilledName.current = name
    tournamentHistoryApi.getPointsByTournamentName(name).then((res) => {
      if (res.success && res.points_structure && Object.keys(res.points_structure).length > 0) {
        setFormData((prev) => {
          const next: Record<string, string> = { ...prev.points_structure }
          Object.entries(res.points_structure!).forEach(([placement, points]) => {
            next[placement] = String(points)
          })
          return { ...prev, points_structure: next }
        })
        toast.success(`Prefilled points from past tournament "${name}" (editable)`)
      }
    }).catch(() => { lastPrefilledName.current = null })
  }, [currentStep, formData.tournament_name])

  useEffect(() => {
    if (formData.selectedTemplate && !formData.useCustomPoints) {
      const template = templates.find((t) => t.id === formData.selectedTemplate)
      if (template) {
        const points: Record<string, string> = {}
        Object.entries(template.points_structure).forEach(([placement, points_value]) => {
          points[placement] = String(points_value)
        })
        setFormData((prev) => ({
          ...prev,
          points_structure: points,
        }))
      }
    }
  }, [formData.selectedTemplate, formData.useCustomPoints, templates])

  const createTournamentMutation = useMutation({
    mutationFn: async () => {
      if (!formData.tournament_name?.trim()) throw new Error('Tournament name is required')
      if (!formData.tournament_date) throw new Error('Tournament start date is required')
      if (!formData.tournament_end_date) throw new Error('Tournament end date is required')
      if (!formData.location?.trim()) throw new Error('Location is required')

      const points_structure: Record<string, number> = {}
      Object.entries(formData.points_structure).forEach(([placement, points_value]) => {
        points_structure[placement] = parseFloat(points_value) || 0
      })

      const tournament = await tournamentsApi.createTournament({
        tournament_name: formData.tournament_name,
        tournament_date: formData.tournament_date,
        tournament_end_date: formData.tournament_end_date,
        location: formData.location || undefined,
        elimination_type: formData.elimination_type as 'single' | 'double' | 'round_robin' | 'group_stage',
        max_players: formData.max_players,
        tables_available: formData.tables_available > 0 ? formData.tables_available : undefined,
        points_structure,
        notes: formData.notes || undefined,
        template_id: formData.selectedTemplate,
        association: selectedAssociation,
        game_type: gameType || undefined,
        bracket_template_id: bracketTemplateId ?? undefined,
      })

      const shouldImport = useCompetitorsImport && competitorsSlug.trim().length > 0
      if (shouldImport) {
        const importResult = await tournamentsApi.importCompetitors(tournament.tournament_id, {
          slug: competitorsSlug.trim(),
          generate_bracket: competitorsGenerateBracket,
          race_to: competitorsRaceTo,
        })
        toast.success(`Imported ${importResult.actual_players} players and ${importResult.matches_updated} matches from competitors`)
      }

      if (formData.entry_fee_cents > 0) {
        await tournamentsApi.updateRegistrationSettings(tournament.tournament_id, {
          entry_fee_cents: formData.entry_fee_cents,
          payment_required: true,
        })
      }

      if (!shouldImport && formData.selectedPlayers.length > 0) {
        await tournamentsApi.registerPlayers(tournament.tournament_id, formData.selectedPlayers)
        await tournamentsApi.generateBracket(tournament.tournament_id)
      }

      return tournament
    },
    onSuccess: (tournament) => {
      toast.success(`Tournament "${tournament.tournament_name}" created successfully!`)
      setTimeout(() => navigate('/tournament-wizard/bracket', { state: { tournamentId: tournament.tournament_id } }), 500)
    },
    onError: (error: any) => {
      console.error('Tournament creation error:', error)
      let errorMessage = 'Unknown error'
      
      if (error?.response?.data?.detail) {
        // FastAPI validation error
        if (Array.isArray(error.response.data.detail)) {
          errorMessage = error.response.data.detail.map((e: any) => 
            `${e.loc?.join(' → ')}: ${e.msg}`
          ).join('; ')
        } else {
          errorMessage = error.response.data.detail
        }
      } else if (error instanceof Error) {
        errorMessage = error.message
      }
      
      toast.error(`Failed to create tournament: ${errorMessage}`)
    },
  })

  const validateStep = () => {
    const newErrors: Record<string, string> = {}

    if (currentStep === 1) {
      if (!selectedAssociation.trim()) newErrors.association = 'Select the association for this tournament'
      if (!formData.tournament_name.trim()) newErrors.tournament_name = 'Tournament name is required'
      if (!formData.tournament_date) newErrors.tournament_date = 'Start date is required'
      if (!formData.tournament_end_date) newErrors.tournament_end_date = 'End date is required'
      if (formData.tournament_end_date && formData.tournament_date && new Date(formData.tournament_end_date) < new Date(formData.tournament_date)) {
        newErrors.tournament_end_date = 'End date must be on or after start date'
      }
      if (!formData.location?.trim()) newErrors.location = 'Location is required'
      if (formData.max_players < 2 || formData.max_players > 256) {
        newErrors.max_players = 'Max players must be between 2 and 256'
      }
      if (formData.tables_available < 1) {
        newErrors.tables_available = 'Tables must be at least 1'
      }
      if (!formData.elimination_type) newErrors.elimination_type = 'Tournament type is required'
    }

    if (currentStep === 2) {
      const hasValidPoints = Object.values(formData.points_structure).some(v => {
        const numValue = parseFloat(v)
        return !isNaN(numValue) && numValue > 0
      })
      if (!hasValidPoints) {
        newErrors.points_structure = 'At least one placement must have points greater than 0'
      }
    }

    if (currentStep === 3 && useCompetitorsImport && !competitorsSlug.trim()) {
      newErrors.competitors_slug = 'Competitors slug is required when import is enabled'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleNext = () => {
    if (validateStep() && currentStep < 4) {
      setCurrentStep((step) => (step + 1) as Step)
    }
  }

  const handlePrev = () => {
    if (currentStep > 1) {
      setCurrentStep((step) => (step - 1) as Step)
    }
  }

  const handleInputChange = (field: string, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const handlePointsChange = (placement: string, value: string) => {
    setFormData((prev) => ({
      ...prev,
      points_structure: { ...prev.points_structure, [placement]: value },
    }))
  }

  const handlePlayerToggle = (playerId: string) => {
    setFormData((prev) => ({
      ...prev,
      selectedPlayers: prev.selectedPlayers.includes(playerId)
        ? prev.selectedPlayers.filter((id) => id !== playerId)
        : [...prev.selectedPlayers, playerId],
    }))
  }

  const getAISuggestion = (): { title: string; suggestions: string[]; priority: CoachPriority } => {
    if (currentStep === 1) {
      const suggestions: string[] = []
      let priority: CoachPriority = 'welcome'

      if (!formData.tournament_name && !formData.location) {
        suggestions.push('Pick your association at the top, then enter a tournament name—or choose an upcoming event to fill in basics.')
        if (filteredUpcoming.length > 0) {
          suggestions.push(`You can use the “Quick create” dropdown to load name, dates, and location from ${filteredUpcoming.length} upcoming events.`)
        }
      }

      if (!formData.tournament_name) {
        suggestions.push('Use the official event name when possible; it helps match points from past events.')
        priority = 'welcome'
      }

      if (formData.tournament_name && !formData.tournament_date) {
        suggestions.push('Set the start date for the event.')
        priority = 'medium'
      }

      if (formData.tournament_date && !formData.location) {
        suggestions.push('Add the venue or city so players know where to go.')
        priority = 'medium'
      }

      if (formData.tournament_end_date && formData.tournament_date &&
          new Date(formData.tournament_end_date) < new Date(formData.tournament_date)) {
        suggestions.push('End date must be on or after the start date—fix that before continuing.')
        priority = 'error'
      }

      if (formData.location && formData.tournament_date) {
        const playerCount = formData.max_players || 32
        if (playerCount <= 16) {
          suggestions.push('Small fields often use single elimination for a shorter day.')
        } else if (playerCount <= 64) {
          suggestions.push('Medium fields often use double elimination so players get a second chance.')
        } else {
          suggestions.push('Large fields may use group play into a knockout stage.')
        }
        const recommendedTables = Math.max(2, Math.ceil(playerCount / 8))
        if (formData.tables_available > 0 && formData.tables_available < recommendedTables) {
          suggestions.push(`You may want at least ${recommendedTables} tables for ${playerCount} players to keep things moving.`)
          priority = 'high'
        }
      }

      if (formData.tournament_name && formData.tournament_date && formData.location && formData.max_players >= 2) {
        suggestions.push('Basics look good—go to Points next to set how ranking points are awarded.')
        priority = 'low'
      }

      return { title: 'Step 1: Tournament basics', suggestions, priority }
    }

    if (currentStep === 2) {
      const suggestions: string[] = []
      let priority: CoachPriority = 'medium'

      const hasValidPoints = Object.values(formData.points_structure).some(v => {
        const numValue = parseFloat(v)
        return !isNaN(numValue) && numValue > 0
      })

      if (!hasValidPoints) {
        suggestions.push('Enter points for at least one finishing place, or pick a template below.')
        priority = 'welcome'
      }

      if (templates.length > 0 && !formData.selectedTemplate && !formData.useCustomPoints) {
        suggestions.push('Templates match common tour structures—pick one and adjust if needed.')
        const recommendedTemplate = templates.find((t) => (t.template_name || '').toLowerCase().includes('standard'))
        if (recommendedTemplate) {
          suggestions.push(`“${recommendedTemplate.template_name}” is a balanced default for many events.`)
        }
      }

      if (formData.useCustomPoints) {
        const totalPoints = Object.values(formData.points_structure).reduce((sum, v) => sum + (parseFloat(v) || 0), 0)
        if (totalPoints > 0) {
          const avgPoints = totalPoints / Object.keys(formData.points_structure).length
          suggestions.push(`Your placements total about ${avgPoints.toFixed(0)} points on average across rows you filled.`)
        }
      }

      const playerCount = formData.max_players || 32
      if (playerCount <= 8) {
        suggestions.push('Small events often pay points through the top few places.')
      } else if (playerCount <= 32) {
        suggestions.push('Mid-size events often pay through about the top 8.')
      } else {
        suggestions.push('Large events often pay deeper into the field.')
      }

      if (hasValidPoints) {
        suggestions.push('Points look set—next, choose who is playing.')
        priority = 'low'
      }

      return { title: 'Step 2: Points', suggestions, priority }
    }

    if (currentStep === 3) {
      const suggestions: string[] = []
      let priority: CoachPriority = 'medium'

      if (useCompetitorsImport) {
        suggestions.push('Import pulls a player list from a competitors-pool slug when your org uses that workflow.')
        if (!competitorsSlug.trim()) {
          suggestions.push('Enter the competitors slug from your organizer, or turn off import to pick players manually.')
          priority = 'error'
        } else {
          suggestions.push('Slug is set—you can continue to review and create.')
          priority = 'low'
        }
      } else {
        if (players.length === 0) {
          suggestions.push('No players are available yet. Use “Add new player” below for first-time tour players, or ask an admin to load the roster.')
          priority = 'error'
        } else {
          suggestions.push(`Select players for this event. Start with “From past tournaments” if shown, then add anyone missing.`)
          if (formData.selectedPlayers.length === 0) {
            suggestions.push('Tap players to add them to the field. You need at least two for a bracket.')
            priority = 'welcome'
          }
          const selected = formData.selectedPlayers.length
          const maxAllowed = formData.max_players || 32
          if (selected > 0) {
            if (selected < 2) {
              suggestions.push('Add at least one more player—brackets need at least two entrants.')
              priority = 'high'
            } else if (selected < Math.min(4, maxAllowed)) {
              suggestions.push('You can run a small event, or add more players for a fuller bracket.')
            } else if (selected >= maxAllowed) {
              suggestions.push(`You’ve reached your max field size (${maxAllowed}).`)
              priority = 'low'
            }
          }
        }
      }

      if (!useCompetitorsImport && formData.selectedPlayers.length >= 4) {
        suggestions.push('Roster looks reasonable—review everything on the last step before creating.')
        priority = 'low'
      }

      return { title: 'Step 3: Players', suggestions, priority }
    }

    if (currentStep === 4) {
      const suggestions: string[] = []
      let priority: CoachPriority = 'medium'

      suggestions.push('Read the summary below. After you create the tournament, changes are harder to undo.')

      const issues: string[] = []
      if (!useCompetitorsImport && formData.selectedPlayers.length < 2) {
        issues.push('You need at least two selected players (or use import) before creating.')
      }
      if (formData.max_players > formData.selectedPlayers.length * 1.5 && formData.selectedPlayers.length > 0) {
        issues.push('Max players is much higher than selected—you can lower max players or add more players.')
      }
      if (!Object.values(formData.points_structure).some(v => parseFloat(v) > 0)) {
        issues.push('Point structure has no positive values—fix on step 2.')
      }

      const duration = new Date(formData.tournament_end_date).getTime() - new Date(formData.tournament_date).getTime()
      const days = duration / (1000 * 60 * 60 * 24)
      if (days > 2) {
        suggestions.push('Multi-day event: plan breaks between sessions.')
      }

      if (issues.length > 0) {
        issues.forEach((issue) => suggestions.push(issue))
        priority = 'error'
      } else {
        const playerCount = formData.selectedPlayers.length
        if (playerCount >= 8) {
          suggestions.push('Field size looks competitive.')
          priority = 'low'
        } else if (playerCount >= 2) {
          suggestions.push('Ready to create when you are.')
          priority = 'low'
        }
      }

      suggestions.push('Click “Create tournament” to save and open brackets.')
      suggestions.push('Use Tournament History and Player Performance to track results afterward.')

      return { title: 'Step 4: Review and create', suggestions, priority }
    }

    return { title: '', suggestions: [], priority: 'low' }
  }

  const wizardPageShellClass =
    'flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4 md:p-8'

  if (entryMode === 'choose') {
    return (
      <div className={wizardPageShellClass}>
        <div className="max-w-2xl mx-auto">
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-white mb-2">
              {getText('tournament_wizard.title', '🎯 New Tournament')}
            </h1>
            <p className="text-slate-400">
              Start a custom event from scratch, or set up one already on the WPBA/WPA calendar with prefilled details you can edit.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <button
              type="button"
              onClick={beginNewTournament}
              className="text-left rounded-xl border-2 border-slate-600 bg-slate-800/60 p-6 hover:border-sky-500/60 hover:bg-slate-800 transition-all"
            >
              <span className="text-3xl mb-3 block" aria-hidden>✨</span>
              <h2 className="text-xl font-bold text-white mb-2">Start new tournament</h2>
              <p className="text-sm text-slate-400 leading-relaxed">
                Blank setup for a local event, league stop, or anything not on the official tour calendar.
              </p>
            </button>

            <button
              type="button"
              onClick={beginScheduledPicker}
              className="text-left rounded-xl border-2 border-emerald-700/40 bg-emerald-950/20 p-6 hover:border-emerald-500/60 hover:bg-emerald-950/30 transition-all"
            >
              <span className="text-3xl mb-3 block" aria-hidden>📅</span>
              <h2 className="text-xl font-bold text-white mb-2">Set up scheduled tournament</h2>
              <p className="text-sm text-slate-400 leading-relaxed">
                Pick an upcoming WPBA/WPA event — we prefill name, dates, location, and field size from calendars and news. You can change anything.
              </p>
              {directorUpcoming.length > 0 && (
                <p className="text-xs text-emerald-400 mt-3">{directorUpcoming.length} upcoming event(s) for your association(s)</p>
              )}
            </button>
          </div>

          <p className="text-center text-sm text-slate-500 mt-8">
            Browse the full calendar on{' '}
            <Link to="/future-tournaments" className="text-sky-400 hover:underline">
              Future Tournaments
            </Link>
            .
          </p>
        </div>
      </div>
    )
  }

  if (entryMode === 'pick-scheduled') {
    return (
      <div className={wizardPageShellClass}>
        <div className="max-w-2xl mx-auto">
          <div className="mb-6">
            <button
              type="button"
              onClick={() => setEntryMode('choose')}
              className="text-sm text-slate-400 hover:text-white mb-4"
            >
              ← Back to start options
            </button>
            <h1 className="text-3xl font-bold text-white mb-2">Set up scheduled tournament</h1>
            <p className="text-slate-400">
              Choose an upcoming event to prefill the wizard. All values stay editable before you create the tournament.
            </p>
          </div>

          {inProgressTournaments.length > 0 && (
            <section className="mb-6 rounded-xl border border-amber-700/40 bg-amber-950/20 p-4">
              <h2 className="text-sm font-semibold text-amber-200 mb-3">Continue in-app setup</h2>
              <ul className="space-y-2">
                {inProgressTournaments.map((t) => (
                  <li
                    key={t.tournament_id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-900/50 px-3 py-2"
                  >
                    <div>
                      <p className="text-white font-medium">{t.tournament_name}</p>
                      <p className="text-xs text-slate-400 capitalize">
                        {t.status.replace(/_/g, ' ')} · {t.actual_players}/{t.max_players} players
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => navigate('/tournament-wizard/bracket', { state: { tournamentId: t.tournament_id } })}
                      className="shrink-0 px-3 py-1.5 text-sm font-medium rounded-lg bg-amber-600 hover:bg-amber-500 text-white"
                    >
                      Continue setup →
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {directorUpcoming.length === 0 ? (
            <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-8 text-center text-slate-400">
              <p className="mb-4">No upcoming events match your association(s) right now.</p>
              <button
                type="button"
                onClick={beginNewTournament}
                className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-sm font-medium"
              >
                Start new tournament instead
              </button>
            </div>
          ) : (
            <ul className="space-y-3">
              {directorUpcoming.map((evt) => (
                <li
                  key={upcomingEventKey(evt)}
                  className="rounded-xl border border-slate-700 bg-slate-800/50 p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
                >
                  <div>
                    <p className="font-semibold text-white">{evt.name}</p>
                    <p className="text-sm text-slate-400 mt-1">
                      {evt.association}
                      {formatEventDateLabel(evt) ? ` · ${formatEventDateLabel(evt)}` : ''}
                      {evt.location ? ` · ${evt.location}` : ''}
                      {evt.max_players ? ` · ${evt.max_players} players` : ''}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => beginScheduledEvent(upcomingEventKey(evt))}
                    className="shrink-0 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold"
                  >
                    Continue setup →
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4 md:p-8">
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <div className="flex flex-wrap items-start justify-between gap-3 mb-2">
            <h1 className="text-4xl font-bold text-white">
              {getText('tournament_wizard.title', '🎯 Tournament Wizard')}
            </h1>
            <button
              type="button"
              onClick={() => setEntryMode('choose')}
              className="text-sm text-slate-400 hover:text-white shrink-0"
            >
              ← Start options
            </button>
          </div>
          {wizardSource === 'scheduled' && formData.tournament_name && (
            <p className="text-sm text-emerald-400 mb-2">
              Setting up scheduled event: <strong>{formData.tournament_name}</strong> — edit any field below.
            </p>
          )}
          {wizardSource === 'new' && (
            <p className="text-sm text-sky-400 mb-2">Custom new tournament — enter all details manually.</p>
          )}
          <p className="text-slate-400">
            {getText(
              'tournament_wizard.intro_text',
              'Walk through name, points, players, and launch — we keep each step short and clear.',
            )}
          </p>
        </div>

        <div className="flex justify-between mb-8">
          {[1, 2, 3, 4].map((step) => (
            <div key={step} className="flex flex-col items-center flex-1">
              <button
                onClick={() => step < currentStep && setCurrentStep(step as Step)}
                className={`w-10 h-10 rounded-full font-semibold transition-all ${
                  step === currentStep
                    ? 'bg-blue-600 text-white shadow-lg'
                    : step < currentStep
                      ? 'bg-green-600 text-white cursor-pointer'
                      : 'bg-slate-700 text-slate-400'
                }`}
                disabled={step > currentStep}
              >
                {step < currentStep ? '✓' : step}
              </button>
              <p className="text-xs text-slate-400 mt-2 text-center">
                {step === 1 && 'Basic Info'}
                {step === 2 && 'Points'}
                {step === 3 && 'Players'}
                {step === 4 && 'Review'}
              </p>
            </div>
          ))}
        </div>

        <div className="bg-slate-800/50 backdrop-blur rounded-lg border border-slate-700 p-6 md:p-8">
          {/* Welcome Message for New Users */}
          {currentStep === 1 && !formData.tournament_name && !showAIAssistant && (
            <div className="mb-6 bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-500/50 rounded-lg p-5 shadow-lg">
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-blue-500 rounded-full flex items-center justify-center">
                    <span className="text-2xl">🎯</span>
                  </div>
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-bold text-white mb-2">Welcome</h3>
                  <p className="text-slate-300 mb-3 leading-relaxed">
                    Optional tips as you go: turn on the assistant for suggestions on format, points, and player count based on what you enter.
                  </p>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setShowAIAssistant(true)}
                      className="px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg font-semibold hover:from-purple-700 hover:to-blue-700 transition-all shadow-md"
                    >
                      🚀 Show tips while I set up
                    </button>
                    <span className="text-xs text-slate-400">You can skip this anytime</span>
                  </div>
                </div>
                <button
                  onClick={() => setAiDismissed(true)}
                  className="text-slate-400 hover:text-white text-xl leading-none transition-colors hover:bg-slate-700/50 rounded p-1"
                  title="Skip welcome"
                >
                  ×
                </button>
              </div>
            </div>
          )}

          {!aiDismissed && showAIAssistant && (() => {
            const aiGuidance = getAISuggestion()
            const priorityColors: Record<CoachPriority, string> = {
              welcome: 'border-purple-500/50 bg-gradient-to-r from-purple-950/30 to-indigo-950/20 shadow-purple-500/10',
              medium: 'border-blue-500/50 bg-gradient-to-r from-blue-950/30 to-purple-950/20 shadow-blue-500/20',
              high: 'border-amber-500/50 bg-gradient-to-r from-amber-950/30 to-orange-950/20 shadow-amber-500/10',
              error: 'border-red-500/50 bg-gradient-to-r from-red-950/30 to-red-900/20 shadow-red-500/20',
              low: 'border-green-500/50 bg-gradient-to-r from-green-950/30 to-emerald-950/20 shadow-green-500/20',
            }
            const priorityIcons: Record<CoachPriority, string> = {
              welcome: '→',
              medium: '💡',
              high: '!',
              error: '!',
              low: '✓',
            }
            const priorityLabels: Record<CoachPriority, string> = {
              welcome: 'Getting started',
              medium: 'Helpful guidance',
              high: 'Heads up',
              error: 'Action required',
              low: 'All set',
            }
            const badgeBg: Record<CoachPriority, string> = {
              welcome: 'bg-violet-600 text-white',
              medium: 'bg-blue-500 text-white',
              high: 'bg-amber-500 text-white',
              error: 'bg-red-500 text-white',
              low: 'bg-green-500 text-white',
            }

            return (
              <div className={`mb-6 border rounded-lg p-5 shadow-lg ${priorityColors[aiGuidance.priority]} transition-all duration-300`}>
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="relative">
                      <img
                        src={avatarUrl}
                        alt="AI Coach Avatar"
                        className="w-12 h-12 rounded-full object-cover border-2 border-blue-400 shadow-lg"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = DEFAULT_AVATAR
                        }}
                      />
                      <div
                        className={`absolute -top-1 -right-1 min-w-[1.25rem] h-5 px-0.5 rounded-full flex items-center justify-center text-xs font-bold shadow-md ${badgeBg[aiGuidance.priority]}`}
                      >
                        {priorityIcons[aiGuidance.priority]}
                      </div>
                    </div>
                    <div>
                      <p className="text-base font-bold text-white">AI Tournament Coach</p>
                      <p className="text-xs text-slate-400">{priorityLabels[aiGuidance.priority]}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => setAiDismissed(true)}
                    className="text-slate-400 hover:text-white text-xl leading-none transition-colors hover:bg-slate-700/50 rounded p-1"
                    title="Dismiss coach"
                  >
                    ×
                  </button>
                </div>

                <div className="space-y-3">
                  <h4 className="text-lg font-semibold text-white flex items-center gap-2">
                    {aiGuidance.title}
                  </h4>

                  <div className="space-y-3">
                    {aiGuidance.suggestions.map((suggestion, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-3 p-3 rounded-md transition-all bg-slate-800/40 border border-slate-700/40"
                      >
                        <span className="text-sm flex-shrink-0 mt-0.5 text-slate-500">•</span>
                        <p className="text-sm leading-relaxed flex-1 text-slate-300">{suggestion}</p>
                      </div>
                    ))}
                  </div>

                  {aiGuidance.priority === 'high' && (
                    <div className="mt-4 p-3 bg-amber-900/25 border border-amber-700/40 rounded-md flex items-center gap-2">
                      <span className="text-amber-400 text-lg" aria-hidden>
                        !
                      </span>
                      <p className="text-sm text-amber-pool_opt_in">Optional: consider the note above before you continue.</p>
                    </div>
                  )}

                  {aiGuidance.priority === 'error' && (
                    <div className="mt-4 p-3 bg-red-900/30 border border-red-700/50 rounded-md flex items-center gap-2">
                      <span className="text-red-400 text-lg" aria-hidden>
                        !
                      </span>
                      <p className="text-sm text-red-200">Fix the items above before creating the tournament.</p>
                    </div>
                  )}

                  {currentStep === 1 && !formData.tournament_name && aiGuidance.priority === 'welcome' && (
                    <div className="mt-4 pt-3 border-t border-slate-600/50">
                      <p className="text-xs text-slate-400 leading-relaxed">
                        These tips update as you fill the form. Red appears only when something must be fixed.
                      </p>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-600/50">
                  <button
                    onClick={() => setAiDismissed(true)}
                    className="text-xs text-slate-400 hover:text-blue-400 underline transition-colors"
                  >
                    Hide coach for now
                  </button>
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span>Step {currentStep} of 4</span>
                    <span className="text-slate-600">•</span>
                    <span className="text-blue-400">AI-Powered Guidance</span>
                  </div>
                </div>
              </div>
            )
          })()}

          {aiDismissed && (
            <div className="mb-4">
              <button
                onClick={() => {
                  setShowAIAssistant(true)
                  setAiDismissed(false)
                }}
                className="text-sm text-blue-400 hover:text-blue-300 underline flex items-center gap-1"
              >
                <img
                  src={avatarUrl}
                  alt="AI Coach Avatar"
                  className="w-5 h-5 rounded-full object-cover flex-shrink-0 border border-blue-400"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = DEFAULT_AVATAR
                  }}
                />
                Show AI Coach
              </button>
            </div>
          )}

          {currentStep === 1 && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-white mb-6">Tournament Details</h2>

              <div>
                <label className="block text-sm font-medium text-slate-200 mb-2">
                  Association <span className="text-red-500">*</span>
                </label>
                <select
                  value={selectedAssociation}
                  onChange={(e) => {
                    setSelectedAssociation(e.target.value)
                    setBracketTemplateId(null)
                  }}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                >
                  <option value="">Select association…</option>
                  {(myAssociationsData?.associations ?? []).map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
                {errors.association && <p className="text-red-500 text-sm mt-1">{errors.association}</p>}
                <p className="text-xs text-slate-400 mt-1">
                  Directors only see associations assigned to their account. This scopes players, bracket presets, and upcoming-event suggestions.
                </p>
              </div>

              {selectedAssociation && (
                <div className="rounded-lg border border-slate-600 bg-slate-800/40 p-4 space-y-4">
                  <h3 className="text-lg font-semibold text-white">Bracket template</h3>
                  <p className="text-sm text-slate-400">
                    Pick a standard size or a saved template. This sets max players and elimination format. Official rules:{' '}
                    {isWpbaAssociation(selectedAssociation) ? (
                      <Link to="/rules?tab=wpba" className="text-sky-400 hover:underline">
                        WPBA rules & points
                      </Link>
                    ) : (
                      <Link to="/rules?tab=wpa" className="text-sky-400 hover:underline">
                        WPA rules & points
                      </Link>
                    )}
                    .
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {([16, 32, 64, 80] as const).map((n) => {
                      const fmt = 'single_elimination' as const
                      const t = findBracketPreset(n, fmt)
                      return (
                        <button
                          key={n}
                          type="button"
                          disabled={!t}
                          onClick={() => t && applyBracketTemplate(t)}
                          className="rounded-lg border border-slate-600 px-3 py-2 text-sm text-white hover:bg-slate-700 disabled:opacity-40"
                        >
                          {n} players (single elim.)
                        </button>
                      )
                    })}
                    <button
                      type="button"
                      onClick={() => setShowCustomBracket((s) => !s)}
                      className={`rounded-lg border px-3 py-2 text-sm ${
                        showCustomBracket
                          ? 'border-sky-500 bg-sky-900/30 text-sky-200'
                          : 'border-slate-600 text-white hover:bg-slate-700'
                      }`}
                    >
                      Custom
                    </button>
                  </div>
                  {bracketTemplates.filter((t) => !t.is_system).length > 0 && (
                    <div>
                      <label className="block text-sm font-medium text-slate-200 mb-1">Your saved templates</label>
                      <select
                        value={bracketTemplateId ?? ''}
                        onChange={(e) => {
                          const id = e.target.value ? parseInt(e.target.value, 10) : NaN
                          const t = bracketTemplates.find((x) => x.id === id)
                          if (t) applyBracketTemplate(t)
                          else setBracketTemplateId(null)
                        }}
                        className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                      >
                        <option value="">—</option>
                        {bracketTemplates
                          .filter((t) => !t.is_system)
                          .map((t) => (
                            <option key={t.id} value={t.id}>
                              {t.name}
                            </option>
                          ))}
                      </select>
                    </div>
                  )}
                  {showCustomBracket && (
                    <div className="grid gap-3 md:grid-cols-2 border border-slate-700 rounded-lg p-3">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Entrants (field size)</label>
                        <input
                          type="number"
                          min={2}
                          max={256}
                          value={customEntrantCount}
                          onChange={(e) => setCustomEntrantCount(parseInt(e.target.value, 10) || 2)}
                          className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Bracket draw size (power of 2, ≥ entrants)</label>
                        <input
                          type="number"
                          min={2}
                          max={512}
                          value={customDrawSize}
                          onChange={(e) => setCustomDrawSize(parseInt(e.target.value, 10) || 2)}
                          className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Format</label>
                        <select
                          value={customFormat}
                          onChange={(e) =>
                            setCustomFormat(e.target.value as 'single_elimination' | 'double_elimination')
                          }
                          className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                        >
                          <option value="single_elimination">Single elimination</option>
                          <option value="double_elimination">Double elimination</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Bye strategy</label>
                        <select
                          value={customByeStrategy}
                          onChange={(e) => setCustomByeStrategy(e.target.value)}
                          className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                        >
                          <option value="top_seed">Top seeds receive byes</option>
                          <option value="random">Random byes</option>
                        </select>
                      </div>
                      <div className="md:col-span-2 flex flex-wrap gap-2 items-end">
                        <button
                          type="button"
                          onClick={applyCustomDrawToForm}
                          className="rounded-lg bg-slate-600 px-4 py-2 text-white text-sm hover:bg-slate-500"
                        >
                          Use this draw
                        </button>
                        <input
                          type="text"
                          value={saveTemplateName}
                          onChange={(e) => setSaveTemplateName(e.target.value)}
                          placeholder="Name to save as template (optional)"
                          className="flex-1 min-w-[12rem] px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                        />
                        <button
                          type="button"
                          disabled={saveBracketTemplateMutation.isPending}
                          onClick={() => saveBracketTemplateMutation.mutate()}
                          className="rounded-lg bg-sky-600 px-4 py-2 text-white text-sm hover:bg-sky-500 disabled:opacity-50"
                        >
                          {saveBracketTemplateMutation.isPending ? 'Saving…' : 'Save as template'}
                        </button>
                      </div>
                    </div>
                  )}
                  <p className="text-xs text-slate-500">
                    Selected: max {formData.max_players} players ·{' '}
                    {bracketTemplateId ? `template #${bracketTemplateId}` : 'no saved template id (custom or unset)'}
                  </p>
                </div>
              )}

              <div className="rounded-lg border border-slate-600 bg-slate-800/40 p-4 space-y-3">
                <h3 className="text-lg font-semibold text-white">Game type</h3>
                {isWpbaAssociation(selectedAssociation) ? (
                  <>
                    <p className="text-sm text-slate-400">
                      WPBA events use 9-ball by default. Only an administrator can select a different game type.
                    </p>
                    <select
                      value={gameType}
                      disabled={!(isAdmin || isSuperAdmin)}
                      onChange={(e) => setGameType(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white disabled:opacity-60"
                    >
                      <option value="9_ball">9-ball</option>
                      <option value="10_ball">10-ball</option>
                      <option value="8_ball">8-ball</option>
                      <option value="straight_pool">Straight pool</option>
                    </select>
                  </>
                ) : (
                  <>
                    <p className="text-sm text-slate-400">Choose the game for this WPA-side event.</p>
                    <select
                      value={gameType}
                      onChange={(e) => setGameType(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                    >
                      <option value="9_ball">9-ball</option>
                      <option value="10_ball">10-ball</option>
                      <option value="8_ball">8-ball</option>
                      <option value="straight_pool">Straight pool</option>
                      <option value="other">Other / see rules</option>
                    </select>
                  </>
                )}
              </div>

              {filteredUpcoming.length > 0 && (
                <div className="bg-blue-900/20 border border-blue-700/30 rounded-lg p-4">
                  <label className="block text-sm font-medium text-blue-300 mb-2">
                    Quick create from upcoming event (matches your association)
                  </label>
                  <select
                    onChange={(e) => e.target.value && handlePrefillFromEvent(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    value={selectedUpcomingKey}
                  >
                    <option value="">Select an upcoming event to prefill...</option>
                    {filteredUpcoming.map((event) => (
                      <option key={upcomingEventKey(event)} value={upcomingEventKey(event)}>
                        {event.name} {event.date ? `(${new Date(event.date).toLocaleDateString()})` : ''} - {event.association}
                        {event.max_players ? ` · ${event.max_players} players` : ''}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-slate-400 mt-2">
                    Prefills name, dates, location, player count, and format when available (from calendars + RSS news). All fields stay editable.
                  </p>
                  {prefillSources.length > 0 && (
                    <ul className="mt-3 space-y-1 text-xs text-slate-300">
                      {prefillSources.map((s) => (
                        <li key={`${s.field}-${s.source}`}>
                          <span className="text-blue-300">{s.label}</span>
                          {' '}from {s.source}
                          {s.sourceUrl ? (
                            <>
                              {' '}
                              <a
                                href={s.sourceUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sky-400 hover:underline"
                              >
                                (source)
                              </a>
                            </>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-200 mb-2">
                  Tournament Name <span className="text-red-500">*</span>
                </label>
                <input
                  value={formData.tournament_name}
                  onChange={(e) => handleInputChange('tournament_name', e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="e.g., Spring League 2024"
                />
                {errors.tournament_name && <p className="text-red-500 text-sm mt-1">{errors.tournament_name}</p>}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">
                    Start Date <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    value={formData.tournament_date}
                    onChange={(e) => handleInputChange('tournament_date', e.target.value)}
                    className="w-full min-w-0 px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  />
                  {errors.tournament_date && <p className="text-red-500 text-sm mt-1">{errors.tournament_date}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">
                    End Date <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    value={formData.tournament_end_date}
                    onChange={(e) => handleInputChange('tournament_end_date', e.target.value)}
                    min={formData.tournament_date}
                    className="w-full min-w-0 px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  />
                  {errors.tournament_end_date && <p className="text-red-500 text-sm mt-1">{errors.tournament_end_date}</p>}
                  <p className="text-xs text-slate-400 mt-1">Same as start date for single-day tournaments</p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">
                    Max Players <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    value={formData.max_players || ''}
                    onChange={(e) => {
                      const val = e.target.value
                      if (!val || val === '') {
                        handleInputChange('max_players', 0)
                      } else {
                        const num = parseInt(val, 10)
                        if (!isNaN(num)) {
                          handleInputChange('max_players', num)
                        }
                      }
                    }}
                    min="2"
                    max="256"
                    step="1"
                    placeholder="e.g., 64"
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  />
                  {errors.max_players && <p className="text-red-500 text-sm mt-1">{errors.max_players}</p>}
                  <p className="text-xs text-slate-400 mt-1">Min: 2, Max: 256 (e.g., 8, 16, 32, 64, 128)</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">
                    Tables <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    value={formData.tables_available || ''}
                    onChange={(e) => {
                      const val = e.target.value
                      if (!val || val === '') {
                        handleInputChange('tables_available', 0)
                      } else {
                        const num = parseInt(val, 10)
                        if (!isNaN(num)) {
                          handleInputChange('tables_available', num)
                        }
                      }
                    }}
                    min="1"
                    step="1"
                    placeholder="e.g., 12"
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  />
                  {errors.tables_available && <p className="text-red-500 text-sm mt-1">{errors.tables_available}</p>}
                  <p className="text-xs text-slate-400 mt-1">Number of tables available for matches</p>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-200 mb-2">
                  Location <span className="text-red-500">*</span>
                </label>
                <input
                  value={formData.location}
                  onChange={(e) => handleInputChange('location', e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="e.g., Billiards Cafe"
                />
                {errors.location && <p className="text-red-500 text-sm mt-1">{errors.location}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-200 mb-2">
                  Entry Fee (optional)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-slate-400 font-medium">$</span>
                  <input
                    type="number"
                    min="0"
                    value={(formData.entry_fee_cents / 100) || ''}
                    onChange={(e) => {
                      const val = e.target.value
                      if (!val) {
                        handleInputChange('entry_fee_cents', 0)
                      } else {
                        const num = parseFloat(val)
                        if (!isNaN(num) && num >= 0) {
                          handleInputChange('entry_fee_cents', Math.round(num * 100))
                        }
                      }
                    }}
                    className="w-full pl-7 pr-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="Enter amount in dollars (e.g., 500, 1000, 2500)"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-200 mb-2">
                  Tournament Type <span className="text-red-500">*</span>
                </label>
                <select
                  value={formData.elimination_type}
                  onChange={(e) => handleInputChange('elimination_type', e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                >
                  <option value="single">Single Elimination</option>
                  <option value="double">Double Elimination</option>
                  <option value="round_robin">Round Robin</option>
                  <option value="group_stage">Group Stage + Playoffs</option>
                </select>
              </div>

              {formData.elimination_type === 'group_stage' && (
                <div className="space-y-4 p-4 bg-slate-800 rounded-lg border border-slate-600">
                  <h3 className="text-lg font-semibold text-white">Group Stage Configuration</h3>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-200 mb-2">
                        Number of Groups
                      </label>
                      <select
                        value={formData.num_groups || ''}
                        onChange={(e) => handleInputChange('num_groups', parseInt(e.target.value) || undefined)}
                        className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                      >
                        <option value="">Auto</option>
                        <option value="2">2 Groups</option>
                        <option value="3">3 Groups</option>
                        <option value="4">4 Groups</option>
                        <option value="6">6 Groups</option>
                        <option value="8">8 Groups</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-slate-200 mb-2">
                        Format Within Groups
                      </label>
                      <select
                        value={formData.group_format || 'round_robin'}
                        onChange={(e) => handleInputChange('group_format', e.target.value as 'round_robin' | 'single_elimination')}
                        className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                      >
                        <option value="round_robin">Round Robin</option>
                        <option value="single_elimination">Single Elimination</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-slate-200 mb-2">
                        Players Advancing per Group
                      </label>
                      <select
                        value={formData.group_advance_count || 1}
                        onChange={(e) => handleInputChange('group_advance_count', parseInt(e.target.value))}
                        className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                      >
                        <option value="1">1 Player</option>
                        <option value="2">2 Players</option>
                        <option value="3">3 Players</option>
                        <option value="4">4 Players</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-slate-200 mb-2">
                        Players per Group (Optional)
                      </label>
                      <input
                        type="number"
                        value={formData.players_per_group || ''}
                        onChange={(e) => handleInputChange('players_per_group', parseInt(e.target.value) || undefined)}
                        className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                        placeholder="Auto-calculated"
                        min="2"
                        max="32"
                      />
                    </div>
                  </div>

                  <div className="text-sm text-slate-400 mt-2">
                    <p>• Groups play their matches first, then top players advance to playoffs</p>
                    <p>• Leave "Number of Groups" as "Auto" for intelligent defaults based on player count</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {currentStep === 2 && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-white mb-2">Point Structure</h2>
              <p className="text-sm text-slate-400 mb-4">
                Official reference:{' '}
                {isWpbaAssociation(selectedAssociation) ? (
                  <Link to="/rules?tab=wpba" className="text-sky-400 hover:text-sky-300 underline">
                    Rules → WPBA (9-ball & point system)
                  </Link>
                ) : (
                  <Link to="/rules?tab=wpa" className="text-sky-400 hover:text-sky-300 underline">
                    Rules → WPA (rulebooks & licenses)
                  </Link>
                )}
                .
              </p>

              {errors.points_structure && (
                <div className="bg-red-900/20 border border-red-700 rounded-lg p-4">
                  <p className="text-red-300 text-sm">{errors.points_structure}</p>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-200 mb-2">Use Template</label>
                <select
                  value={formData.selectedTemplate || ''}
                  onChange={(e) => handleInputChange('selectedTemplate', e.target.value ? parseInt(e.target.value) : undefined)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                >
                  <option value="">Select a template...</option>
                  {templates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.template_name} ({template.elimination_type})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="useCustomPoints"
                  checked={formData.useCustomPoints}
                  onChange={(e) => handleInputChange('useCustomPoints', e.target.checked)}
                  className="w-4 h-4 text-blue-600 bg-slate-700 border-slate-600 rounded focus:ring-2 focus:ring-blue-500"
                />
                <label htmlFor="useCustomPoints" className="ml-2 text-sm font-medium text-slate-200">
                  Use Custom Points
                </label>
              </div>

              {(formData.useCustomPoints || !formData.selectedTemplate) && (
                <div className="space-y-4">
                  <p className="text-sm text-slate-400">Define points for each placement</p>
                  <div className="space-y-3">
                    {Object.entries(formData.points_structure).map(([placement]) => (
                      <div key={placement} className="flex gap-3 items-end">
                        <div className="flex-1">
                          <label className="block text-xs font-medium text-slate-300 mb-1">Place {placement}</label>
                          <input
                            type="number"
                            value={formData.points_structure[placement]}
                            onChange={(e) => handlePointsChange(placement, e.target.value)}
                            className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                            placeholder="Points"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {formData.selectedTemplate && !formData.useCustomPoints && (
                <div className="bg-blue-900/20 border border-blue-700 rounded-lg p-4">
                  <h3 className="font-semibold text-blue-200 mb-3">Template Points</h3>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    {Object.entries(formData.points_structure).map(([placement, points]) => (
                      <div key={placement} className="flex justify-between">
                        <span className="text-slate-400">Place {placement}:</span>
                        <span className="text-blue-200 font-semibold">{points}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {currentStep === 3 && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-white mb-6">Select Players</h2>

              <div className="bg-slate-900/40 border border-slate-700 rounded-lg p-4 space-y-4">
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={useCompetitorsImport}
                    onChange={(e) => {
                      const enabled = e.target.checked
                      setUseCompetitorsImport(enabled)
                      if (enabled) {
                        setFormData((prev) => ({ ...prev, selectedPlayers: [] }))
                      }
                    }}
                    className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-700 text-blue-500 focus:ring-2 focus:ring-blue-500/40"
                  />
                  <span>
                    <span className="block text-sm font-medium text-slate-200">Import players and matches from competitors</span>
                    <span className="block text-xs text-slate-400 mt-1">
                      Paste a competitors tournament slug to load players, matches, and placements into this tournament.
                    </span>
                  </span>
                </label>

                {useCompetitorsImport && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-slate-200 mb-2">Competitors slug</label>
                      <input
                        value={competitorsSlug}
                        onChange={(e) => setCompetitorsSlug(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                        placeholder="2026-wpba-classics-players-championship"
                      />
                      {errors.competitors_slug && <p className="text-red-500 text-sm mt-1">{errors.competitors_slug}</p>}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-200 mb-2">Race to</label>
                      <input
                        type="number"
                        min={1}
                        value={competitorsRaceTo}
                        onChange={(e) => setCompetitorsRaceTo(parseInt(e.target.value) || 1)}
                        className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                      />
                    </div>
                    <div className="md:col-span-3">
                      <label className="flex items-center gap-2 text-sm text-slate-200">
                        <input
                          type="checkbox"
                          checked={competitorsGenerateBracket}
                          onChange={(e) => setCompetitorsGenerateBracket(e.target.checked)}
                          className="h-4 w-4 rounded border-slate-600 bg-slate-700 text-blue-500 focus:ring-2 focus:ring-blue-500/40"
                        />
                        Generate bracket if none exists
                      </label>
                    </div>
                  </div>
                )}
              </div>

              <div className={useCompetitorsImport ? 'opacity-50 pointer-events-none space-y-4' : 'space-y-4'}>
                {!useCompetitorsImport && (
                  <>
                    <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
                      <input
                        type="search"
                        value={playerSearch}
                        onChange={(e) => setPlayerSearch(e.target.value)}
                        placeholder="Search players…"
                        className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                      />
                      <button
                        type="button"
                        onClick={() => setShowNewPlayerForm((v) => !v)}
                        className="rounded-lg border border-sky-600 px-4 py-2 text-sm text-sky-200 hover:bg-sky-900/30 whitespace-nowrap"
                      >
                        {showNewPlayerForm ? 'Close new player form' : 'Add new player'}
                      </button>
                    </div>

                    {showNewPlayerForm && (
                      <div className="rounded-lg border border-slate-600 bg-slate-800/60 p-4 space-y-3">
                        <p className="text-sm text-slate-400">
                          For players new to the tour. Fields marked * are required.
                        </p>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <input
                            value={newPlayerFirst}
                            onChange={(e) => setNewPlayerFirst(e.target.value)}
                            placeholder="First name *"
                            className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                          />
                          <input
                            value={newPlayerLast}
                            onChange={(e) => setNewPlayerLast(e.target.value)}
                            placeholder="Last name *"
                            className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                          />
                          <input
                            value={newPlayerCountry}
                            onChange={(e) => setNewPlayerCountry(e.target.value)}
                            placeholder="Country (optional)"
                            className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                          />
                          <input
                            value={newPlayerLicense}
                            onChange={(e) => setNewPlayerLicense(e.target.value)}
                            placeholder="License # (optional)"
                            className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                          />
                        </div>
                        <button
                          type="button"
                          disabled={createPlayerMutation.isPending || !newPlayerFirst.trim() || !newPlayerLast.trim()}
                          onClick={() =>
                            createPlayerMutation.mutate({
                              first_name: newPlayerFirst.trim(),
                              last_name: newPlayerLast.trim(),
                              nationality: newPlayerCountry.trim() || undefined,
                              license_number: newPlayerLicense.trim() || undefined,
                            })
                          }
                          className="rounded-lg bg-sky-600 px-4 py-2 text-white text-sm hover:bg-sky-500 disabled:opacity-50"
                        >
                          {createPlayerMutation.isPending ? 'Creating…' : 'Create and select player'}
                        </button>
                      </div>
                    )}

                    {activeBracketTemplate &&
                      activeBracketTemplate.bracket_draw_size > formData.selectedPlayers.length && (
                        <p className="text-sm text-amber-200/90 bg-amber-950/30 border border-amber-800/50 rounded-lg px-3 py-2">
                          Bracket draw is {activeBracketTemplate.bracket_draw_size} slots; you selected{' '}
                          {formData.selectedPlayers.length}. Remaining slots can be byes (seeded) or fill later.
                        </p>
                      )}

                    {selectedAssociation && historyFiltered.length > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold text-slate-200 mb-2">
                          From past {selectedAssociation} tournaments
                        </h3>
                        <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                          {historyFiltered.map((player) => (
                            <label
                              key={player.player_id}
                              className="flex items-center p-3 bg-violet-900/20 hover:bg-violet-900/30 border border-violet-700/40 rounded-lg cursor-pointer transition-colors"
                            >
                              <input
                                type="checkbox"
                                checked={formData.selectedPlayers.includes(player.player_id)}
                                onChange={() => handlePlayerToggle(player.player_id)}
                                className="w-4 h-4 text-violet-500 bg-slate-600 border-slate-500 rounded focus:ring-2 focus:ring-violet-500"
                              />
                              <div className="ml-3 flex-1">
                                <p className="font-medium text-white">
                                  {player.first_name} {player.last_name}
                                </p>
                              </div>
                              {player.fargo_score && (
                                <span className="text-sm font-semibold text-violet-300">FR: {player.fargo_score}</span>
                              )}
                            </label>
                          ))}
                        </div>
                      </div>
                    )}

                    <div>
                      <h3 className="text-sm font-semibold text-slate-200 mb-2">All players in pool</h3>
                      <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                        {players.length === 0 ? (
                          <p className="text-slate-400 text-center py-6">
                            No players match this association yet. Use &quot;Add new player&quot; for first-time tour
                            players.
                          </p>
                        ) : otherPlayersFiltered.length === 0 ? (
                          <p className="text-slate-400 text-center py-4">No matches for your search.</p>
                        ) : (
                          otherPlayersFiltered.map((player) => (
                            <label
                              key={player.player_id}
                              className="flex items-center p-3 bg-slate-700/50 hover:bg-slate-700 border border-slate-600 rounded-lg cursor-pointer transition-colors"
                            >
                              <input
                                type="checkbox"
                                checked={formData.selectedPlayers.includes(player.player_id)}
                                onChange={() => handlePlayerToggle(player.player_id)}
                                className="w-4 h-4 text-blue-600 bg-slate-600 border-slate-500 rounded focus:ring-2 focus:ring-blue-500"
                              />
                              <div className="ml-3 flex-1">
                                <p className="font-medium text-white">
                                  {player.first_name} {player.last_name}
                                  {player.license_overdue && (
                                    <span
                                      className="ml-2 px-2 py-0.5 text-xs font-semibold bg-amber-500/30 text-amber-200 rounded"
                                      title="License overdue"
                                    >
                                      License overdue
                                    </span>
                                  )}
                                </p>
                                {player.nickname && (
                                  <p className="text-xs text-slate-400">&quot;{player.nickname}&quot;</p>
                                )}
                              </div>
                              {player.fargo_score && (
                                <span className="text-sm font-semibold text-blue-300">FR: {player.fargo_score}</span>
                              )}
                            </label>
                          ))
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>

              {formData.selectedPlayers.length > 0 && (
                <div className="bg-green-900/20 border border-green-700 rounded-lg p-4">
                  <p className="text-green-200">
                    <span className="font-semibold">{formData.selectedPlayers.length}</span> player(s) selected
                    {formData.max_players > 0 && (
                      <span className="text-green-300/90"> · max field {formData.max_players}</span>
                    )}
                  </p>
                </div>
              )}
            </div>
          )}

          {currentStep === 4 && (
            <div className="space-y-6">
              <h2 className="text-2xl font-bold text-white mb-6">Review Tournament</h2>

              <div className="space-y-4">
                <div className="bg-slate-700/50 rounded-lg p-4">
                  <h3 className="font-semibold text-slate-200 mb-3">Tournament Details</h3>
                  <dl className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-slate-400">Association:</dt>
                      <dd className="text-white font-medium">{selectedAssociation || '—'}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-400">Game type:</dt>
                      <dd className="text-white font-medium">{gameType.replace('_', '-')}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-400">Name:</dt>
                      <dd className="text-white font-medium">{formData.tournament_name}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-400">Start Date:</dt>
                      <dd className="text-white font-medium">{formData.tournament_date}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-400">End Date:</dt>
                      <dd className="text-white font-medium">{formData.tournament_end_date}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-400">Location:</dt>
                      <dd className="text-white font-medium">{formData.location || 'Not specified'}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-400">Type:</dt>
                      <dd className="text-white font-medium capitalize">{formData.elimination_type.replace('_', ' ')}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-400">Max Players:</dt>
                      <dd className="text-white font-medium">{formData.max_players}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-400">Entry Fee:</dt>
                      <dd className="text-white font-medium">
                        {formData.entry_fee_cents > 0 ? `$${(formData.entry_fee_cents / 100).toFixed(2)} (payment required)` : 'Free'}
                      </dd>
                    </div>
                  </dl>
                </div>

                <div className="bg-slate-700/50 rounded-lg p-4">
                  <h3 className="font-semibold text-slate-200 mb-3">Points Structure</h3>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    {Object.entries(formData.points_structure).map(([placement, points]) => (
                      <div key={placement} className="flex justify-between">
                        <span className="text-slate-400">Place {placement}:</span>
                        <span className="text-white font-medium">{points}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {formData.selectedPlayers.length > 0 && (
                  <div className="bg-slate-700/50 rounded-lg p-4">
                    <h3 className="font-semibold text-slate-200 mb-3">
                      Registered Players ({formData.selectedPlayers.length})
                    </h3>
                    <ul className="space-y-2">
                      {formData.selectedPlayers.map((playerId) => {
                        const player =
                          players.find((p) => p.player_id === playerId) ||
                          historyPlayers.find((p) => p.player_id === playerId)
                        return (
                          <li key={playerId} className="text-sm text-slate-300">
                            • {player?.first_name} {player?.last_name}
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">Notes (Optional)</label>
                  <textarea
                    value={formData.notes}
                    onChange={(e) => handleInputChange('notes', e.target.value)}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="Any additional notes about this tournament..."
                    rows={3}
                  />
                </div>
              </div>
            </div>
          )}

          <div className="flex gap-4 mt-8 pt-6 border-t border-slate-700">
            <button
              onClick={handlePrev}
              disabled={currentStep === 1}
              className="flex-1 px-6 py-3 bg-slate-700 text-white rounded-lg font-semibold hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              ← Previous
            </button>

            {currentStep < 4 ? (
              <button
                onClick={handleNext}
                className="flex-1 px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors"
              >
                Next →
              </button>
            ) : (
              <button
                onClick={() => createTournamentMutation.mutate()}
                disabled={createTournamentMutation.isPending}
                className="flex-1 px-6 py-3 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {createTournamentMutation.isPending ? 'Creating...' : '✓ Create Tournament'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
