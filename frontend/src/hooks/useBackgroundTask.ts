import { useState, useEffect } from 'react'

/**
 * Hook to monitor background task status
 * Polls the API for current running task status
 */
export function useBackgroundTask() {
  const [task, setTask] = useState<any | null>(null)
  const [isRunning, setIsRunning] = useState(false)

  // Poll for task status every 2 seconds when running
  useEffect(() => {
    if (!isRunning && !task?.is_running) return

    const interval = setInterval(async () => {
      try {
        const response = await fetch('/api/fargo/status')
        if (response.ok) {
          const data = await response.json()
          setTask(data)
          setIsRunning(data.is_running || false)
        }
      } catch (error) {
        console.error('Failed to get task status:', error)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [isRunning, task?.is_running])

  return {
    task: task?.task,
    isRunning: task?.is_running || false,
  }
}
