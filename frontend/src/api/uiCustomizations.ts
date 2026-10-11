import apiClient from './client'

export interface ButtonOverride {
  label?: string
  visible?: boolean
}

export interface UiCustomizationPayload {
  version: number
  text: Record<string, string>
  buttons: Record<string, ButtonOverride>
  layouts: Record<string, string[]>
}

const DEFAULT_PAYLOAD: UiCustomizationPayload = {
  version: 1,
  text: {},
  buttons: {},
  layouts: {},
}

export const uiCustomizationsApi = {
  get(): Promise<UiCustomizationPayload> {
    return apiClient.get<UiCustomizationPayload>('/ui-customizations/global').then((r) => r.data)
  },

  update(payload: UiCustomizationPayload): Promise<UiCustomizationPayload> {
    return apiClient.put<UiCustomizationPayload>('/ui-customizations/global', payload).then((r) => r.data)
  },

  defaults(): UiCustomizationPayload {
    return { ...DEFAULT_PAYLOAD }
  },
}
