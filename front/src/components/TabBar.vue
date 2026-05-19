<template>
  <van-tabbar v-model="active" route>
    <van-tabbar-item to="/aichat" icon="chat-o">问答</van-tabbar-item>
    <van-tabbar-item to="/knowledgebase" icon="records-o">资料库</van-tabbar-item>
    <van-tabbar-item to="/sessions" icon="comment-circle-o">记录</van-tabbar-item>
    <van-tabbar-item to="/my" icon="user-o">我的</van-tabbar-item>
  </van-tabbar>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const active = ref(0)

// 根据当前路由路径设置激活的标签
const setActiveTab = () => {
  const path = route.path
  if (path.includes('/aichat')) {
    active.value = 0
  } else if (path.includes('/knowledgebase')) {
    active.value = 1
  } else if (path.includes('/sessions')) {
    active.value = 2
  } else if (path.includes('/my')) {
    active.value = 3
  }
}

// 初始化时设置激活标签
setActiveTab()

// 监听路由变化，更新激活标签
watch(() => route.path, () => {
  setActiveTab()
})
</script>

<style scoped>
:deep(.van-tabbar-item__icon) {
  margin-bottom: 3px;
}

:deep(.van-tabbar-item--active) {
  font-weight: 700;
}
</style>
