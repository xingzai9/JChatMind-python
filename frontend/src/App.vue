<template>
  <div style="display:flex;height:100vh;overflow:hidden;">

    <!-- ── 左侧导航侧边栏 ───────────────────── -->
    <aside style="width:220px;min-width:220px;display:flex;flex-direction:column;background:#fff;border-right:1px solid #f0f0f5;padding:20px 12px;">

      <!-- Logo -->
      <div style="display:flex;align-items:center;gap:10px;padding:8px 8px 20px;">
        <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;">
          🤖
        </div>
        <div>
          <div style="font-weight:700;font-size:14px;color:#1a1a2e;">JChatMind</div>
          <div style="font-size:11px;color:#9ca3af;">AI Agent 平台</div>
        </div>
      </div>

      <!-- 导航菜单 -->
      <nav style="flex:1;display:flex;flex-direction:column;gap:4px;">
        <router-link to="/" :class="['nav-link', $route.name === 'home' ? 'active' : '']">
          <span style="font-size:16px;">🏠</span> Agent 管理
        </router-link>
        <router-link to="/chat" :class="['nav-link', $route.name === 'chat' ? 'active' : '']">
          <span style="font-size:16px;">💬</span> 对话交互
        </router-link>
        <router-link to="/knowledge" :class="['nav-link', $route.name === 'knowledge' ? 'active' : '']">
          <span style="font-size:16px;">📚</span> 知识库
        </router-link>
      </nav>

      <!-- 底部版本 -->
      <div style="font-size:11px;color:#c4c4d0;padding:8px;">v1.0 · FastAPI + Vue 3</div>
    </aside>

    <!-- ── 主内容区 ─────────────────────────── -->
    <main style="flex:1;overflow:hidden;display:flex;flex-direction:column;">
      <router-view></router-view>
    </main>

  </div>
</template>

<script setup>
</script>
