import { ref, watch } from 'vue'

const STORAGE_KEY = 'imsp-kg-project'
export const HEADER_NAME = 'X-KG-Project'

// Reactive project state (singleton across app)
const currentProject = ref(localStorage.getItem(STORAGE_KEY) || 'default')

// Persist to localStorage on change
watch(currentProject, (val) => {
  localStorage.setItem(STORAGE_KEY, val)
})

export function useProject() {
  const setProject = (name: string) => {
    currentProject.value = name
  }

  return {
    currentProject,
    setProject,
    HEADER_NAME,
  }
}
