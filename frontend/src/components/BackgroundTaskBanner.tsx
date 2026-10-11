import { useBackgroundTask } from '@/hooks/useBackgroundTask'
import { useAuth } from '@/contexts/AuthContext'

/**
 * Sticky banner that displays background task status
 * Shows "currently [task_name] running in background" at the top of the page
 * Only visible to super_admin users
 */
export default function BackgroundTaskBanner() {
  const { task, isRunning } = useBackgroundTask()
  const { user } = useAuth()

  if (!isRunning || !task || user?.role !== 'super_admin') return null

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-blue-600 text-white px-4 py-3 shadow-lg">
      <div className="max-w-7xl mx-auto flex items-center gap-3">
        <div className="flex-shrink-0">
          <div className="flex space-x-1">
            <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
            <div className="w-2 h-2 bg-white rounded-full animate-pulse animation-delay-200"></div>
            <div className="w-2 h-2 bg-white rounded-full animate-pulse animation-delay-400"></div>
          </div>
        </div>
        <div className="flex-1">
          <p className="font-medium">
            Currently <span className="font-bold">{task.task_name}</span> running in background
          </p>
          {task.message && (
            <p className="text-sm text-blue-pool_opt_in">{task.message}</p>
          )}
        </div>
        <div className="flex-shrink-0 text-blue-200 text-sm">
          {task.started_at && (
            <span>
              {Math.floor(
                (new Date().getTime() - new Date(task.started_at).getTime()) / 1000
              )}s running
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
