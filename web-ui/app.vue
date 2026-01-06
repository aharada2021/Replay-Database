<template>
  <v-app>
    <v-app-bar v-if="showAppBar" color="primary" prominent>
      <v-app-bar-nav-icon></v-app-bar-nav-icon>
      <v-toolbar-title>WoWS Replay Database</v-toolbar-title>
      <v-spacer></v-spacer>

      <!-- ユーザー情報 -->
      <template v-if="auth.isAuthenticated && auth.user">
        <v-avatar v-if="auth.user.avatar" size="32" class="mr-2">
          <v-img :src="auth.user.avatar" :alt="auth.displayName"></v-img>
        </v-avatar>
        <span class="mr-4 text-body-2">{{ auth.displayName }}</span>
        <v-btn icon @click="handleLogout" title="ログアウト">
          <v-icon>mdi-logout</v-icon>
        </v-btn>
      </template>
    </v-app-bar>

    <v-main>
      <v-container fluid>
        <NuxtPage />
      </v-container>
    </v-main>

    <v-footer v-if="showAppBar" app>
      <v-spacer></v-spacer>
      <span>&copy; 2026 WoWS Replay Bot</span>
    </v-footer>
  </v-app>
</template>

<script setup lang="ts">
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

// ログインページではヘッダー・フッターを非表示
const showAppBar = computed(() => route.path !== '/login')

const handleLogout = async () => {
  await auth.logout()
  router.push('/login')
}
</script>
