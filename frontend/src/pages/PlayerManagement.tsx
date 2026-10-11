import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { tournamentsApi, type Player } from '@/api/tournaments'
import { toast } from '@/lib/toast'

interface EditingPlayer extends Partial<Player> {
  player_id?: string
}

export default function PlayerManagement() {
  const queryClient = useQueryClient()
  const [searchTerm, setSearchTerm] = useState('')
  const [filterMembership, setFilterMembership] = useState<string>('all')
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingPlayer, setEditingPlayer] = useState<EditingPlayer | null>(null)
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    nickname: '',
    email: '',
    phone: '',
    license_number: '',
    license_expiry_date: '',
    fargo_score: '',
    hometown: '',
    state: '',
    nationality: '',
    membership_status: 'active',
    hall_of_fame: false,
  })

  const { data: players = [], isLoading } = useQuery<Player[]>({
    queryKey: ['players'],
    queryFn: () => tournamentsApi.getPlayers(),
  })

  const createMutation = useMutation({
    mutationFn: tournamentsApi.createPlayer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['players'] })
      toast.success('Player created successfully!')
      resetForm()
    },
    onError: (error) => {
      toast.error(`Failed to create player: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ playerId, data }: { playerId: string; data: Partial<Player> }) =>
      tournamentsApi.updatePlayer(playerId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['players'] })
      toast.success('Player updated successfully!')
      resetForm()
    },
    onError: (error) => {
      toast.error(`Failed to update player: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: tournamentsApi.deletePlayer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['players'] })
      toast.success('Player deleted successfully!')
    },
    onError: (error) => {
      toast.error(`Failed to delete player: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const syncFargoMutation = useMutation({
    mutationFn: tournamentsApi.syncPlayerFargo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['players'] })
      toast.success('Fargo rating synced!')
    },
    onError: (error) => {
      toast.error(`Fargo sync failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const resetForm = () => {
    setFormData({
      first_name: '',
      last_name: '',
      nickname: '',
      email: '',
      phone: '',
      license_number: '',
      license_expiry_date: '',
      fargo_score: '',
      hometown: '',
      state: '',
      nationality: '',
      membership_status: 'active',
      hall_of_fame: false,
    })
    setShowAddForm(false)
    setEditingPlayer(null)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.first_name.trim() || !formData.last_name.trim()) {
      toast.error('First name and last name are required')
      return
    }

    const playerData = {
      first_name: formData.first_name,
      last_name: formData.last_name,
      nickname: formData.nickname || undefined,
      email: formData.email || undefined,
      phone: formData.phone || undefined,
      license_number: formData.license_number || undefined,
      license_expiry_date: formData.license_expiry_date || undefined,
      fargo_score: formData.fargo_score ? parseInt(formData.fargo_score) : undefined,
      hometown: formData.hometown || undefined,
      state: formData.state || undefined,
      nationality: formData.nationality || undefined,
      membership_status: (formData.membership_status as any) || 'active',
      hall_of_fame: formData.hall_of_fame,
    }

    if (editingPlayer?.player_id) {
      updateMutation.mutate({
        playerId: editingPlayer.player_id,
        data: playerData,
      })
    } else {
      createMutation.mutate(playerData)
    }
  }

  const handleEdit = (player: Player) => {
    setEditingPlayer(player)
    setFormData({
      first_name: player.first_name,
      last_name: player.last_name,
      nickname: player.nickname || '',
      email: player.email || '',
      phone: player.phone || '',
      license_number: player.license_number || '',
      license_expiry_date: player.license_expiry_date || '',
      fargo_score: player.fargo_score ? String(player.fargo_score) : '',
      hometown: player.hometown || '',
      state: player.state || '',
      nationality: player.nationality || '',
      membership_status: player.membership_status,
      hall_of_fame: player.hall_of_fame,
    })
    setShowAddForm(true)
  }

  const handleDelete = (playerId: string) => {
    if (confirm('Are you sure you want to delete this player?')) {
      deleteMutation.mutate(playerId)
    }
  }

  const filteredPlayers = players.filter((player) => {
    const matchesSearch =
      player.first_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      player.last_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      player.nickname?.toLowerCase().includes(searchTerm.toLowerCase())

    const matchesFilter = filterMembership === 'all' || player.membership_status === filterMembership

    return matchesSearch && matchesFilter
  })

  return (
    <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <div className="sticky top-0 z-20 bg-slate-900/95 backdrop-blur border-b border-slate-700 p-4 md:p-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-3xl md:text-4xl font-bold text-white">👥 Player Management</h1>
              <p className="text-slate-400 mt-1">{filteredPlayers.length} player(s)</p>
            </div>
            <button
              onClick={() => {
                resetForm()
                setShowAddForm(!showAddForm)
              }}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors w-full md:w-auto"
            >
              {showAddForm ? '✕ Cancel' : '+ Add Player'}
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto p-4 md:p-6">
        {/* Add/Edit Form */}
        {showAddForm && (
          <div className="bg-slate-800/50 backdrop-blur rounded-lg border border-slate-700 p-6 mb-6">
            <h2 className="text-2xl font-bold text-white mb-6">
              {editingPlayer ? 'Edit Player' : 'Add New Player'}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">
                    First Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.first_name}
                    onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="e.g., Jennifer"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">
                    Last Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.last_name}
                    onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="e.g., Barretta"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">Nickname</label>
                  <input
                    type="text"
                    value={formData.nickname}
                    onChange={(e) => setFormData({ ...formData, nickname: e.target.value })}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="e.g., Jenna"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">License Number</label>
                  <input
                    type="text"
                    value={formData.license_number}
                    onChange={(e) => setFormData({ ...formData, license_number: e.target.value })}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="WPBA/WPA License"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">License Expiry</label>
                  <input
                    type="date"
                    value={formData.license_expiry_date}
                    onChange={(e) => setFormData({ ...formData, license_expiry_date: e.target.value })}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="YYYY-MM-DD"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">Email</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="player@example.com"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">Phone</label>
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="555-1234"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">Fargo Rating</label>
                  <input
                    type="number"
                    value={formData.fargo_score}
                    onChange={(e) => setFormData({ ...formData, fargo_score: e.target.value })}
                    min="0"
                    max="1000"
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="650"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">Nationality</label>
                  <input
                    type="text"
                    value={formData.nationality}
                    onChange={(e) => setFormData({ ...formData, nationality: e.target.value })}
                    maxLength={3}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="USA"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">Hometown</label>
                  <input
                    type="text"
                    value={formData.hometown}
                    onChange={(e) => setFormData({ ...formData, hometown: e.target.value })}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="New York"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">State</label>
                  <input
                    type="text"
                    value={formData.state}
                    onChange={(e) => setFormData({ ...formData, state: e.target.value.toUpperCase() })}
                    maxLength={2}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="NY"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-200 mb-2">Membership Status</label>
                  <select
                    value={formData.membership_status}
                    onChange={(e) => setFormData({ ...formData, membership_status: e.target.value })}
                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                    <option value="suspended">Suspended</option>
                    <option value="lifetime">Lifetime</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-3 px-4 py-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.hall_of_fame}
                      onChange={(e) => setFormData({ ...formData, hall_of_fame: e.target.checked })}
                      className="w-4 h-4 text-blue-600 bg-slate-700 border-slate-600 rounded focus:ring-2 focus:ring-blue-500"
                    />
                    <span className="text-sm font-medium text-slate-200">Hall of Fame 🏆</span>
                  </label>
                </div>
              </div>

              <div className="flex gap-4 pt-4">
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="flex-1 px-6 py-3 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {createMutation.isPending || updateMutation.isPending ? 'Saving...' : '✓ Save Player'}
                </button>
                <button
                  type="button"
                  onClick={resetForm}
                  className="flex-1 px-6 py-3 bg-slate-700 text-white rounded-lg font-semibold hover:bg-slate-600 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Search & Filter */}
        <div className="flex flex-col md:flex-row gap-4 mb-6">
          <input
            type="text"
            placeholder="Search by name, nickname..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
          />
          <select
            value={filterMembership}
            onChange={(e) => setFilterMembership(e.target.value)}
            className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
          >
            <option value="all">All Members</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="suspended">Suspended</option>
            <option value="lifetime">Lifetime</option>
          </select>
        </div>

        {/* Players Table */}
        {isLoading ? (
          <div className="text-center py-12">
            <p className="text-slate-400">Loading players...</p>
          </div>
        ) : filteredPlayers.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-400">No players found. {!showAddForm && <span>Create one to get started!</span>}</p>
          </div>
        ) : (
          <div className="overflow-x-auto bg-slate-800/50 backdrop-blur rounded-lg border border-slate-700">
            <table className="w-full">
              <thead className="border-b border-slate-700 bg-slate-800">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-slate-200">Name</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-slate-200">License</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-slate-200 hidden md:table-cell">
                    Fargo
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-slate-200 hidden lg:table-cell">
                    Hometown
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-slate-200">Status</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-slate-200">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {filteredPlayers.map((player) => (
                  <tr key={player.player_id} className="hover:bg-slate-700/30 transition-colors">
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium text-white">
                          {player.first_name} {player.last_name}
                          {player.hall_of_fame && <span className="ml-2 text-lg">🏆</span>}
                          {player.license_overdue && (
                            <span className="ml-2 px-2 py-0.5 text-xs font-semibold bg-amber-500/30 text-amber-200 rounded" title="License overdue">
                              License overdue
                            </span>
                          )}
                        </p>
                        {player.nickname && <p className="text-xs text-slate-400">({player.nickname})</p>}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-300">
                      {player.license_number || '—'}
                      {player.license_expiry_date && (
                        <span className="block text-xs text-slate-500">Exp: {player.license_expiry_date}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-300 hidden md:table-cell">
                      <div className="flex items-center gap-2">
                        {player.fargo_score ? (
                          <span className="px-2 py-1 bg-blue-500/20 text-blue-200 rounded text-xs font-semibold">
                            {player.fargo_score}
                          </span>
                        ) : (
                          '—'
                        )}
                        <button
                          type="button"
                          onClick={() => syncFargoMutation.mutate(player.player_id)}
                          disabled={syncFargoMutation.isPending}
                          className="px-2 py-0.5 text-xs rounded bg-slate-600 text-slate-200 hover:bg-slate-500 disabled:opacity-50"
                          title="Sync Fargo from FairMatch"
                        >
                          Sync
                        </button>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-300 hidden lg:table-cell">
                      {player.hometown ? `${player.hometown}, ${player.state}` : '—'}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span
                        className={`px-2 py-1 rounded text-xs font-semibold ${
                          player.membership_status === 'active'
                            ? 'bg-green-500/20 text-green-200'
                            : player.membership_status === 'inactive'
                              ? 'bg-yellow-500/20 text-yellow-200'
                              : player.membership_status === 'suspended'
                                ? 'bg-red-500/20 text-red-200'
                                : 'bg-purple-500/20 text-purple-200'
                        }`}
                      >
                        {player.membership_status.charAt(0).toUpperCase() + player.membership_status.slice(1)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => handleEdit(player)}
                          className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(player.player_id)}
                          disabled={deleteMutation.isPending}
                          className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
