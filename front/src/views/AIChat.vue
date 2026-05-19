<template>
  <div class="ai-chat-container">
    <van-nav-bar 
      title="本地文档问答台" 
      fixed 
      right-text="会话" 
      @click-right="goToSessions"
    />
    
    <div class="chat-content">
      <section class="workspace-summary">
        <div>
          <p class="summary-kicker">Private RAG Workspace</p>
          <h1>把问题交给你的资料库</h1>
          <p class="summary-copy">回答优先来自已上传文档，检索过程会显示在消息中，方便核对来源。</p>
        </div>
        <button class="summary-action" @click="router.push('/knowledgebase')">上传资料</button>
      </section>

      <div class="messages-container" ref="messagesContainer">
        <div 
          v-for="(message, index) in messages" 
          :key="index"
          :class="['message', message.role === 'user' ? 'user-message' : 'ai-message']"
        >
          <div class="message-content">
            <!-- 思考过程区域 -->
            <div v-if="message.thinking && message.thinking.length > 0" class="thinking-section">
              <div class="thinking-header" @click="toggleThinking(message)">
                <span class="thinking-label">检索轨迹</span>
                <span class="thinking-toggle">{{ message.thinkingCollapsed ? '展开' : '收起' }}</span>
              </div>
              <div v-show="!message.thinkingCollapsed" class="thinking-body">
                <div v-for="(step, sIndex) in message.thinking" :key="sIndex" class="thinking-step">
                  <span class="thinking-stage-label" :style="{ backgroundColor: getStageColor(step.stage) }">
                    {{ getStageLabel(step.stage) }}
                  </span>
                  <span class="thinking-step-content">{{ step.content }}</span>
                  <div v-if="step.details" class="thinking-details">
                    <template v-if="step.details.documents">
                      <div v-for="(doc, dIndex) in step.details.documents.slice(0, 3)" :key="dIndex" class="thinking-doc-item">
                        <span class="thinking-doc-source">{{ doc.source }}</span>
                        <span class="thinking-doc-score">{{ (doc.score * 100).toFixed(0) }}%</span>
                      </div>
                      <div v-if="step.details.documents.length > 3" class="thinking-doc-more">
                        ... 还有 {{ step.details.documents.length - 3 }} 个文档
                      </div>
                    </template>
                    <template v-else-if="step.details.scores">
                      <div v-for="(sc, cIndex) in step.details.scores.slice(0, 3)" :key="cIndex" class="thinking-score-item">
                        <span>#{{ sc.rank || sc.index }}</span>
                        <span>{{ (sc.score * 100).toFixed(0) }}%</span>
                        <span class="thinking-score-preview">{{ truncateText(sc.preview, 40) }}</span>
                      </div>
                    </template>
                    <template v-else-if="step.details.hypothetical_doc_preview">
                      <div class="thinking-detail-text">{{ truncateText(step.details.hypothetical_doc_preview, 80) }}</div>
                    </template>
                    <template v-else>
                      <div v-for="(val, key) in step.details" :key="key" class="thinking-detail-kv">
                        <span class="thinking-detail-key">{{ key }}:</span>
                        <span class="thinking-detail-val">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>
            <!-- 回复正文 -->
            <div v-if="message.content" v-html="formatMessage(message.content)"></div>
            <!-- 打字指示器（无内容且无思考过程时显示） -->
            <div v-if="message.role === 'assistant' && !message.content && (!message.thinking || message.thinking.length === 0)" class="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      </div>
      
      <div class="input-container">
        <van-field
          v-model="userInput"
          rows="1"
          autosize
          type="textarea"
          placeholder="请输入问题..."
          class="chat-input"
          @keypress.enter.prevent="sendMessage"
        />
        <van-button 
          type="primary" 
          class="send-button" 
          :disabled="isLoading || !userInput.trim()" 
          @click="sendMessage"
        >
          提问
        </van-button>
      </div>
    </div>
    
    <tab-bar />
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import TabBar from '../components/TabBar.vue';
import { showToast } from 'vant';
import { marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js';
import 'highlight.js/styles/monokai-sublime.css';
import 'highlight.js/lib/common';
import { apiConfig } from '../config/api';
import { useUserStore } from '../store/user';
import { useSessionStore } from '../store/session';

// 从cookie中获取CSRF token
const getCsrfToken = () => {
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  return cookieValue || '';
};

// 聊天消息
const messages = ref([
  { role: 'assistant', content: '你好，我会优先检索你上传的资料，再给出回答。可以先去资料库上传 PDF、Word、PPT 或 Markdown。' }
]);
const userInput = ref('');
const messagesContainer = ref(null);
const isLoading = ref(false);
const sessionId = ref('');
const hasJumped = ref(false);
const autoCollapseTimer = ref(null);

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();
const sessionStore = useSessionStore();

const resetToFreshChat = () => {
  sessionId.value = '';
  sessionStore.setCurrentSession(null);
  messages.value = [
    { role: 'assistant', content: '你好，我会优先检索你上传的资料，再给出回答。可以先去资料库上传 PDF、Word、PPT 或 Markdown。' }
  ];
  if (route.params.sessionId) {
    router.replace('/aichat');
  }
};

const ensureChatToken = async () => {
  const storedToken = localStorage.getItem('jwt_token');
  if (userStore.token && userStore.token !== 'test_token_for_unlogin') {
    return userStore.token;
  }

  if (storedToken && storedToken !== 'test_token_for_unlogin') {
    userStore.restoreFromLocalStorage();
    return userStore.token;
  }

  return '';
};

// 配置marked使用marked-highlight插件
marked.use(markedHighlight({
  langPrefix: 'hljs language-',
  highlight(code, lang) {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext';
    return hljs.highlight(code, { language }).value;
  }
}));

// 格式化消息内容（支持Markdown和代码高亮）
const formatMessage = (content) => {
  if (!content) return '';
  try {
    // 使用marked解析Markdown，并用DOMPurify清理HTML
    const parsed = marked(content, {
      breaks: true,
      gfm: true,
      headerIds: false,
      mangle: false
    });
    const sanitized = DOMPurify.sanitize(parsed);
    return sanitized;
  } catch (error) {
    console.error('Markdown解析错误:', error);
    return content;
  }
};

// 思考过程阶段配置
const stageConfig = {
  retrieval:  { label: '检索',   color: '#0f766e' },
  hyde:       { label: '扩展',   color: '#5b6f9b' },
  reorder:    { label: '排序', color: '#c06c2f' },
  summarize:  { label: '生成',   color: '#4f8a5f' }
};

const getStageLabel = (stage) => {
  return stageConfig[stage]?.label || stage || '处理中';
};

const getStageColor = (stage) => {
  return stageConfig[stage]?.color || '#999';
};

const truncateText = (text, maxLen) => {
  if (!text) return '';
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text;
};

// localStorage 存储最近 5 条思考过程
const THINKING_HISTORY_KEY = 'ai_thinking_history';

const saveThinkingToHistory = (sessionId, query, thinking) => {
  if (!sessionId || !thinking || thinking.length === 0) return;
  try {
    let history = JSON.parse(localStorage.getItem(THINKING_HISTORY_KEY) || '[]');
    history = history.filter(e => e.sessionId !== sessionId);
    history.unshift({ sessionId, query, thinking, timestamp: Date.now() });
    localStorage.setItem(THINKING_HISTORY_KEY, JSON.stringify(history.slice(0, 5)));
  } catch (e) { /* ignore */ }
};

const loadThinkingFromHistory = (sessionId) => {
  if (!sessionId) return null;
  try {
    const history = JSON.parse(localStorage.getItem(THINKING_HISTORY_KEY) || '[]');
    return history.find(e => e.sessionId === sessionId)?.thinking || null;
  } catch (e) {
    return null;
  }
};

// 切换思考过程展开/折叠（用户手动操作时取消自动折叠定时器）
const toggleThinking = (message) => {
  message.thinkingCollapsed = !message.thinkingCollapsed;
  if (autoCollapseTimer.value) {
    clearTimeout(autoCollapseTimer.value);
    autoCollapseTimer.value = null;
  }
};

// 发送消息
const sendMessage = async () => {
  if (!userInput.value.trim() || isLoading.value) return;
  
  // 检查是否登录
  const token = await ensureChatToken();
  if (!token) {
    showToast('请先登录');
    return;
  }
  
  // 添加用户消息
  const userMessage = userInput.value.trim();
  messages.value.push({ role: 'user', content: userMessage });
  userInput.value = '';
  
  // 添加AI消息占位（含思考过程字段）
  messages.value.push({ role: 'assistant', content: '', thinking: [], thinkingCollapsed: false, thinkingAutoCollapsed: false });
  
  // 滚动到底部
  await nextTick();
  scrollToBottom();
  
  // 发送请求
  isLoading.value = true;
  try {
    await fetchAIResponse(userMessage);
  } catch (error) {
    console.error('Error fetching AI response:', error);
    // 更新最后一条消息为错误信息
    messages.value[messages.value.length - 1].content = `发生错误: ${error.message || '请检查网络连接和API设置'}`;
  } finally {
    isLoading.value = false;
    await nextTick();
    scrollToBottom();
  }
};

// 获取AI响应（使用SSE）
const fetchAIResponse = async (userMessage) => {
  try {
    // 确保使用正确的相对路径，通过Vite代理访问
    const url = '/chat/agent/query/stream';
    // 从localStorage获取token
    const token = await ensureChatToken();
    // console.log('发送AI请求到:', url);
    // console.log('使用的token:', token);
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        session_id: sessionId.value || undefined,
        query: userMessage
      })
    });
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
    
    // 处理SSE流
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let aiResponse = '';
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (!data) continue;
        
        try {
          const json = JSON.parse(data);
          
          switch (json.type) {
            case 'step':
              break;
            case 'thinking':
              {
                const idx = messages.value.length - 1;
                if (messages.value[idx].role === 'assistant') {
                  const newStep = {
                    stage: json.stage || '',
                    content: json.content || '',
                    details: json.details || null
                  };
                  // 完整替换消息对象以强制 Vue 重新渲染
                  messages.value[idx] = {
                    ...messages.value[idx],
                    thinking: [...messages.value[idx].thinking, newStep]
                  };
                  // 等待 Vue DOM 刷新 + 浏览器 paint
                  await nextTick();
                  await new Promise(resolve => requestAnimationFrame(resolve));
                  scrollToBottom();
                }
              }
              break;
            case 'response':
              {
                const lastMsg = messages.value[messages.value.length - 1];
                // 第一条 response 到达时延迟折叠思考过程（仅一次）
                if (!lastMsg.thinkingAutoCollapsed && lastMsg.thinking.length > 0) {
                  lastMsg.thinkingAutoCollapsed = true;
                  if (autoCollapseTimer.value) clearTimeout(autoCollapseTimer.value);
                  autoCollapseTimer.value = setTimeout(() => {
                    lastMsg.thinkingCollapsed = true;
                    autoCollapseTimer.value = null;
                  }, 1500);
                }
                const content = json.content || '';
                if (content) {
                  aiResponse += content;
                  
                  // 逐字符显示打字机效果
                  const displayContent = lastMsg.content || '';
                  const remainingContent = aiResponse.substring(displayContent.length);
                  
                  for (const char of remainingContent) {
                    lastMsg.content += char;
                  await new Promise(resolve => setTimeout(resolve, 0));
                    scrollToBottom();
                    // 控制打字速度，每个字符延迟8ms
                    await new Promise(resolve => setTimeout(resolve, 8));
                  }
                }
                // 保存会话ID（不立即跳转，避免中断SSE）
                if (json.session_id && typeof json.session_id === 'string' && json.session_id.trim()) {
                  sessionId.value = json.session_id;
                }
              }
              break;
            case 'done':
              {
                const sid = json.session_id;
                if (sid && typeof sid === 'string' && sid.trim()) {
                  sessionId.value = sid;
                  // 保存思考过程到 localStorage
                  const lastMsg = messages.value[messages.value.length - 1];
                  if (lastMsg && lastMsg.role === 'assistant') {
                    saveThinkingToHistory(sid, userMessage, lastMsg.thinking);
                  }
                  // 如果当前路由没有sessionId参数，跳转到带sessionId的路由
                  if (!route.params.sessionId) {
                    router.push(`/aichat/${sid}`);
                  }
                }
              }
              break;
            case 'error':
              if ((json.content || '').includes('当前会话不属于你')) {
                sessionId.value = '';
                await fetchAIResponse(userMessage);
                return;
              }
              throw new Error(json.content || 'API错误');
              break;
          }
        } catch (e) {
          console.error('Error parsing SSE data:', e);
        }
      }
    }
  }
  
  // 如果没有收到任何内容
  if (!aiResponse) {
    messages.value[messages.value.length - 1].content = '抱歉，我无法生成回复。请检查API设置或稍后再试。';
  }
  } catch (error) {
    console.error('Fetch error:', error);
    throw error;
  }
};

