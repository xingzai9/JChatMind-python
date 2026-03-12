# 实验室 Agent 管理系统 - 前端

基于 Vue 3 + Vite + Tailwind CSS + DaisyUI 构建的现代化前端界面。

## 技术栈

- **Vue 3** - 渐进式 JavaScript 框架
- **Vite** - 下一代前端构建工具
- **Vue Router** - 官方路由管理器
- **Axios** - HTTP 客户端
- **Tailwind CSS** - 原子化 CSS 框架
- **DaisyUI** - Tailwind CSS 组件库

## 功能特性

✅ Agent 管理 - 创建、查看、编辑、删除 Agent  
✅ 对话交互 - 与 Agent 进行实时对话  
✅ 会话管理 - 查看和管理历史会话  
✅ 知识库管理 - 创建知识库、上传文档  
✅ 响应式设计 - 完美适配各种屏幕尺寸  
✅ 现代化 UI - 美观、简洁、易用  

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

访问：`http://localhost:5173`

### 3. 构建生产版本

```bash
npm run build
```

## 项目结构

```
frontend/
├── src/
│   ├── api/              # API 调用封装
│   ├── components/       # 可复用组件
│   ├── views/            # 页面组件
│   ├── App.vue           # 根组件
│   ├── main.js           # 入口文件
│   └── style.css         # 全局样式
├── index.html            # HTML 模板
├── package.json          # 依赖配置
├── vite.config.js        # Vite 配置
└── tailwind.config.js    # Tailwind 配置
```

## API 配置

前端通过 Vite 代理访问后端 API：

- 开发环境：`/api` → `http://localhost:8000/api`
- 生产环境：需要配置 Nginx 反向代理

## 开发说明

1. 所有 API 调用统一封装在 `src/api/index.js`
2. 使用 Vue 3 Composition API（`<script setup>`）
3. 样式使用 Tailwind CSS 原子类
4. UI 组件基于 DaisyUI 主题系统
