<template>
  <v-app>
    <v-app-bar v-if="showAppBar" color="primary" density="compact" height="48">
      <v-app-bar-nav-icon size="small"></v-app-bar-nav-icon>
      <v-toolbar-title class="text-body-1">WoWS Replay Database</v-toolbar-title>
      <v-spacer></v-spacer>

      <!-- ユーザーメニュー -->
      <template v-if="auth.isAuthenticated && auth.user">
        <v-menu offset-y>
          <template v-slot:activator="{ props }">
            <v-btn v-bind="props" variant="text" class="text-none" size="small">
              <v-avatar size="24" class="mr-1">
                <v-img v-if="auth.user.avatar" :src="auth.user.avatar" :alt="auth.displayName"></v-img>
                <v-icon v-else size="small">mdi-account-circle</v-icon>
              </v-avatar>
              <span class="d-none d-sm-inline text-caption">{{ auth.displayName }}</span>
              <v-icon end size="small">mdi-menu-down</v-icon>
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-item>
              <v-list-item-title class="text-caption text-grey">
                {{ auth.user.username }}
              </v-list-item-title>
            </v-list-item>
            <v-divider></v-divider>
            <v-list-item @click="handleLogout">
              <template v-slot:prepend>
                <v-icon size="small">mdi-logout</v-icon>
              </template>
              <v-list-item-title class="text-body-2">ログアウト</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
      </template>
    </v-app-bar>

    <v-main>
      <v-container fluid>
        <NuxtPage />
      </v-container>
    </v-main>

    <v-footer v-if="showAppBar" app class="py-1">
      <v-spacer></v-spacer>
      <span class="text-caption">&copy; 2026 WoWS Replay Bot</span>
    </v-footer>
  </v-app>
</template>

<script setup lang="ts">
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

// ログインページではヘッダー・フッターを非表示
const showAppBar = computed(() => route.path !== '/login')

// 初回マウント時にユーザー情報を取得
onMounted(async () => {
  if (auth.isLoading) {
    await auth.fetchUser()
  }
})

const handleLogout = async () => {
  await auth.logout()
  router.push('/login')
}
</script>
