import React, { useState } from 'react';
import { StepProps } from '../TournamentWizard';

const ScheduleStep: React.FC<StepProps> = ({
  data,
  onNext,
  onBack,
  isFirstStep,
  isLastStep
}) => {
  const [formData, setFormData] = useState({
    start_time: data.start_time || '09:00',
    estimated_duration_hours: data.estimated_duration_hours || 8,
    tables_available: data.tables_available || 4,
    match_time_limit_minutes: data.match_time_limit_minutes || 60,
    shot_clock_seconds: data.shot_clock_seconds || 60,
    use_shot_clock: data.use_shot_clock !== undefined ? data.use_shot_clock : true,
  });

  const handleNext = () => {
    onNext(formData, true);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Schedule</h2>
        <p className="text-gray-400">Set up timing and table assignments</p>
      </div>

      <div className="space-y-4">
        {/* Start Time */}
        <div>
          <label htmlFor="start_time" className="block text-sm font-medium text-gray-300 mb-2">
            Start Time
          </label>
          <input
            type="time"
            id="start_time"
            value={formData.start_time}
            onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </div>

        {/* Estimated Duration */}
        <div>
          <label htmlFor="estimated_duration_hours" className="block text-sm font-medium text-gray-300 mb-2">
            Estimated Duration (hours)
          </label>
          <input
            type="number"
            id="estimated_duration_hours"
            min="1"
            max="24"
            value={formData.estimated_duration_hours}
            onChange={(e) => setFormData({ ...formData, estimated_duration_hours: parseInt(e.target.value) })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </div>

        {/* Tables Available */}
        <div>
          <label htmlFor="tables_available" className="block text-sm font-medium text-gray-300 mb-2">
            Tables Available
          </label>
          <input
            type="number"
            id="tables_available"
            min="1"
            max="64"
            value={formData.tables_available}
            onChange={(e) => setFormData({ ...formData, tables_available: parseInt(e.target.value) })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </div>

        {/* Match Time Limit */}
        <div>
          <label htmlFor="match_time_limit_minutes" className="block text-sm font-medium text-gray-300 mb-2">
            Match Time Limit (minutes)
          </label>
          <input
            type="number"
            id="match_time_limit_minutes"
            min="0"
            max="480"
            value={formData.match_time_limit_minutes}
            onChange={(e) => setFormData({ ...formData, match_time_limit_minutes: parseInt(e.target.value) })}
            className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            placeholder="0 for no limit"
          />
          <p className="mt-1 text-xs text-gray-400">Enter 0 for no time limit</p>
        </div>

        {/* Use Shot Clock */}
        <div className="flex items-center space-x-3">
          <input
            type="checkbox"
            id="use_shot_clock"
            checked={formData.use_shot_clock}
            onChange={(e) => setFormData({ ...formData, use_shot_clock: e.target.checked })}
            className="w-5 h-5 bg-slate-800 border-slate-700 rounded focus:ring-2 focus:ring-sky-500"
          />
          <label htmlFor="use_shot_clock" className="text-sm font-medium text-gray-300">
            Use shot clock
          </label>
        </div>

        {/* Shot Clock Duration */}
        {formData.use_shot_clock && (
          <div>
            <label htmlFor="shot_clock_seconds" className="block text-sm font-medium text-gray-300 mb-2">
              Shot Clock Duration (seconds)
            </label>
            <input
              type="number"
              id="shot_clock_seconds"
              min="30"
              max="600"
              value={formData.shot_clock_seconds}
              onChange={(e) => setFormData({ ...formData, shot_clock_seconds: parseInt(e.target.value) })}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
        )}
      </div>

      {/* Navigation Buttons */}
      <div className="flex justify-between pt-6 border-t border-slate-700">
        <button
          onClick={onBack}
          className="px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
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

export default ScheduleStep;
