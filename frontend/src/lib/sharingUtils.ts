/**
 * Sharing Utilities for Export/Import Operations
 * Handles clipboard operations, file downloads, QR codes, and data compression
 */

import { testCenterLogger } from './testCenterLogger'

// Compression utilities
export class CompressionUtils {
  static async compressData(data: any): Promise<string> {
    try {
      const jsonString = JSON.stringify(data)
      const compressed = await this.compressString(jsonString)
      return btoa(compressed)
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'compress_data'
      })
      throw new Error('Failed to compress data')
    }
  }

  static async decompressData(compressedData: string): Promise<any> {
    try {
      const decompressed = atob(compressedData)
      const jsonString = await this.decompressString(decompressed)
      return JSON.parse(jsonString)
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'decompress_data'
      })
      throw new Error('Failed to decompress data')
    }
  }

  private static async compressString(input: string): Promise<string> {
    // Simple compression using built-in compression if available
    if ('CompressionStream' in window) {
      const stream = new CompressionStream('gzip')
      const writer = stream.writable.getWriter()
      const reader = stream.readable.getReader()

      writer.write(new TextEncoder().encode(input))
      writer.close()

      const chunks: Uint8Array[] = []
      let done = false
      while (!done) {
        const { value, done: readerDone } = await reader.read()
        if (value) chunks.push(value)
        done = readerDone
      }

      const compressed = new Uint8Array(chunks.reduce((acc, chunk) => acc + chunk.length, 0))
      let offset = 0
      for (const chunk of chunks) {
        compressed.set(chunk, offset)
        offset += chunk.length
      }

      return Array.from(compressed).map(b => String.fromCharCode(b)).join('')
    } else {
      // Fallback: return uncompressed data
      return input
    }
  }

  private static async decompressString(compressed: string): Promise<string> {
    // Simple decompression using built-in decompression if available
    if ('DecompressionStream' in window) {
      const stream = new DecompressionStream('gzip')
      const writer = stream.writable.getWriter()
      const reader = stream.readable.getReader()

      const compressedBytes = new Uint8Array(compressed.split('').map(c => c.charCodeAt(0)))
      writer.write(compressedBytes)
      writer.close()

      const chunks: Uint8Array[] = []
      let done = false
      while (!done) {
        const { value, done: readerDone } = await reader.read()
        if (value) chunks.push(value)
        done = readerDone
      }

      const decompressed = new Uint8Array(chunks.reduce((acc, chunk) => acc + chunk.length, 0))
      let offset = 0
      for (const chunk of chunks) {
        decompressed.set(chunk, offset)
        offset += chunk.length
      }

      return new TextDecoder().decode(decompressed)
    } else {
      // Fallback: return as-is (assuming it wasn't compressed)
      return compressed
    }
  }
}

// Clipboard utilities
export class ClipboardUtils {
  static async copyToClipboard(text: string): Promise<boolean> {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text)
        testCenterLogger.userInteraction('clipboard_copy_success', {
          dataLength: text.length
        })
        return true
      } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea')
        textArea.value = text
        textArea.style.position = 'fixed'
        textArea.style.left = '-999999px'
        textArea.style.top = '-999999px'
        document.body.appendChild(textArea)
        textArea.focus()
        textArea.select()

        const success = document.execCommand('copy')
        document.body.removeChild(textArea)

        if (success) {
          testCenterLogger.userInteraction('clipboard_copy_fallback_success', {
            dataLength: text.length
          })
        } else {
          testCenterLogger.criticalError(new Error('Fallback clipboard copy failed'), {
            operation: 'clipboard_copy_fallback'
          })
        }

        return success
      }
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'clipboard_copy'
      })
      return false
    }
  }

  static async readFromClipboard(): Promise<string | null> {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        const text = await navigator.clipboard.readText()
        testCenterLogger.userInteraction('clipboard_read_success', {
          dataLength: text.length
        })
        return text
      } else {
        testCenterLogger.criticalError(new Error('Clipboard API not available'), {
          operation: 'clipboard_read'
        })
        return null
      }
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'clipboard_read'
      })
      return null
    }
  }
}

