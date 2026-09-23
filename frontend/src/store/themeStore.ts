// netguard/frontend/src/store/themeStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface ThemeState {
  darkMode: boolean
  toggleDarkMode: () => void
  setDarkMode: (dark: boolean) => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      darkMode: true,
      toggleDarkMode: () =>
        set((state) => {
          const next = !state.darkMode
          document.documentElement.classList.toggle('dark', next)
          return { darkMode: next }
        }),
      setDarkMode: (dark) => {
        document.documentElement.classList.toggle('dark', dark)
        set({ darkMode: dark })
      },
    }),
    { name: 'netguard-theme' },
  ),
)
