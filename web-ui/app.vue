<template>
  <v-app>
    <v-app-bar color="primary" prominent>
      <v-app-bar-nav-icon></v-app-bar-nav-icon>
      <v-toolbar-title>WoWS Replay Database</v-toolbar-title>
      <v-spacer></v-spacer>
      <v-btn icon>
        <v-icon>mdi-cog</v-icon>
      </v-btn>
    </v-app-bar>

    <v-main>
      <v-container fluid>
        <NuxtPage />
      </v-container>
    </v-main>

    <v-footer app>
      <v-spacer></v-spacer>
      <span>&copy; 2026 WoWS Replay Bot</span>
    </v-footer>
  </v-app>
</template>

<script setup lang="ts">
// Nuxt 3/4では自動的にVue RouterとPiniaがセットアップされます
</script>