// File download utilities
export class FileDownloadUtils {
  static downloadJSON(data: any, filename: string): void {
    try {
      const jsonString = JSON.stringify(data, null, 2)
      const blob = new Blob([jsonString], { type: 'application/json' })
      const url = URL.createObjectURL(blob)

      const a = document.createElement('a')
      a.href = url
      a.download = filename.endsWith('.json') ? filename : `${filename}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      testCenterLogger.userInteraction('file_download_success', {
        filename,
        dataSize: jsonString.length
      })
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'file_download',
        filename
      })
      throw new Error('Failed to download file')
    }
  }

  static downloadText(text: string, filename: string, mimeType: string = 'text/plain'): void {
    try {
      const blob = new Blob([text], { type: mimeType })
      const url = URL.createObjectURL(blob)

      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      testCenterLogger.userInteraction('text_download_success', {
        filename,
        dataSize: text.length
      })
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'text_download',
        filename
      })
      throw new Error('Failed to download text file')
    }
  }
}

// QR Code utilities
export class QRCodeUtils {
  private static qrCodeLibrary: any = null

  static async loadQRCodeLibrary(): Promise<void> {
    if (this.qrCodeLibrary) return

    try {
      // Dynamic import of QR code library
      // In a real implementation, you would install qrcode package
      // For now, we'll use a placeholder
      this.qrCodeLibrary = {
        generate: (text: string) => `QR:${text}` // Placeholder
      }
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'load_qr_library'
      })
      throw new Error('Failed to load QR code library')
    }
  }

  static async generateQRCode(text: string, options: {
    size?: number
    format?: 'png' | 'svg' | 'url'
  } = {}): Promise<string> {
    try {
      await this.loadQRCodeLibrary()

      const { size = 256, format = 'url' } = options

      // In a real implementation, this would generate an actual QR code
      // For now, we'll create a data URL placeholder
      const qrData = `data:image/svg+xml;base64,${btoa(`
        <svg width="${size}" height="${size}" xmlns="http://www.w3.org/2000/svg">
          <rect width="100%" height="100%" fill="white"/>
          <text x="50%" y="50%" text-anchor="middle" dy=".3em" font-family="monospace" font-size="12">
            QR Code Placeholder
          </text>
          <text x="50%" y="70%" text-anchor="middle" dy=".3em" font-family="monospace" font-size="8">
            ${text.substring(0, 20)}${text.length > 20 ? '...' : ''}
          </text>
        </svg>
      `)}`

      testCenterLogger.userInteraction('qr_code_generated', {
        textLength: text.length,
        format,
        size
      })

      return qrData
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'generate_qr_code'
      })
      throw new Error('Failed to generate QR code')
    }
  }

  static async generateQRCodeForData(data: any, options: {
    compress?: boolean
    size?: number
    format?: 'png' | 'svg' | 'url'
  } = {}): Promise<string> {
    try {
      const { compress = false } = options

      let textToEncode: string
      if (compress) {
        textToEncode = await CompressionUtils.compressData(data)
      } else {
        textToEncode = JSON.stringify(data)
      }

      // Check if the data is too large for QR code
      if (textToEncode.length > 2000) {
        // If too large, create a shortened version or use a different approach
        const summary = {
          type: data.type,
          name: data.metadata?.name || 'Unknown',
          size: textToEncode.length,
          compressed: compress,
          summary: 'Data too large for QR code. Use file import instead.'
        }
        textToEncode = JSON.stringify(summary)
      }

      return await this.generateQRCode(textToEncode, options)
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'generate_qr_for_data'
      })
      throw new Error('Failed to generate QR code for data')
    }
  }
}

// Sharing utilities
export class SharingUtils {
  static async shareTournamentExport(data: any, options: {
    method: 'clipboard' | 'download' | 'qrcode'
    filename?: string
    compress?: boolean
    qrSize?: number
  } = { method: 'download' }): Promise<{ success: boolean; result?: any; error?: string }> {
    try {
      const { method, filename = 'tournament_export', compress = false } = options

      let dataToShare: any
      if (compress) {
        dataToShare = await CompressionUtils.compressData(data)
      } else {
        dataToShare = data
      }

      switch (method) {
        case 'clipboard': {
          const jsonString = JSON.stringify(dataToShare, null, 2)
          const success = await ClipboardUtils.copyToClipboard(jsonString)
          return {
            success,
            result: success ? 'Data copied to clipboard' : undefined,
            error: success ? undefined : 'Failed to copy to clipboard'
          }
        }

        case 'download': {
          FileDownloadUtils.downloadJSON(dataToShare, filename)
          return {
            success: true,
            result: `File downloaded as ${filename}.json`
          }
        }

        case 'qrcode': {
          const qrCode = await QRCodeUtils.generateQRCodeForData(dataToShare, {
            compress,
            size: options.qrSize
          })
          return {
            success: true,
            result: qrCode
          }
        }

        default:
          return {
            success: false,
            error: `Unsupported sharing method: ${method}`
          }
      }
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'share_tournament_export',
        method: options.method
      })
      return {
        success: false,
        error: error.message
      }
    }
  }

  static async importFromClipboard(): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const clipboardText = await ClipboardUtils.readFromClipboard()
      if (!clipboardText) {
        return {
          success: false,
          error: 'No data found in clipboard'
        }
      }

      // Try to parse as compressed data first
      try {
        const decompressedData = await CompressionUtils.decompressData(clipboardText)
        return {
          success: true,
          data: decompressedData
        }
      } catch {
        // Not compressed, try parsing as regular JSON
        try {
          const data = JSON.parse(clipboardText)
          return {
            success: true,
            data
          }
        } catch {
          return {
            success: false,
            error: 'Clipboard data is not valid JSON'
          }
        }
      }
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'import_from_clipboard'
      })
      return {
        success: false,
        error: error.message
      }
    }
  }

  static createShareableLink(data: any, baseUrl: string = window.location.origin): string {
    try {
      // Create a compressed version for URL sharing
      const compressed = btoa(JSON.stringify(data))
      const shareableUrl = `${baseUrl}/import?data=${encodeURIComponent(compressed)}`

      testCenterLogger.userInteraction('shareable_link_created', {
        dataSize: compressed.length,
        urlLength: shareableUrl.length
      })

      return shareableUrl
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'create_shareable_link'
      })
      throw new Error('Failed to create shareable link')
    }
  }

  static async parseSharedData(sharedData: string): Promise<any> {
    try {
      // Try to decode from base64 first (for compressed data)
      try {
        const decoded = atob(sharedData)
        const data = JSON.parse(decoded)
        return data
      } catch {
        // Try parsing as regular JSON
        return JSON.parse(sharedData)
      }
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'parse_shared_data'
      })
      throw new Error('Failed to parse shared data')
    }
  }
}

// Export convenience functions
export const sharingUtils = {
  compress: CompressionUtils.compressData,
  decompress: CompressionUtils.decompressData,
  copyToClipboard: ClipboardUtils.copyToClipboard,
  readFromClipboard: ClipboardUtils.readFromClipboard,
  downloadJSON: FileDownloadUtils.downloadJSON,
  downloadText: FileDownloadUtils.downloadText,
  generateQRCode: QRCodeUtils.generateQRCode,
  generateQRCodeForData: QRCodeUtils.generateQRCodeForData,
  shareTournamentExport: SharingUtils.shareTournamentExport,
  importFromClipboard: SharingUtils.importFromClipboard,
  createShareableLink: SharingUtils.createShareableLink,
  parseSharedData: SharingUtils.parseSharedData
}

export default sharingUtils