// 跳转到会话管理页面
const goToSessions = () => {
  router.push('/sessions');
};

// 滚动到底部
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

// 监听消息变化，自动滚动
watch(messages, () => {
  nextTick(() => {
    scrollToBottom();
  });
}, { deep: true });

// 监听路由参数变化，重新加载会话历史
watch(() => route.params.sessionId, async (newSessionId) => {
  await ensureChatToken();
  if (newSessionId) {
    try {
      const result = await sessionStore.getSession(newSessionId);
      if (result.success && sessionStore.currentSession) {
        loadSessionHistory(sessionStore.currentSession);
      } else {
        resetToFreshChat();
      }
    } catch (error) {
      console.error('加载会话历史失败:', error);
      resetToFreshChat();
    }
  }
}, { immediate: true });

// 组件挂载时检查是否有当前会话或路由参数中的会话ID
onMounted(async () => {
  await ensureChatToken();

  // 检查路由参数中是否有sessionId
  const routeSessionId = route.params.sessionId;
  
  if (routeSessionId) {
    // 从路由参数获取会话ID，加载会话历史
    try {
      const result = await sessionStore.getSession(routeSessionId);
      if (result.success && sessionStore.currentSession) {
        loadSessionHistory(sessionStore.currentSession);
      } else {
        resetToFreshChat();
      }
    } catch (error) {
      console.error('加载会话历史失败:', error);
      resetToFreshChat();
    }
  } else if (sessionStore.currentSession) {
    // 从store中加载会话历史
    loadSessionHistory(sessionStore.currentSession);
  }
  
  scrollToBottom();
});

