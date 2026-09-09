<template>
  <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
    <!-- Game -->
    <section class="space-y-4">
      <div class="overflow-hidden rounded-xl border border-outline-gray-2 bg-black shadow-sm">
        <canvas
          ref="canvasRef"
          class="doom-canvas block aspect-[8/5] w-full outline-none"
          width="640"
          height="400"
          tabindex="0"
          @mousedown.prevent="onMouseDown"
          @contextmenu.prevent
        />
        <div class="flex flex-wrap items-center gap-3 border-t border-gray-800 bg-gray-900 px-4 py-2 text-sm text-gray-300">
          <span class="inline-flex items-center gap-2">
            <span class="h-2 w-2 rounded-full" :class="statusDot" />
            {{ engine.state.message || 'Idle' }}
          </span>
          <div class="ml-auto flex items-center gap-2">
            <Button variant="outline" size="sm" theme="gray" @click="engine.tap(engine.KEY.ESCAPE)">Menu (Esc)</Button>
            <Button variant="solid" size="sm" theme="red" @click="engine.tap(engine.KEY.ENTER)">Enter</Button>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <StatTile label="Level" :value="engine.state.level" />
        <StatTile label="Kills" :value="engine.state.kills" :unit="outOf(engine.state.totalKills)" value-class="text-red-600" />
        <StatTile label="Items" :value="engine.state.items" :unit="outOf(engine.state.totalItems)" />
        <StatTile label="Secrets" :value="engine.state.secrets" :unit="outOf(engine.state.totalSecrets)" />
        <StatTile label="Time" :value="engine.state.timeSeconds != null ? formatTime(engine.state.timeSeconds) : null" />
      </div>

      <div class="rounded-lg border border-outline-gray-2 bg-surface-white p-4 text-sm text-ink-gray-7">
        <div class="mb-2 font-medium text-ink-gray-9">Controls</div>
        <div class="grid gap-x-6 gap-y-1 sm:grid-cols-2">
          <span><kbd class="kbd">Esc</kbd> menu · <kbd class="kbd">Enter</kbd> confirm</span>
          <span><kbd class="kbd">↑↓←→</kbd> / <kbd class="kbd">WASD</kbd> move, A/D strafe</span>
          <span><kbd class="kbd">Ctrl</kbd> or click fires · <kbd class="kbd">Space</kbd> / <kbd class="kbd">E</kbd> / right click uses</span>
          <span><kbd class="kbd">Shift</kbd> run · <kbd class="kbd">Tab</kbd> map · cheats work (<code>iddqd</code>, <code>idclev12</code>)</span>
        </div>
        <p class="mt-3 text-ink-gray-5">
          A run opens when a level starts and is saved when it ends, whether you reach the exit or die.
          <template v-if="!isLoggedIn"><a :href="loginUrl" class="text-ink-blue-3 underline">Log in</a> to have them saved.</template>
        </p>
      </div>
    </section>

    <!-- Side panel -->
    <aside class="space-y-6">
      <div>
        <div class="mb-2 flex items-center justify-between">
          <h2 class="text-base font-semibold">Leaderboard</h2>
          <Button variant="ghost" size="sm" icon="refresh-cw" :loading="leaderboard.loading" @click="leaderboard.reload()" />
        </div>
        <div v-if="leaderboard.data?.length" class="divide-y divide-outline-gray-2 rounded-lg border border-outline-gray-2 bg-surface-white">
          <div v-for="entry in leaderboard.data" :key="entry.level" class="px-4 py-3">
            <div class="flex items-center justify-between">
              <span class="font-doom text-xs text-red-600">{{ entry.level_name }}</span>
              <Badge theme="gray" variant="subtle">{{ entry.runs }} run{{ entry.runs > 1 ? 's' : '' }}</Badge>
            </div>
            <dl class="mt-2 grid grid-cols-2 gap-2 text-sm">
              <div>
                <dt class="text-xs text-ink-gray-5">Fastest</dt>
                <dd class="tabular-nums">{{ formatTime(entry.fastest.time_seconds) }} <span class="text-ink-gray-5">· {{ entry.fastest.player_name }}</span></dd>
              </div>
              <div>
                <dt class="text-xs text-ink-gray-5">Most kills</dt>
                <dd class="tabular-nums">{{ ratio(entry.most_kills.kills, entry.most_kills.total_kills) }} <span class="text-ink-gray-5">· {{ entry.most_kills.player_name }}</span></dd>
              </div>
            </dl>
          </div>
        </div>
        <EmptyCard v-else :loading="leaderboard.loading" text="No completed level yet. Be the first." />
      </div>

      <div>
        <div class="mb-2 flex items-center justify-between">
          <h2 class="text-base font-semibold">Recent runs</h2>
          <router-link :to="{ name: 'Runs' }" class="text-sm text-ink-blue-3 hover:underline">All runs</router-link>
        </div>
        <div v-if="runs.data?.length" class="divide-y divide-outline-gray-2 rounded-lg border border-outline-gray-2 bg-surface-white">
          <div v-for="run in runs.data" :key="run.name" class="flex items-center gap-3 px-4 py-2.5 text-sm">
            <Avatar :label="run.player_name" size="sm" />
            <div class="min-w-0 flex-1">
              <div class="truncate font-medium">{{ run.player_name }}</div>
              <div class="text-xs text-ink-gray-5">{{ formatDate(run.creation) }}</div>
            </div>
            <div class="text-right tabular-nums">
              <div class="font-doom text-[10px]" :class="run.completed ? 'text-red-600' : 'text-ink-gray-5'">{{ run.level_name }}</div>
              <div class="text-xs text-ink-gray-7">
                {{ ratio(run.kills, run.total_kills) }} · {{ formatTime(run.time_seconds) }}
                <span v-if="!run.completed" class="text-ink-gray-5">· died</span>
              </div>
            </div>
          </div>
        </div>
        <EmptyCard v-else :loading="runs.loading" text="No runs recorded yet." />
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from 'vue'
import { Avatar, Badge, Button, createResource, toast } from 'frappe-ui'
import StatTile from '@/components/StatTile.vue'
import EmptyCard from '@/components/EmptyCard.vue'
import { useDoomEngine } from '@/composables/useDoomEngine'
import { isLoggedIn, loginUrl } from '@/session'
import { formatTime, formatDate, ratio } from '@/utils'

