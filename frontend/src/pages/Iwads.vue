<template>
  <div class="mx-auto max-w-3xl space-y-6">
    <div>
      <h1 class="text-lg font-semibold">Game data</h1>
      <p class="mt-1 text-sm text-ink-gray-6">
        The engine ships with Freedoom, which is freely redistributable. Upload your own IWAD to
        play the game you own — it stays private to your account and is never served to anyone
        else.
      </p>
    </div>

    <!-- Upload -->
    <div v-if="isLoggedIn" class="rounded-lg border border-outline-gray-2 bg-surface-white p-4">
      <div class="mb-3 text-sm font-medium">Add an IWAD</div>
      <FileUploader
        :file-types="['.wad', '.WAD']"
        :upload-args="{ private: true, folder: 'Home/Doom' }"
        @success="onUploaded"
        @failure="onUploadFailed"
      >
        <template #default="{ openFileSelector, uploading, progress }">
          <div class="flex items-center gap-3">
            <Button :loading="uploading || registering" @click="openFileSelector">
              {{ uploading ? `Uploading ${progress}%` : 'Choose a .wad file' }}
            </Button>
            <span class="text-xs text-ink-gray-5">
              A full IWAD (doom.wad, doom2.wad…), not a PWAD. Up to 50 MB.
            </span>
          </div>
        </template>
      </FileUploader>
    </div>
    <div v-else class="rounded-lg border border-outline-gray-2 bg-surface-white p-4 text-sm">
      <a :href="loginUrl" class="text-ink-blue-3 underline">Log in</a> to upload your own IWAD.
      You are playing the bundled Freedoom.
    </div>

    <!-- List -->
    <div v-if="iwads.data?.length" class="divide-y divide-outline-gray-2 rounded-lg border border-outline-gray-2 bg-surface-white">
      <div v-for="entry in iwads.data" :key="entry.name || 'shipped'" class="flex items-center gap-3 px-4 py-3">
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <span class="truncate text-sm font-medium">{{ entry.title }}</span>
            <Badge v-if="entry.active" theme="green" variant="subtle">Playing</Badge>
            <Badge v-if="entry.is_default" theme="blue" variant="subtle">Default</Badge>
            <Badge v-if="entry.owned" theme="gray" variant="subtle">Yours</Badge>
            <Badge v-if="entry.is_free" theme="green" variant="outline">Free</Badge>
          </div>
          <div class="mt-0.5 text-xs text-ink-gray-5">
            {{ entry.file_name }} · {{ megabytes(entry.file_size) }}
          </div>
        </div>

        <Button
          v-if="!entry.active"
          size="sm"
          :loading="selecting"
          @click="choose(entry)"
        >Play this</Button>

        <Button
          v-if="isAdmin && entry.name && entry.is_free && !entry.is_default && !entry.owned"
          size="sm"
          variant="subtle"
          :loading="settingDefault"
          @click="makeDefault(entry)"
        >Make default</Button>

        <Button
          v-if="entry.owned"
          size="sm"
          variant="ghost"
          theme="red"
          icon="trash-2"
          :loading="removing"
          @click="remove(entry)"
        />
      </div>
    </div>
    <EmptyCard v-else :loading="iwads.loading" text="No IWAD available." />

    <p class="text-xs text-ink-gray-5">
      Only a freely redistributable IWAD can be made the default, because the default is what
      guests are served. Your own uploads are yours alone: they can be played by you and are
      refused to every other session.
    </p>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Badge, Button, FileUploader, createResource, toast } from 'frappe-ui'
import EmptyCard from '@/components/EmptyCard.vue'
import { isLoggedIn, loginUrl, session } from '@/session'

defineOptions({ name: 'Iwads' })

const errorText = (err) => err?.messages?.[0] || err?.message || err
const megabytes = (n) => (n ? (n / 1048576).toFixed(1) + ' MB' : '—')

const isAdmin = computed(() => session.user === 'Administrator')

const iwads = createResource({ url: 'doom_manager.api.list_iwads', auto: true })

const registering = ref(false)
const selecting = ref(false)
const settingDefault = ref(false)
const removing = ref(false)

function run(flag, resource, params, okMessage) {
  flag.value = true
  return resource
    .submit(params)
    .then(() => {
      toast.success(okMessage)
      iwads.reload()
    })
    .catch((err) => toast.error(errorText(err)))
    .finally(() => (flag.value = false))
}

const registerIwad = createResource({ url: 'doom_manager.api.register_iwad' })
const selectIwad = createResource({ url: 'doom_manager.api.select_iwad' })
const defaultIwad = createResource({ url: 'doom_manager.api.set_default_iwad' })
const removeIwad = createResource({ url: 'doom_manager.api.delete_iwad' })

function onUploaded(file) {
  run(
    registering,
    registerIwad,
    { file_url: file.file_url, title: file.file_name },
    'IWAD added. Choose "Play this", then reload the page to boot it.',
  )
}

const onUploadFailed = (err) => toast.error(errorText(err) || 'Upload failed')

const choose = (entry) =>
  run(selecting, selectIwad, { iwad: entry.name || '' },
      'Selected. Reload the page to boot it — the engine only reads its IWAD at startup.')

const makeDefault = (entry) =>
  run(settingDefault, defaultIwad, { iwad: entry.name }, 'Default updated.')

const remove = (entry) => run(removing, removeIwad, { iwad: entry.name }, 'Removed.')
</script>
