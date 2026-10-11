import { useState } from 'react'

interface BackgroundControlsProps {
  opacity: number
  onOpacityChange: (opacity: number) => void
  enabled: boolean
  onEnabledChange: (enabled: boolean) => void
  scale: number
  onScaleChange: (scale: number) => void
  objectFit: 'cover' | 'contain' | 'fill' | 'none' | 'scale-down'
  onObjectFitChange: (fit: 'cover' | 'contain' | 'fill' | 'none' | 'scale-down') => void
  /** Position offset from center (%). Move background around. */
  positionX?: number
  positionY?: number
  onPositionChange?: (x: number, y: number) => void
}

export default function BackgroundControls({
  opacity,
  onOpacityChange,
  enabled,
  onEnabledChange,
  scale,
  onScaleChange,
  objectFit,
  onObjectFitChange,
  positionX = 0,
  positionY = 0,
  onPositionChange,
}: BackgroundControlsProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-3 bg-card/90 hover:bg-card border border-border rounded-lg shadow-lg backdrop-blur-sm transition-colors"
        title="Background Controls"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
        </svg>
      </button>

      {/* Controls Panel */}
      {isOpen && (
        <div className="absolute bottom-16 right-0 bg-card border border-border rounded-lg p-4 shadow-xl backdrop-blur-sm min-w-[250px]">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold">Background Controls</h3>
            <button
              onClick={() => setIsOpen(false)}
              className="text-muted-foreground hover:text-foreground"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Enable/Disable Toggle */}
          <div className="mb-4">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => onEnabledChange(e.target.checked)}
                className="w-4 h-4"
              />
              <span>Show Video Background</span>
            </label>
          </div>

          {/* Opacity Slider */}
          {enabled && (
            <>
              <div className="mb-4">
                <label className="block text-sm mb-2">
                  Opacity: {Math.round(opacity * 100)}%
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={opacity}
                  onChange={(e) => onOpacityChange(parseFloat(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>0%</span>
                  <span>100%</span>
                </div>
              </div>

              {/* Position X / Y — move background around */}
              {onPositionChange && (
                <>
                  <div className="mb-4">
                    <label className="block text-sm mb-2">
                      Position X: {positionX}%
                    </label>
                    <input
                      type="range"
                      min="-50"
                      max="50"
                      step="1"
                      value={positionX}
                      onChange={(e) => onPositionChange(parseInt(e.target.value, 10), positionY)}
                      className="w-full"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground mt-1">
                      <span>← Left</span>
                      <span>Right →</span>
                    </div>
                  </div>
                  <div className="mb-4">
                    <label className="block text-sm mb-2">
                      Position Y: {positionY}%
                    </label>
                    <input
                      type="range"
                      min="-50"
                      max="50"
                      step="1"
                      value={positionY}
                      onChange={(e) => onPositionChange(positionX, parseInt(e.target.value, 10))}
                      className="w-full"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground mt-1">
                      <span>↑ Up</span>
                      <span>Down ↓</span>
                    </div>
                  </div>
                </>
              )}

              {/* Scale/Size Slider */}
              <div className="mb-4">
                <label className="block text-sm mb-2">
                  Size: {Math.round(scale * 100)}%
                </label>
                <input
                  type="range"
                  min="0.5"
                  max="2"
                  step="0.1"
                  value={scale}
                  onChange={(e) => onScaleChange(parseFloat(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>50%</span>
                  <span>200%</span>
                </div>
              </div>

              {/* Object Fit Selection */}
              <div>
                <label className="block text-sm mb-2">Fit Mode:</label>
                <select
                  value={objectFit}
                  onChange={(e) => onObjectFitChange(e.target.value as any)}
                  className="w-full px-3 py-2 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="cover">Cover (Fill Screen)</option>
                  <option value="contain">Contain (Show All)</option>
                  <option value="fill">Fill (Stretch)</option>
                  <option value="none">None (Original Size)</option>
                  <option value="scale-down">Scale Down</option>
                </select>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