defineOptions({ name: 'Play' })

const engine = useDoomEngine()
const canvasRef = ref(null)

const runs = createResource({ url: 'doom_manager.api.get_runs', params: { limit: 8 }, auto: true })
const leaderboard = createResource({ url: 'doom_manager.api.get_leaderboard', auto: true })

const errorText = (err) => err?.messages?.[0] || err?.message || err

const startRun = createResource({
  url: 'doom_manager.api.start_run',
  onError(err) {
    toast.error(`Could not start the run: ${errorText(err)}`)
  },
})

const finishRun = createResource({
  url: 'doom_manager.api.finish_run',
  onSuccess(name) {
    toast.success(`Run saved (${name})`)
    runs.reload()
    leaderboard.reload()
  },
  onError(err) {
    toast.error(`Could not save the run: ${errorText(err)}`)
  },
})

const outOf = (total) => (total ? `/ ${total}` : '')


const statusDot = computed(() => ({
  loading: 'bg-yellow-400 animate-pulse',
  ready: 'bg-green-500',
  error: 'bg-red-500',
  idle: 'bg-gray-500',
})[engine.state.status])

function onMouseDown(ev) {
  canvasRef.value?.focus()
  engine.pushKey(1, ev.button === 2 ? engine.KEY.USE : engine.KEY.FIRE)
}

// The run opened for the level being played, held as a promise rather than as
// an id: a level can end before start_run has answered (dying in the first
// seconds), and the finish still has to reach the right document.
let openRun = null

function onLevelStart(payload) {
  if (!isLoggedIn.value) return
  // start_run reports its own failures; resolve to null so the finish is skipped.
  openRun = startRun.submit(payload).catch(() => null)
}

function onLevelEnd(payload) {
  if (!isLoggedIn.value) {
    toast.info(`${payload.level} — log in to save runs`)
    return
  }
  const pending = openRun
  openRun = null
  if (!pending) return
  pending.then((run) => {
    if (!run) return
    finishRun.submit({
      run,
      outcome: payload.outcome,
      kills: payload.kills,
      items: payload.items,
      secrets: payload.secrets,
      time_seconds: payload.time_seconds,
    })
  })
}

let unsubscribe = []
onMounted(() => {
  engine.attach(canvasRef.value)
  engine.setActive(true)
  unsubscribe = [engine.onLevelStart(onLevelStart), engine.onLevelEnd(onLevelEnd)]
})
onActivated(() => {
  engine.attach(canvasRef.value)
  engine.setActive(true)
})
onDeactivated(() => engine.setActive(false))
onBeforeUnmount(() => {
  engine.setActive(false)
  unsubscribe.forEach((off) => off())
})
</script>

<style scoped>
.kbd {
  @apply rounded border border-outline-gray-3 bg-surface-gray-2 px-1 py-0.5 font-mono text-xs;
}
</style>