// 加载会话历史
const loadSessionHistory = (session) => {
  if (session.history && session.history.length > 0) {
    // 清空当前消息
    messages.value = [];
    // 加载历史消息
    session.history.forEach(([userMsg, aiMsg]) => {
      messages.value.push({ role: 'user', content: userMsg });
      messages.value.push({ role: 'assistant', content: aiMsg, thinking: [], thinkingCollapsed: true, thinkingAutoCollapsed: true });
    });
    // 设置会话ID
    sessionId.value = session.session_id;
    // 从 localStorage 恢复思考过程
    const saved = loadThinkingFromHistory(session.session_id);
    if (saved && messages.value.length > 0) {
      const last = messages.value[messages.value.length - 1];
      if (last.role === 'assistant') {
        last.thinking = saved;
      }
    }
  }
};
</script>

<style scoped>
.ai-chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding-top: 46px;
  padding-bottom: 50px;
  box-sizing: border-box;
  background:
    linear-gradient(180deg, rgba(15, 118, 110, 0.08), rgba(238, 246, 243, 0) 220px),
    var(--background-color);
}

.chat-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.workspace-summary {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin: 14px 14px 8px;
  padding: 16px;
  border: 1px solid rgba(15, 118, 110, 0.14);
  border-radius: 8px;
  background: linear-gradient(135deg, #fbfdfc 0%, #e8f6f1 100%);
  box-shadow: 0 14px 34px rgba(33, 63, 55, 0.08);
}

.summary-kicker {
  margin: 0 0 5px;
  font-size: 11px;
  font-weight: 700;
  color: var(--primary-color);
  text-transform: uppercase;
}

.workspace-summary h1 {
  margin: 0;
  font-size: 19px;
  line-height: 1.2;
  color: var(--ink);
}

.summary-copy {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-color-light);
}

