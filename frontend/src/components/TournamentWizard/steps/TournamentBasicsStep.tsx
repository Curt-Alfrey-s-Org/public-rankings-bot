import React, { useState, useEffect } from 'react';
import { StepProps } from '../TournamentWizard';

const RANKING_SYSTEMS = [
  { value: 'WPBA_Women', label: 'WPBA Women' },
  { value: 'WPBA', label: 'WPBA' },
  { value: 'WPA_Women', label: 'WPA Women' },
  { value: 'WPA_Men', label: 'WPA Men' },
  { value: 'WPA', label: 'WPA' },
  { value: 'WPA_Heyball', label: 'WPA Heyball' },
  { value: 'WPA_Heyball_Men', label: 'WPA Heyball Men' },
  { value: 'WPA_Heyball_Women', label: 'WPA Heyball Women' },
  { value: 'WPA_Artistic', label: 'WPA Artistic' },
];

const GAME_TYPES = [
  { value: '9-ball', label: '9-Ball' },
  { value: '8-ball', label: '8-Ball' },
  { value: '10-ball', label: '10-Ball' },
  { value: 'straight-pool', label: 'Straight Pool' },
  { value: 'one-pocket', label: 'One Pocket' },
  { value: 'bank-pool', label: 'Bank Pool' },
  { value: 'other', label: 'Other' },
];

const TournamentBasicsStep: React.FC<StepProps> = ({
  data,
  onNext,
  onBack,
  isFirstStep,
  isLastStep
}) => {
  const [formData, setFormData] = useState({
    tournament_name: data.tournament_name || '',
    tournament_date: data.tournament_date || '',
    location: data.location || '',
    elimination_type: data.elimination_type || '',
    max_players: data.max_players ?? 0,
    game_type: data.game_type || '',
    ranking_system: data.ranking_system || '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = () => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.tournament_name || formData.tournament_name.trim().length < 3) {
      newErrors.tournament_name = 'Tournament name must be at least 3 characters';
    }
    
    if (!formData.tournament_date) {
      newErrors.tournament_date = 'Tournament date is required';
    }
    
    if (!(formData.ranking_system || '').trim()) {
      newErrors.ranking_system = 'Please select who the tournament is for (Tournament for)';
    }
    
    if (!(formData.game_type || '').trim()) {
      newErrors.game_type = 'Please select a game type';
    }
    
    const maxP = formData.max_players;
    if (maxP < 2 || maxP > 256) {
      newErrors.max_players = 'Max players must be between 2 and 256';
    }
    
    if (!(formData.elimination_type || '').trim()) {
      newErrors.elimination_type = 'Please select elimination type';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validate()) {
      onNext(formData, true);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Tournament Basics</h2>
        <p className="text-gray-400">Enter the basic information about your tournament</p>
      </div>

      <div className="space-y-4">
        {/* Tournament Name */}
        <div>
          <label htmlFor="tournament_name" className="block text-sm font-medium text-gray-300 mb-2">
            Tournament Name *
          </label>
          <input
            type="text"
            id="tournament_name"
            value={formData.tournament_name}
            onChange={(e) => setFormData({ ...formData, tournament_name: e.target.value })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            placeholder="e.g., Spring Championship 2026"
          />
          {errors.tournament_name && (
            <p className="mt-1 text-sm text-red-400">{errors.tournament_name}</p>
          )}
        </div>

        {/* Tournament Date */}
        <div>
          <label htmlFor="tournament_date" className="block text-sm font-medium text-gray-300 mb-2">
            Tournament Date *
          </label>
          <input
            type="date"
            id="tournament_date"
            value={formData.tournament_date}
            onChange={(e) => setFormData({ ...formData, tournament_date: e.target.value })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
          {errors.tournament_date && (
            <p className="mt-1 text-sm text-red-400">{errors.tournament_date}</p>
          )}
        </div>

        {/* Tournament for (ranking system) */}
        <div>
          <label htmlFor="ranking_system" className="block text-sm font-medium text-gray-300 mb-2">
            Tournament for (ranking system) *
          </label>
          <select
            id="ranking_system"
            value={formData.ranking_system}
            onChange={(e) => setFormData({ ...formData, ranking_system: e.target.value })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            title="Who this tournament is for — Auto Fill uses this to pull top ranked players"
          >
            <option value="">— Select —</option>
            {RANKING_SYSTEMS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          {errors.ranking_system && (
            <p className="mt-1 text-sm text-red-400">{errors.ranking_system}</p>
          )}
        </div>

        {/* Game Type */}
        <div>
          <label htmlFor="game_type" className="block text-sm font-medium text-gray-300 mb-2">
            Game Type *
          </label>
          <select
            id="game_type"
            value={formData.game_type}
            onChange={(e) => setFormData({ ...formData, game_type: e.target.value })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="">— Select —</option>
            {GAME_TYPES.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          {errors.game_type && (
            <p className="mt-1 text-sm text-red-400">{errors.game_type}</p>
          )}
        </div>

        {/* Location */}
        <div>
          <label htmlFor="location" className="block text-sm font-medium text-gray-300 mb-2">
            Location
          </label>
          <input
            type="text"
            id="location"
            value={formData.location}
            onChange={(e) => setFormData({ ...formData, location: e.target.value })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            placeholder="e.g., Billiards Hall, New York"
          />
        </div>

        {/* Elimination Type */}
        <div>
          <label htmlFor="elimination_type" className="block text-sm font-medium text-gray-300 mb-2">
            Elimination Type *
          </label>
          <select
            id="elimination_type"
            value={formData.elimination_type}
            onChange={(e) => setFormData({ ...formData, elimination_type: e.target.value })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="">— Select —</option>
            <option value="single">Single Elimination</option>
            <option value="double">Double Elimination</option>
          </select>
          {errors.elimination_type && (
            <p className="mt-1 text-sm text-red-400">{errors.elimination_type}</p>
          )}
        </div>

        {/* Max Players */}
        <div>
          <label htmlFor="max_players" className="block text-sm font-medium text-gray-300 mb-2">
            Maximum Players *
          </label>
          <input
            type="number"
            id="max_players"
            min="2"
            max="256"
            value={formData.max_players || ''}
            onChange={(e) => setFormData({ ...formData, max_players: parseInt(e.target.value, 10) || 0 })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            placeholder="e.g. 32"
          />
          {errors.max_players && (
            <p className="mt-1 text-sm text-red-400">{errors.max_players}</p>
          )}
        </div>
      </div>

      {/* Navigation Buttons */}
      <div className="flex justify-between pt-6 border-t border-slate-700">
        <button
          onClick={onBack}
          disabled={isFirstStep}
          className="px-6 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-gray-600 text-white rounded-lg transition-colors"
        >
          Back
        </button>
        <button
          onClick={handleNext}
          className="px-6 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  );
};

export default TournamentBasicsStep;
