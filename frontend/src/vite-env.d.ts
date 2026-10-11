/// <reference types="vite/client" />

import 'axios'

declare module 'axios' {
  interface AxiosRequestConfig {
    /** When true, response error interceptor skips toasts and heavy logging (caller handles failure). */
    skipGlobalErrorUI?: boolean
  }
}
