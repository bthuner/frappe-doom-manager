<template>
  <div class="flex items-center justify-center rounded-lg border border-dashed border-outline-gray-3 px-4 py-8 text-sm text-ink-gray-5">
    <LoadingIndicator v-if="loading" class="h-4 w-4" />
    <span v-else>{{ text }}</span>
  </div>
</template>

<script setup>
import { LoadingIndicator } from 'frappe-ui'
defineProps({ loading: Boolean, text: { type: String, default: 'Nothing here yet.' } })
</script>