.summary-action {
  flex: 0 0 auto;
  border: 0;
  border-radius: 6px;
  padding: 10px 12px;
  background: var(--primary-color);
  color: #fff;
  font-weight: 700;
  box-shadow: 0 8px 18px rgba(15, 118, 110, 0.2);
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 10px 14px 14px;
}

.message {
  margin-bottom: 12px;
  max-width: 86%;
}

.user-message {
  margin-left: auto;
}

.ai-message {
  margin-right: auto;
}

.message-content {
  padding: 11px 13px;
  border-radius: 8px;
  word-break: break-word;
  box-shadow: 0 8px 20px rgba(33, 63, 55, 0.06);
}

.user-message .message-content {
  background: #0f766e;
  color: white;
  border-bottom-right-radius: 2px;
}

.ai-message .message-content {
  background-color: #fbfdfc;
  color: var(--text-color);
  border: 1px solid rgba(15, 118, 110, 0.1);
  border-bottom-left-radius: 2px;
}

.input-container {
  display: flex;
  padding: 10px 14px 12px;
  border-top: 1px solid rgba(15, 118, 110, 0.1);
  background-color: rgba(251, 253, 252, 0.96);
  box-shadow: 0 -10px 24px rgba(33, 63, 55, 0.05);
}

.chat-input {
  flex: 1;
  margin-right: 10px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  border-radius: 8px;
  overflow: hidden;
}

.send-button {
  align-self: flex-end;
  min-width: 72px;
  border-radius: 6px;
}

/* Markdown 样式 */
.message-content pre {
  background-color: #f8f8f8;
  padding: 10px;
  border-radius: 5px;
  overflow-x: auto;
}

