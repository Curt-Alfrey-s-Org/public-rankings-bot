import React, { useState, useEffect } from 'react';
import { StepProps } from '../TournamentWizard';
import { tournamentsApi } from '@/api/tournaments';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from '@/lib/toast';

interface PlayerRegistrationStepProps extends StepProps {
  data: StepProps['data'] & { tournamentId?: string | null };
}

const PlayerRegistrationStep: React.FC<PlayerRegistrationStepProps> = ({
  data,
  onNext,
  onBack,
  isFirstStep,
  isLastStep,
}) => {
  const tournamentId = data.tournamentId ?? null;
  const queryClient = useQueryClient();
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const { data: players = [], isLoading } = useQuery({
    queryKey: ['tournament-players', tournamentId],
    queryFn: () => tournamentsApi.getTournamentPlayers(tournamentId!),
    enabled: !!tournamentId,
  });

  const autoFillMutation = useMutation({
    mutationFn: () => tournamentsApi.autoFillPlayers(tournamentId!),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['tournament-players', tournamentId] });
      toast.success(res.message || `Added ${res.added} player(s)`);
      setLoadingAction(null);
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Auto Fill failed');
      setLoadingAction(null);
    },
  });

  const clearMutation = useMutation({
    mutationFn: () => tournamentsApi.clearRegistration(tournamentId!),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['tournament-players', tournamentId] });
      toast.success(res.message || `Cleared ${res.removed} player(s)`);
      setLoadingAction(null);
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Clear registration failed');
      setLoadingAction(null);
    },
  });

  const handleAutoFill = () => {
    if (!tournamentId) return;
    setLoadingAction('autofill');
    autoFillMutation.mutate();
  };

  const handleClear = () => {
    if (!tournamentId) return;
    if (players.length === 0) {
      toast.info('No players registered');
      return;
    }
    if (!window.confirm(`Remove all ${players.length} registered player(s)?`)) return;
    setLoadingAction('clear');
    clearMutation.mutate();
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Player Registration</h2>
        <p className="text-gray-400">
          Add players from the tournament&apos;s ranking system or manage the list. Set &quot;Tournament for&quot; in Basics to use Auto Fill.
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleAutoFill}
          disabled={!tournamentId || loadingAction !== null}
          className="px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 disabled:text-gray-500 text-white rounded-lg transition-colors"
        >
          {loadingAction === 'autofill' ? 'Filling…' : 'Auto Fill from rankings'}
        </button>
        <button
          type="button"
          onClick={handleClear}
          disabled={!tournamentId || loadingAction !== null || players.length === 0}
          className="px-4 py-2 bg-slate-600 hover:bg-slate-500 disabled:bg-slate-700 disabled:text-gray-500 text-white rounded-lg transition-colors"
        >
          {loadingAction === 'clear' ? 'Clearing…' : 'Clear registration'}
        </button>
      </div>

      {isLoading ? (
        <div className="text-gray-400">Loading players…</div>
      ) : (
        <div className="bg-slate-800 rounded-lg overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-gray-400">
                <th className="p-3">#</th>
                <th className="p-3">Name</th>
                <th className="p-3">License</th>
                <th className="p-3">Points / Rank</th>
              </tr>
            </thead>
            <tbody>
              {players.length === 0 ? (
                <tr>
                  <td colSpan={4} className="p-4 text-gray-500">
                    No players registered. Use Auto Fill to add top players from the ranking system, or add players later from the tournament page.
                  </td>
                </tr>
              ) : (
                players.map((p: any, i: number) => (
                  <tr key={p.player_id || i} className="border-b border-slate-700/50">
                    <td className="p-3 text-gray-400">{p.seed_position ?? i + 1}</td>
                    <td className="p-3 text-white">
                      {((p.first_name || '') + ' ' + (p.last_name || '')).trim() || p.player_id || '—'}
                    </td>
                    <td className="p-3 text-gray-400">{p.license_number || '—'}</td>
                    <td className="p-3 text-gray-400">
                      {p.total_points != null ? `${p.total_points} pts` : ''}
                      {p.current_rank != null ? ` #${p.current_rank}` : ''}
                      {!p.total_points && !p.current_rank ? '—' : ''}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex justify-between pt-6 border-t border-slate-700">
        <button
          onClick={onBack}
          disabled={isFirstStep}
          className="px-6 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-gray-600 text-white rounded-lg transition-colors"
        >
          Back
        </button>
        <button
          onClick={() => onNext({}, true)}
          className="px-6 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  );
};

export default PlayerRegistrationStep;
