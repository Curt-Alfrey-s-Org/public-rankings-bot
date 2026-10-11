/**
 * Export Utilities
 * Functions for exporting data to CSV, JSON, and PDF formats
 */

/**
 * Converts an array of objects to CSV format and downloads it
 * @param data Array of objects to export
 * @param filename Name of the file to download (without extension)
 * @throws Error if data is invalid or too large
 */
export function exportToCsv<T extends Record<string, unknown>>(
  data: T[],
  filename: string = 'export'
): void {
  try {
    if (!Array.isArray(data) || data.length === 0) {
      throw new Error('No data to export')
    }

    // Check for reasonable size (limit to 100MB)
    const estimatedSize = JSON.stringify(data).length
    if (estimatedSize > 100 * 1024 * 1024) {
      throw new Error('Dataset too large to export (>100MB). Please filter data or export in batches.')
    }

    // Get headers from first object
    const headers = Object.keys(data[0])

    // Create CSV content
    const csvContent = [
      // Header row
      headers.map((h) => `"${String(h).replace(/"/g, '""')}"`).join(','),
      // Data rows
      ...data.map((row) =>
        headers
          .map((header) => {
            const value = row[header]
            if (value === null || value === undefined) {
              return ''
            }
            const stringValue = String(value)
            // Quote fields with commas, newlines, or quotes
            if (stringValue.includes(',') || stringValue.includes('\n') || stringValue.includes('"')) {
              return `"${stringValue.replace(/"/g, '""')}"`
            }
            return stringValue
          })
          .join(',')
      ),
    ].join('\n')

    // Create blob and download
    downloadFile(csvContent, `${filename}.csv`, 'text/csv;charset=utf-8;')
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to export CSV'
    throw new Error(`CSV Export Error: ${message}`)
  }
}

/**
 * Converts an array of objects to JSON format and downloads it
 * @param data Array of objects to export
 * @param filename Name of the file to download (without extension)
 * @throws Error if data is invalid or too large
 */
export function exportToJson<T extends Record<string, unknown>>(
  data: T[],
  filename: string = 'export'
): void {
  try {
    if (!Array.isArray(data)) {
      throw new Error('Data must be an array')
    }

    // Check for reasonable size (limit to 100MB)
    const jsonString = JSON.stringify(data, null, 2)
    if (jsonString.length > 100 * 1024 * 1024) {
      throw new Error('Dataset too large to export (>100MB). Please filter data or export in batches.')
    }

    downloadFile(jsonString, `${filename}.json`, 'application/json;charset=utf-8;')
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to export JSON'
    throw new Error(`JSON Export Error: ${message}`)
  }
}

/**
 * Helper function to trigger file download
 * @param content File content as string
 * @param filename Name of the file to download
 * @param mimeType MIME type of the file
 */
function downloadFile(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.style.visibility = 'hidden'

  document.body.appendChild(link)
  link.click()

  // Cleanup
  setTimeout(() => {
    try {
      document.body.removeChild(link)
    } catch (e) {
      // Silently fail if element is already removed (can happen in test environments)
    }
    URL.revokeObjectURL(url)
  }, 100)
}

/**
 * Formats a date for use in export filenames
 * @param date Date to format
 * @returns Formatted date string (YYYY-MM-DD_HHmmss)
 */
export function getExportFilename(baseFilename: string, date?: Date): string {
  const d = date || new Date()
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  const seconds = String(d.getSeconds()).padStart(2, '0')

  return `${baseFilename}_${year}-${month}-${day}_${hours}${minutes}${seconds}`
}
