export default defineNuxtRouteMiddleware(async (to) => {
  // ログインページは認証不要
  if (to.path === '/login') {
    return
  }

  const auth = useAuthStore()

  // 初回アクセス時はユーザー情報を取得
  if (auth.isLoading) {
    await auth.fetchUser()
  }

  // 未認証の場合はログインページへリダイレクト
  if (!auth.isAuthenticated) {
    return navigateTo('/login')
  }
})
