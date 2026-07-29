# AIHot Runbook

本手册记录 2026-07-28 的本地验证、前端构建和生产部署方式。

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

## 全网采集周期

- 唯一周期配置是 `config/collection.yaml`，当前为 `720` 分钟（12 小时）；频道主文件和扩展目录禁止声明逐源周期。
- `channels/ai.yaml` 与 `channels/amazon.yaml` 通过 `source_catalogs` 装载已验证目录，当前启用且可采集规模分别为 340 和 325。
- 调度器可以更频繁地扫描队列，但只会为 `next_fetch_at` 已到期的信源创建任务，不等于每次扫描都会重新抓取全网。
- 生产 timer 每小时扫描一次、单轮最多处理 60 个到期任务，12 小时容量上限为 720 个任务，高于当前 665 个启用信源；已有活跃任务会在应用批量上限前排除，避免失败任务阻塞后续信源。
- Worker 租约超过 60 分钟会自动回收；同一任务连续 3 次租约过期后转为 `dead`，信源进入 4 小时退避且下一次正常抓取仍遵循全局 12 小时周期。
- 调度器计算下一次成功抓取时间时直接读取 `config/collection.yaml`。部署中的 `intel-engine seed-sources` 还会把全局周期和规范化发布者身份同步到目录内及遗留数据库信源。
- 同一事件会按独立 `publisher_key` 聚合证据；至少两个独立发布方确认同一事实后，才会标记为“已交叉验证”。每条确认事实会保存发布者和信源 ID，前端可追溯到支持方。
- DeepSeek 事件级分析作为辅助解释和置信度输入，不能自行把确定性规则未确认的事件晋级为“已交叉验证”。部署会运行 `intel-engine backfill-evidence`，为已有事件补齐规则证据。
- 部署先同步等待 `aihot-pipeline@1.service` 完成一次单任务 smoke；通过后才启用每小时触发 `aihot-pipeline@60.service` 的 timer。

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
访问入口：https://aihot.shcai.top/
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
