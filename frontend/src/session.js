import { computed, reactive } from 'vue'
import { createResource } from 'frappe-ui'

// Boot data is serialised into window.* by www/doom.py + the jinjaBootData
// vite plugin. Under `vite dev` nothing is injected, so we fall back to Guest.
export const session = reactive({
  user: window.session_user || 'Guest',
  fullName: window.full_name || 'Guest',
})

export const isLoggedIn = computed(() => session.user !== 'Guest')

export const logout = createResource({
  url: 'logout',
  onSuccess() {
    window.location.href = '/doom'
  },
})

export const loginUrl = '/login?redirect-to=/doom'
