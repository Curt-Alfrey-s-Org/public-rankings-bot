/**
 * WPA Rules API: list and link to official rule PDFs.
 */

import { apiClient } from '@/api/client'

export interface WpaRuleItem {
  filename: string
  title: string
}

export const rulesApi = {
  list: (): Promise<WpaRuleItem[]> =>
    apiClient.get<WpaRuleItem[]>('/rules').then((r) => r.data),

  /** URL path to open a rule PDF (same-origin). */
  fileUrl: (filename: string): string =>
    `/api/rules/files/${encodeURIComponent(filename)}`,
}
