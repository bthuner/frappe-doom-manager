<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-lg font-semibold">Runs</h1>
        <p class="text-sm text-ink-gray-5">Every submitted Doom Run, newest first.</p>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="ghost" icon-left="refresh-cw" :loading="runs.loading" @click="runs.reload()">Refresh</Button>
        <Button v-if="isLoggedIn" variant="outline" icon-left="external-link" link="/app/doom-run">Open in Desk</Button>
      </div>
    </div>

    <ListView
      v-if="rows.length"
      :columns="columns"
      :rows="rows"
      row-key="name"
      :options="{ selectable: false, showTooltip: false, resizeColumn: false }"
    />
    <EmptyCard v-else :loading="runs.loading" text="No runs yet." />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, ListView, createResource } from 'frappe-ui'
import EmptyCard from '@/components/EmptyCard.vue'
import { isLoggedIn } from '@/session'
import { formatTime, formatDate, ratio } from '@/utils'

const runs = createResource({ url: 'doom_manager.api.get_runs', params: { limit: 200 }, auto: true })

const columns = [
  { label: 'Player', key: 'player_name', width: 2 },
  { label: 'Level', key: 'level_name', width: 1 },
  { label: 'Kills', key: 'kills_label', width: 1, align: 'right' },
  { label: 'Items', key: 'items_label', width: 1, align: 'right' },
  { label: 'Secrets', key: 'secrets_label', width: 1, align: 'right' },
  { label: 'Time', key: 'time_label', width: 1, align: 'right' },
  { label: 'Outcome', key: 'outcome', width: 1 },
  { label: 'Date', key: 'date_label', width: 2 },
]

const rows = computed(() =>
  (runs.data || []).map((r) => ({
    name: r.name,
    player_name: r.player_name,
    level_name: r.level_name,
    kills_label: ratio(r.kills, r.total_kills),
    items_label: ratio(r.items, r.total_items),
    secrets_label: ratio(r.secrets, r.total_secrets),
    time_label: formatTime(r.time_seconds),
    outcome: r.outcome,
    date_label: formatDate(r.creation),
  })),
)
</script>
