import { useState, useEffect } from 'react'
import { logger } from '@/lib/logger'

interface DashboardWidget {
  id: string
  component: React.ReactNode
  title: string
  defaultOrder: number
}

interface DraggableWidgetProps {
  id: string
  children: React.ReactNode
  title: string
  index: number
  isDragging: boolean
  onDragStart: (id: string) => void
  onDragOver: (e: React.DragEvent, id: string) => void
  onDrop: (e: React.DragEvent, id: string) => void
  onDragEnd: () => void
}

function DraggableWidget({
  id,
  children,
  title: _title,
  index: _index,
  isDragging,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
}: DraggableWidgetProps) {
  const [isHovered, setIsHovered] = useState(false)

  return (
    <div
      className={`relative group transition-all h-full ${
        isDragging ? 'opacity-50 scale-95' : 'opacity-pool_opt_in'
      }`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Drag Handle - Visual indicator on hover */}
      {isHovered && (
        <div
          className="absolute -top-3 -right-3 z-10 pointer-events-none bg-card border border-border rounded-lg p-2 shadow-lg hover:shadow-xl transition-shadow"
          title="Drag to rearrange"
        >
          <svg
            className="w-5 h-5 text-muted-foreground"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 8h16M4 16h16"
            />
          </svg>
        </div>
      )}
      
      {/* Draggable Widget Container */}
      <div
        draggable
        onDragStart={(e) => {
          e.dataTransfer.effectAllowed = 'move'
          e.dataTransfer.setData('text/plain', id)
          onDragStart(id)
        }}
        onDragOver={(e) => {
          e.preventDefault()
          e.dataTransfer.dropEffect = 'move'
          onDragOver(e, id)
        }}
        onDrop={(e) => {
          e.preventDefault()
          onDrop(e, id)
        }}
        onDragEnd={onDragEnd}
        className="w-full h-full bg-card border border-border rounded-lg hover:border-primary/40 transition-all hover:shadow-lg p-4 sm:p-6"
        style={{ cursor: isHovered ? 'grab' : 'default' }}
      >
        {children}
      </div>
    </div>
  )
}

interface DraggableDashboardProps {
  widgets: DashboardWidget[]
}

export default function DraggableDashboard({ widgets }: DraggableDashboardProps) {
  const [widgetIds, setWidgetIds] = useState<string[]>([])
  const [draggedId, setDraggedId] = useState<string | null>(null)
  const [_dragOverId, setDragOverId] = useState<string | null>(null)

  // Load saved layout from localStorage
  useEffect(() => {
    const savedLayout = localStorage.getItem('dashboard-layout')
    if (savedLayout) {
      try {
        const parsed = JSON.parse(savedLayout)
        // Validate that all widget IDs exist
        const validIds = parsed.filter((id: string) =>
          widgets.some((w) => w.id === id)
        )
        // Add any missing widgets
        widgets.forEach((w) => {
          if (!validIds.includes(w.id)) {
            validIds.push(w.id)
          }
        })
        setWidgetIds(validIds)
      } catch (error) {
        logger.warn('Failed to parse dashboard layout; using default order', undefined, error as Error)
        // If parsing fails, use default order
        const sorted = [...widgets].sort((a, b) => a.defaultOrder - b.defaultOrder)
        setWidgetIds(sorted.map((w) => w.id))
      }
    } else {
      // Default order based on defaultOrder property
      const sorted = [...widgets].sort((a, b) => a.defaultOrder - b.defaultOrder)
      setWidgetIds(sorted.map((w) => w.id))
    }
  }, [widgets])

  function handleDragStart(id: string) {
    setDraggedId(id)
  }

  function handleDragOver(e: React.DragEvent, id: string) {
    e.preventDefault()
    if (draggedId && draggedId !== id) {
      setDragOverId(id)
    }
  }

  function handleDrop(e: React.DragEvent, targetId: string) {
    e.preventDefault()
    
    if (!draggedId || draggedId === targetId) {
      setDraggedId(null)
      setDragOverId(null)
      return
    }

    setWidgetIds((items) => {
      const draggedIndex = items.indexOf(draggedId)
      const targetIndex = items.indexOf(targetId)
      
      if (draggedIndex === -1 || targetIndex === -1) {
        return items
      }

      const newItems = [...items]
      const [removed] = newItems.splice(draggedIndex, 1)
      newItems.splice(targetIndex, 0, removed)
      
      // Save to localStorage
      try {
        localStorage.setItem('dashboard-layout', JSON.stringify(newItems))
      } catch (error) {
        logger.warn('Failed to save dashboard layout', { newItems }, error as Error)
      }
      
      return newItems
    })

    setDraggedId(null)
    setDragOverId(null)
  }

  function handleDragEnd() {
    setDraggedId(null)
    setDragOverId(null)
  }

  // Create widget map for easy lookup
  const widgetMap = new Map(widgets.map((w) => [w.id, w]))

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 auto-rows-max w-full min-w-0">
      {widgetIds.length === 0 ? (
        <div className="col-span-full text-center py-12 text-muted-foreground">
          <p>Loading dashboard...</p>
        </div>
      ) : (
        widgetIds.map((id, index) => {
          const widget = widgetMap.get(id)
          if (!widget) return null
          
          // Full width for mode-selector, stats-overview, and activity
          const isFullWidth = ['mode-selector', 'stats-overview', 'recent-activity'].includes(id)

          return (
            <div key={id} className={isFullWidth ? 'lg:col-span-2' : ''}>
              <DraggableWidget
                id={id}
                title={widget.title}
                index={index}
                isDragging={draggedId === id}
                onDragStart={handleDragStart}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                onDragEnd={handleDragEnd}
              >
                {widget.component}
              </DraggableWidget>
            </div>
          )
        })
      )}
    </div>
  )
}
