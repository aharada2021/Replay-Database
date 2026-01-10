<template>
  <div class="match-comments pa-4">
    <h3 class="mb-3">
      <v-icon class="mr-1">mdi-comment-multiple</v-icon>
      コメント ({{ comments.length }})
    </h3>

    <!-- コメント投稿フォーム（認証済みユーザーのみ） -->
    <v-card v-if="authStore.isAuthenticated" variant="outlined" class="mb-4">
      <v-card-text class="pa-3">
        <v-textarea
          v-model="newComment"
          placeholder="コメントを入力..."
          rows="2"
          hide-details
          density="compact"
          :counter="1000"
          :disabled="isSubmitting"
        />
        <div class="d-flex justify-end mt-2">
          <v-btn
            color="primary"
            size="small"
            :loading="isSubmitting"
            :disabled="!newComment.trim() || newComment.length > 1000"
            @click="submitComment"
          >
            <v-icon size="small" class="mr-1">mdi-send</v-icon>
            投稿
          </v-btn>
        </div>
      </v-card-text>
    </v-card>

    <!-- ログイン促進メッセージ -->
    <v-alert v-else type="info" variant="tonal" density="compact" class="mb-4">
      <template v-slot:prepend>
        <v-icon>mdi-login</v-icon>
      </template>
      コメントを投稿するにはログインしてください
      <template v-slot:append>
        <v-btn size="small" variant="text" color="primary" @click="authStore.loginWithDiscord">
          ログイン
        </v-btn>
      </template>
    </v-alert>

    <!-- コメント一覧 -->
    <div v-if="isLoading" class="text-center py-4">
      <v-progress-circular indeterminate />
    </div>

    <div v-else-if="comments.length === 0" class="text-center py-4 text-grey">
      コメントはまだありません
    </div>

    <v-card
      v-else
      v-for="comment in comments"
      :key="comment.commentId"
      variant="outlined"
      class="mb-2 comment-card"
    >
      <v-card-text class="pa-3">
        <!-- 編集モード -->
        <template v-if="editingCommentId === comment.commentId">
          <v-textarea
            v-model="editContent"
            rows="2"
            hide-details
            density="compact"
            :counter="1000"
            :disabled="isSubmitting"
          />
          <div class="d-flex justify-end mt-2 gap-2">
            <v-btn
              size="small"
              variant="text"
              @click="cancelEdit"
            >
              キャンセル
            </v-btn>
            <v-btn
              color="primary"
              size="small"
              :loading="isSubmitting"
              :disabled="!editContent.trim() || editContent.length > 1000"
              @click="saveEdit(comment)"
            >
              保存
            </v-btn>
          </div>
        </template>

        <!-- 通常表示 -->
        <template v-else>
          <!-- ヘッダー -->
          <div class="d-flex align-center mb-2">
            <v-avatar size="28" class="mr-2">
              <v-img
                v-if="comment.discordAvatar"
                :src="comment.discordAvatar"
                :alt="comment.discordGlobalName || comment.discordUsername"
              />
              <v-icon v-else>mdi-account</v-icon>
            </v-avatar>
            <span class="font-weight-bold text-body-2">
              {{ comment.discordGlobalName || comment.discordUsername }}
            </span>
            <span class="text-caption text-grey ml-2">
              {{ formatRelativeTime(comment.createdAt) }}
              <span v-if="comment.updatedAt" class="text-grey-darken-1"> (編集済み)</span>
            </span>
          </div>

          <!-- コメント本文 -->
          <p class="text-body-2 mb-2" style="white-space: pre-wrap;">{{ comment.content }}</p>

          <!-- アクション -->
          <div class="d-flex align-center">
            <!-- いいねボタン -->
            <v-btn
              size="x-small"
              variant="text"
              :color="isLikedByMe(comment) ? 'pink' : 'grey'"
              :disabled="!authStore.isAuthenticated"
              @click="toggleLike(comment)"
            >
              <v-icon size="small">{{ isLikedByMe(comment) ? 'mdi-heart' : 'mdi-heart-outline' }}</v-icon>
              <span class="ml-1">{{ comment.likeCount }}</span>
            </v-btn>

            <v-spacer />

            <!-- 編集・削除ボタン（認証済みユーザーのみ） -->
            <template v-if="authStore.isAuthenticated">
              <v-btn
                size="x-small"
                variant="text"
                color="grey"
                @click="startEdit(comment)"
              >
                <v-icon size="small">mdi-pencil</v-icon>
              </v-btn>
              <v-btn
                size="x-small"
                variant="text"
                color="error"
                @click="confirmDelete(comment)"
              >
                <v-icon size="small">mdi-delete</v-icon>
              </v-btn>
            </template>
          </div>
        </template>
      </v-card-text>
    </v-card>

    <!-- 削除確認ダイアログ -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title>コメントを削除</v-card-title>
        <v-card-text>
          このコメントを削除してもよろしいですか？
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">キャンセル</v-btn>
          <v-btn color="error" variant="flat" :loading="isDeleting" @click="executeDelete">
            削除
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { Comment } from '~/types/replay'
import { useAuthStore } from '~/stores/auth'

