import { defineStore } from 'pinia'
import type { User } from '~/types/replay'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    isAuthenticated: false,
    isLoading: true,
    error: null as string | null,
  }),

  actions: {
    async fetchUser() {
      this.isLoading = true
      this.error = null

      try {
        const config = useRuntimeConfig()
        const baseUrl = config.public.apiBaseUrl

        const response = await $fetch<User>(`${baseUrl}/api/auth/me`, {
          credentials: 'include',
        })

        this.user = response
        this.isAuthenticated = true
      } catch (err: any) {
        console.log('[Auth] Not authenticated or error:', err?.message)
        this.user = null
        this.isAuthenticated = false
        // 401 は正常なケース（未ログイン）なのでエラーとして扱わない
        if (err?.status !== 401 && err?.statusCode !== 401) {
          this.error = err?.message || 'Authentication error'
        }
      } finally {
        this.isLoading = false
      }
    },

    loginWithDiscord() {
      const config = useRuntimeConfig()
      const baseUrl = config.public.apiBaseUrl
      window.location.href = `${baseUrl}/api/auth/discord`
    },

    async logout() {
      try {
        const config = useRuntimeConfig()
        const baseUrl = config.public.apiBaseUrl

        await $fetch(`${baseUrl}/api/auth/logout`, {
          method: 'POST',
          credentials: 'include',
        })
      } catch (err) {
        console.error('[Auth] Logout error:', err)
      } finally {
        this.user = null
        this.isAuthenticated = false
      }
    },
  },

  getters: {
    displayName: (state) => {
      if (!state.user) return ''
      return state.user.globalName || state.user.username
    },
  },
})
