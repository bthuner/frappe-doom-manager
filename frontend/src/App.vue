<template>
  <div class="flex min-h-full flex-col bg-surface-gray-1 text-ink-gray-9">
    <header class="border-b border-outline-gray-2 bg-surface-white">
      <div class="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3 sm:px-6">
        <router-link :to="{ name: 'Play' }" class="flex items-center gap-2">
          <span class="rounded bg-red-600 px-2 py-0.5 font-doom text-xs tracking-widest text-white">DOOM</span>
          <span class="text-base font-semibold">on Frappe</span>
        </router-link>

        <nav class="flex items-center gap-1">
          <router-link v-for="item in nav" :key="item.name" :to="{ name: item.name }" custom v-slot="{ navigate, isActive }">
            <Button :variant="isActive ? 'subtle' : 'ghost'" :icon-left="item.icon" @click="navigate">{{ item.label }}</Button>
          </router-link>
        </nav>

        <div class="ml-auto flex items-center gap-3">
          <template v-if="isLoggedIn">
            <div class="flex items-center gap-2">
              <Avatar :label="session.fullName" size="sm" />
              <span class="text-sm text-ink-gray-8">{{ session.fullName }}</span>
            </div>
            <Button variant="ghost" icon-left="log-out" :loading="logout.loading" @click="logout.submit()">Log out</Button>
          </template>
          <template v-else>
            <Badge theme="orange" variant="subtle">Guest · runs are not saved</Badge>
            <Button variant="solid" icon-left="log-in" :link="loginUrl">Log in</Button>
          </template>
        </div>
      </div>
    </header>

    <main class="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
      <router-view v-slot="{ Component }">
        <!-- keep-alive keeps the game canvas (and the running engine) mounted
             while browsing the runs page -->
        <keep-alive include="Play">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { Avatar, Badge, Button } from 'frappe-ui'
import { session, isLoggedIn, logout, loginUrl } from '@/session'

const nav = [
  { name: 'Play', label: 'Play', icon: 'crosshair' },
  { name: 'Runs', label: 'Runs', icon: 'list' },
]
</script>
