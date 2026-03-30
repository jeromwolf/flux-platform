<script setup lang="ts">
import { computed } from 'vue'
import { useProject } from '@/composables/useProject'

const { currentProject } = useProject()

const projects = ['default', 'DevKG', 'ProdKG']

const projectColorClass = computed(() => {
  const name = currentProject.value.toLowerCase()
  if (name.includes('dev')) return 'project-dev'
  if (name.includes('prod')) return 'project-prod'
  return 'project-default'
})
</script>

<template>
  <div class="project-selector">
    <select v-model="currentProject" class="project-select" :class="projectColorClass">
      <option v-for="p in projects" :key="p" :value="p">{{ p }}</option>
    </select>
    <span class="project-badge" :class="projectColorClass">KG</span>
  </div>
</template>

<style scoped>
.project-selector {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.project-select {
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  font-size: 13px;
  background: white;
  cursor: pointer;
}
.project-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  color: white;
}
.project-dev { border-color: #22c55e; }
.project-select.project-dev { border-color: #22c55e; }
.project-badge.project-dev { background: #22c55e; }
.project-prod { border-color: #ef4444; }
.project-select.project-prod { border-color: #ef4444; }
.project-badge.project-prod { background: #ef4444; }
.project-default { border-color: #6b7280; }
.project-select.project-default { border-color: #6b7280; }
.project-badge.project-default { background: #6b7280; }
</style>