.message-content code {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 2px 4px;
  border-radius: 3px;
}

.message-content img {
  max-width: 100%;
}

/* 打字指示器 */
.typing-indicator {
  display: flex;
  padding: 5px;
}

.typing-indicator span {
  height: 8px;
  width: 8px;
  background-color: #999;
  border-radius: 50%;
  margin: 0 2px;
  display: inline-block;
  animation: bounce 1.5s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-5px);
  }
}

/* Markdown样式 */
:deep(pre) {
  background-color: #1e1e1e;
  padding: 15px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 10px 0;
  color: #d4d4d4;
}

:deep(pre code) {
  background-color: transparent;
  padding: 0;
  border-radius: 0;
  color: #d4d4d4;
}

:deep(code) {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  background-color: rgba(0, 0, 0, 0.05);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
}

:deep(p) {
  margin: 8px 0;
  line-height: 1.5;
}

:deep(ul), :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}

:deep(li) {
  margin: 4px 0;
  line-height: 1.5;
}

:deep(a) {
  color: #1989fa;
  text-decoration: none;
}

:deep(a:hover) {
  text-decoration: underline;
}

:deep(h1), :deep(h2), :deep(h3), :deep(h4), :deep(h5), :deep(h6) {
  margin: 12px 0 8px 0;
  font-weight: bold;
}

:deep(h1) {
  font-size: 1.5em;
}

:deep(h2) {
  font-size: 1.3em;
}

:deep(h3) {
  font-size: 1.1em;
}

:deep(blockquote) {
  border-left: 4px solid #1989fa;
  padding-left: 10px;
  margin: 10px 0;
  color: #666;
  background-color: #f9f9f9;
  padding: 8px 12px;
  border-radius: 0 4px 4px 0;
}

:deep(hr) {
  border: 0;
  border-top: 1px solid #eee;
  margin: 16px 0;
}

:deep(img) {
  max-width: 100%;
  border-radius: 4px;
  margin: 8px 0;
}

:deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
}

:deep(th), :deep(td) {
  border: 1px solid #ddd;
  padding: 8px;
  text-align: left;
}

:deep(th) {
  background-color: #f2f2f2;
  font-weight: bold;
}

/* 思考过程样式 */
.thinking-section {
  margin-bottom: 8px;
  border-left: 3px solid var(--primary-color);
  padding-left: 8px;
  background-color: #edf8f5;
  border-radius: 4px;
  padding: 6px 8px;
  font-size: 12px;
}

.thinking-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
  padding: 2px 0;
}

.thinking-label {
  color: var(--primary-strong);
  font-weight: 500;
  font-size: 12px;
}

.thinking-toggle {
  color: var(--text-color-lighter);
  font-size: 11px;
}

.thinking-body {
  margin-top: 4px;
}

.thinking-step {
  padding: 4px 0;
  border-bottom: 1px solid rgba(15, 118, 110, 0.08);
  line-height: 1.4;
}

.thinking-step:last-child {
  border-bottom: none;
}

.thinking-stage-label {
  display: inline-block;
  font-size: 10px;
  color: #fff;
  padding: 1px 5px;
  border-radius: 3px;
  margin-right: 4px;
  vertical-align: middle;
  line-height: 1.5;
}

.thinking-step-content {
  color: #888;
  font-size: 12px;
  vertical-align: middle;
}

.thinking-details {
  margin-top: 3px;
  padding: 4px 6px;
  background-color: rgba(255, 255, 255, 0.72);
  border-radius: 3px;
  font-size: 11px;
  color: var(--text-color-light);
}

.thinking-detail-text {
  color: #999;
  font-size: 11px;
  line-height: 1.4;
}

.thinking-detail-kv {
  display: flex;
  gap: 4px;
  line-height: 1.5;
}

.thinking-detail-key {
  color: #aaa;
  white-space: nowrap;
}

.thinking-detail-val {
  color: #999;
  word-break: break-all;
}

.thinking-doc-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1px 0;
  line-height: 1.5;
}

.thinking-doc-source {
  color: #999;
  font-size: 11px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thinking-doc-score {
  color: #888;
  font-size: 11px;
  margin-left: 8px;
  white-space: nowrap;
}

.thinking-doc-more {
  color: #bbb;
  font-size: 11px;
  margin-top: 2px;
}

.thinking-score-item {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 1px 0;
  line-height: 1.5;
  font-size: 11px;
  color: #999;
}

.thinking-score-preview {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #aaa;
}
</style>