const props = defineProps<{
  arenaUniqueId: string
}>()

const authStore = useAuthStore()
const api = useApi()

// 状態
const comments = ref<Comment[]>([])
const newComment = ref('')
const isLoading = ref(true)
const isSubmitting = ref(false)
const isDeleting = ref(false)

// 編集
const editingCommentId = ref<string | null>(null)
const editContent = ref('')

// 削除
const deleteDialog = ref(false)
const commentToDelete = ref<Comment | null>(null)

// コメント読み込み
const loadComments = async () => {
  isLoading.value = true
  try {
    comments.value = await api.getComments(props.arenaUniqueId)
  } catch (error) {
    console.error('Failed to load comments:', error)
  } finally {
    isLoading.value = false
  }
}

// コメント投稿
const submitComment = async () => {
  if (!newComment.value.trim() || isSubmitting.value) return

  isSubmitting.value = true
  try {
    const comment = await api.postComment(props.arenaUniqueId, newComment.value.trim())
    if (comment) {
      comments.value.push(comment)
      newComment.value = ''
    }
  } catch (error) {
    console.error('Failed to post comment:', error)
  } finally {
    isSubmitting.value = false
  }
}

// 編集開始
const startEdit = (comment: Comment) => {
  editingCommentId.value = comment.commentId
  editContent.value = comment.content
}

// 編集キャンセル
const cancelEdit = () => {
  editingCommentId.value = null
  editContent.value = ''
}

// 編集保存
const saveEdit = async (comment: Comment) => {
  if (!editContent.value.trim() || isSubmitting.value) return

  isSubmitting.value = true
  try {
    const updated = await api.updateComment(
      props.arenaUniqueId,
      comment.commentId,
      editContent.value.trim()
    )
    if (updated) {
      const index = comments.value.findIndex(c => c.commentId === comment.commentId)
      if (index !== -1) {
        comments.value[index] = updated
      }
    }
    editingCommentId.value = null
    editContent.value = ''
  } catch (error) {
    console.error('Failed to update comment:', error)
  } finally {
    isSubmitting.value = false
  }
}

// 削除確認
const confirmDelete = (comment: Comment) => {
  commentToDelete.value = comment
  deleteDialog.value = true
}

// 削除実行
const executeDelete = async () => {
  if (!commentToDelete.value || isDeleting.value) return

  isDeleting.value = true
  try {
    await api.deleteComment(props.arenaUniqueId, commentToDelete.value.commentId)
    comments.value = comments.value.filter(c => c.commentId !== commentToDelete.value!.commentId)
    deleteDialog.value = false
    commentToDelete.value = null
  } catch (error) {
    console.error('Failed to delete comment:', error)
  } finally {
    isDeleting.value = false
  }
}

// いいね判定
const isLikedByMe = (comment: Comment): boolean => {
  if (!authStore.user) return false
  return comment.likes?.includes(authStore.user.id) || false
}

// いいねトグル
const toggleLike = async (comment: Comment) => {
  if (!authStore.isAuthenticated) return

  try {
    const updated = await api.likeComment(props.arenaUniqueId, comment.commentId)
    if (updated) {
      const index = comments.value.findIndex(c => c.commentId === comment.commentId)
      if (index !== -1) {
        comments.value[index] = updated
      }
    }
  } catch (error) {
    console.error('Failed to like comment:', error)
  }
}

// 相対時間フォーマット
const formatRelativeTime = (dateTime: string): string => {
  try {
    const date = new Date(dateTime)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const seconds = Math.floor(diff / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (seconds < 60) return 'たった今'
    if (minutes < 60) return `${minutes}分前`
    if (hours < 24) return `${hours}時間前`
    if (days < 7) return `${days}日前`

    // 7日以上前は日付表示
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}/${month}/${day}`
  } catch {
    return dateTime
  }
}

onMounted(() => {
  loadComments()
})
</script>

<style scoped>
.match-comments {
  background: rgba(255, 255, 255, 0.02);
  border-radius: 8px;
}

.comment-card {
  transition: background-color 0.2s;
}

.comment-card:hover {
  background: rgba(255, 255, 255, 0.03);
}

.gap-2 {
  gap: 8px;
}
</style>
