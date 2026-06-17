# AIHot Runbook

本手册记录 2026-06-17 的本地验证、前端构建和生产部署方式。

## 本地后端

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m uvicorn intel_engine.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

## 本地前端

```powershell
cd web
npm install
npm run dev
```

默认入口：

```text
http://127.0.0.1:5173/
http://127.0.0.1:5173/admin
```

## 验证命令

前端：

```powershell
cd web
npm test -- --run
npm run build
```

后端冒烟：

```powershell
.\.venv\Scripts\python -m pytest tests/test_api.py tests/test_auth.py tests/test_publisher.py tests/test_daily.py -q
```

发布前全量：

```powershell
.\.venv\Scripts\python -m pytest -q
```

## 生产部署

部署脚本：

```powershell
.\scripts\deploy-aihot.ps1 -KeyPath <private-key-path>
```

可选环境变量：

```powershell
$env:AIHOT_DEPLOY_KEY="<private-key-path>"
.\scripts\deploy-aihot.ps1
```

脚本流程：

```text
1. 校验当前分支。
2. 执行 web 前端 build。
3. 将当前 Git commit 打包成 bundle。
4. 上传到服务器。
5. 在服务器项目目录 fetch bundle 并 reset 到该 commit。
6. 安装 Python 包。
7. 执行 Alembic migration。
8. seed sources。
9. 重启 aihot-web.service。
10. 轮询 /health。
```

生产信息：

```text
访问入口：http://aihot.shcai.top/
服务器项目目录：/data/wwwroot/AIHot
服务健康检查：http://127.0.0.1:8003/health
```

安全要求：

- 不把 SSH 私钥、数据库密码、DeepSeek key 写入仓库。
- 部署前确认 `git status --short` 中只有预期改动。
- 生产部署脚本会在服务器保存 reset 前的 diff、status 和 untracked 清单到 `/data/wwwroot/AIHot-deploy-backups/`。

## 前端验收重点

- Reader Mode：`/`、`/selected`、`/all`、`/daily`、`/rss`、`/sources`、`/feedback`。
- Ops Mode：`/admin` 后的 Dashboard、Sources、Jobs、Health、Quality、Events Review、Daily Digests、Feedback、Admin Access。
- Lab Mode：Strategies、Evaluations。
- 深浅色主题均可读。
- 移动端无全局横向滚动，底部导航不遮挡主要内容。
- Cmd+K 可打开、搜索、键盘选择、Esc 关闭。
- `prefers-reduced-motion` 下内容完整可见。
