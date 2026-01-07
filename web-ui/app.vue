<template>
  <v-app>
    <v-app-bar v-if="showAppBar" color="primary" prominent>
      <v-app-bar-nav-icon></v-app-bar-nav-icon>
      <v-toolbar-title>WoWS Replay Database</v-toolbar-title>
      <v-spacer></v-spacer>

      <!-- ユーザーメニュー -->
      <template v-if="auth.isAuthenticated && auth.user">
        <v-menu offset-y>
          <template v-slot:activator="{ props }">
            <v-btn v-bind="props" variant="text" class="text-none">
              <v-avatar size="32" class="mr-2">
                <v-img v-if="auth.user.avatar" :src="auth.user.avatar" :alt="auth.displayName"></v-img>
                <v-icon v-else>mdi-account-circle</v-icon>
              </v-avatar>
              <span class="d-none d-sm-inline">{{ auth.displayName }}</span>
              <v-icon end>mdi-menu-down</v-icon>
            </v-btn>
          </template>
          <v-list>
            <v-list-item>
              <v-list-item-title class="text-caption text-grey">
                {{ auth.user.username }}
              </v-list-item-title>
            </v-list-item>
            <v-divider></v-divider>
            <v-list-item @click="handleLogout">
              <template v-slot:prepend>
                <v-icon>mdi-logout</v-icon>
              </template>
              <v-list-item-title>ログアウト</v-list-item-title>
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

// 初回マウント時にユーザー情報を取得
onMounted(async () => {
  console.log('[App] onMounted - isLoading:', auth.isLoading)
  if (auth.isLoading) {
    await auth.fetchUser()
  }
  console.log('[App] After fetchUser - isAuthenticated:', auth.isAuthenticated)
  console.log('[App] After fetchUser - user:', auth.user)
  console.log('[App] After fetchUser - avatar:', auth.user?.avatar)
})

const handleLogout = async () => {
  await auth.logout()
  router.push('/login')
}
</script>
