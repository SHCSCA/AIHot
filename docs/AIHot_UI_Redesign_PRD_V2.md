# AI 热点情报平台 - PC 端视觉与交互重构 PRD V2.0（深化版）

**文档版本:** V2.0
**设计原则:** PC 优先、性能拉满、沉浸体验、极客美学
**目标:** 将“数据表格型”前台彻底升级为沉浸式数字情报终端，支持高度交互的实时情报浏览与分析。

---

## 1. 全局设计规范 (Global Design System)

### 1.1 材质与空间感 (Material & Space)
- **毛玻璃拟物化 (Glassmorphism)**
  - 浮层透明度：0.72~0.85
  - 高斯模糊值：blur(24px)，移动端可适度降低至 blur(16px)
  - 底色建议使用动态渐变 + 细微噪点纹理（Noise Texture）
- **无边框与弥散阴影 (Borderless & Diffuse Shadow)**
  - 卡片阴影：0 2px 10px rgba(0,0,0,0.08) + 0 4px 20px rgba(0,0,0,0.06)
  - 高亮或交互状态阴影增强至 0 6px 30px rgba(brand-color,0.25)
- **光效反馈 (Glow Effects)**
  - 鼠标悬停 glow 强度：20~25px 扩散，颜色渐变沿品牌色谱
  - 点击状态：0.95 缩放 + glow 瞬时增强 1.2x

### 1.2 动态主题模式 (Dynamic Themes)
- **日间模式 (Aurora White)**
  - 背景色：#FDFDFD + 微渐变
  - 标签色：高饱和荧光紫、青色
- **夜间模式 (Cyber Deep)**
  - 背景色：#0B0F1D 渐变深海蓝到紫罗兰
  - 高亮元素：发光材质 + 外发光 0 0 8px rgba(brand-color,0.5)

### 1.3 排版体系 (Typography)
- **流体字号 (Fluid Typography)**
  - clamp(14px, 1.2vw, 20px) 等
- **等宽数字字体 (Tabular Numerals)**
  - JetBrains Mono / Fira Code，font-variant-numeric: tabular-nums
- **行高与字重**
  - 摘要内容行高：1.8，字重 Regular
  - 标题字重：ExtraBold
- **响应式间距**
  - 基于 8px 栅格系统
  - 边距、间距统一使用 spacing tokens：8/16/24/32/48

---

## 2. 核心界面重构需求 (Core UI Redesign)

### 2.1 全局导航与检索
- **Cmd+K 控制台模式**
  - 聚光灯式搜索面板，带高斯模糊背景 + 场景压暗
  - 搜索结果分区：快速跳转 / 热门情报 / 历史搜索
  - 键盘操作完整覆盖：上下选择、回车进入、Esc 退出
  - 搜索输入框光标：闪烁 1s 循环
  - 动效优化：防抖实时搜索，延迟 < 50ms

### 2.2 英雄区 (Hero Section)
- **Bento Box 聚合仪表盘**
  - 主模块 (2x2 span)：今日热点，动态波浪 SVG 背景
  - 数据模块 1：平滑贝塞尔折线图，鼠标悬停 Tooltip + 动画探照灯
  - 数据模块 2：翻页时钟风格数字滚动
  - 卡片悬停 Tilt 动效：鼠标移动 3D 倾斜 ±10°

### 2.3 过滤器与分类
- **丝滑胶囊按钮**
  - 分类切换弹性动效 (Spring Physics)
  - 胶囊高度：36px，圆角 18px
  - 激活滑块颜色：品牌主色 + 透明渐变
- **Sticky 吸顶过滤舱**
  - 向下滚动时自动吸附，背景深度模糊
  - 滑动交互平滑过渡 0.3s

### 2.4 情报信息流 (Event Feed)
- **磁贴瀑布布局**
  - 自动根据容器宽度分 2~3 列
  - 高分情报卡片宽度占两列，Score > 85
- **卡片结构**
  - 左上角：极简时间戳
  - 右上角：精选分颜色编码
  - 底部标签：半透明毛玻璃材质
- **FLIP 动效**
  - 查看详情展开，推开周围卡片
  - 动画参数：duration 0.45s，ease: cubic-bezier(.4,0,.2,1)
  - 避免闪烁，流畅膨胀

### 2.5 日报阅读区 (Daily Digest)
- **沉浸式 Zen Mode**
  - 最大宽度 760px，左右侧边栏淡出
  - 渐进式显现：fade-up 20px，duration 0.5s
  - 打字机模式可选：按行或按字母逐步呈现

---

## 3. 全局动效与微交互 (Micro-interactions)

| 动效名称 | 参数与说明 |
|----------|------------|
| 探照灯 Hover 光源 | 径向渐变，半径 120px，鼠标位置跟随 |
| 入场骨架扫描 | Shimmer gradient，速度 1.2s 循环 |
| 按钮物理回弹 | Scale 0.95，阻尼曲线 spring(300,20) |
| 共享元素转场 | Duration 0.45s，ease-in-out，平滑位置补间 |

---

## 4. 技术实现约束与建议
- **CSS 与样式管理**
  - Tailwind CSS 原子化管理 spacing、color、font-size、z-index
- **动画库依赖**
  - Framer Motion：FLIP、弹簧物理、共享元素
- **React 组件化建议**
  - BentoBox、EventCard、FilterCapsule、DailyDigest 单独组件化
  - 动效参数可通过 props 传递，实现全局统一管理

---

## 5. 样式布局与排版
- **栅格系统**
  - 12 列响应式网格，最大宽度 1440px
  - gutter 间距 24px
- **整体布局**
  - Header 固定高度 80px，导航 + 搜索栏
  - Hero 区高度 400px，Bento Box 横向铺满
  - 主内容区 Event Feed 自适应列数
  - Footer 高度 60px，简洁信息
- **间距规范**
  - 内边距：16px~32px
  - 卡片间距：16px~24px
  - Typography margin/padding 使用 spacing tokens

---

## 6. 额外深化点
1. **数据刷新动效**：每条情报或折线图更新时，采用数字滚动 + 波浪流动效果
2. **可访问性**：高对比色模式、键盘导航完整覆盖、ARIA 标签完善
3. **性能优化**：虚拟化列表 + lazy load 卡片，避免渲染过多 DOM
