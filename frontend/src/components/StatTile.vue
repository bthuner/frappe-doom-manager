<template>
  <div class="rounded-lg border border-outline-gray-2 bg-surface-white px-4 py-3">
    <div class="text-xs uppercase tracking-wide text-ink-gray-5">{{ label }}</div>
    <div class="mt-1 flex items-baseline gap-1">
      <span class="text-2xl font-semibold tabular-nums" :class="valueClass">{{ value ?? '—' }}</span>
      <span v-if="unit && value != null" class="text-sm text-ink-gray-5">{{ unit }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: null },
  unit: { type: String, default: '' },
  valueClass: { type: String, default: '' },
})
</script>
