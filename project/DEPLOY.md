# 部署到 Render（方案 B）

本文说明如何将 **AI 提示词优化助手** 部署到 [Render](https://render.com) 免费 Web 服务，获得固定公网地址。

> **说明：** Railway 也可使用，见文末「Railway 简要步骤」。Render 与 Railway 均使用 `requirements-prod.txt` + `wsgi.py` + `Procfile`。

---

## 一、部署前准备

1. **代码推送到 GitHub**（Render 从 Git 拉取代码）
   - 仓库根目录为 `实训4`，应用在子目录 `project/`
2. **准备 DeepSeek API Key**（或你的 OpenAI 兼容代理 Key）
3. **生成随机 SECRET_KEY**（可用 Python：`python -c "import secrets; print(secrets.token_hex(32))"`）

---

## 二、Render 创建 Web Service

1. 登录 [https://dashboard.render.com](https://dashboard.render.com)
2. 点击 **New +** → **Web Service**
3. 连接你的 GitHub 仓库
4. 填写配置：

| 配置项 | 填写内容 |
|--------|----------|
| **Name** | `prompt-optimizer`（任意英文名） |
| **Region** | 选离你较近的（如 Singapore） |
| **Branch** | `main` |
| **Root Directory** | `project` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements-prod.txt` |
| **Start Command** | `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120` |
| **Instance Type** | Free |

5. 展开 **Environment Variables**，添加：

| Key | Value | 必填 |
|-----|-------|------|
| `FLASK_DEBUG` | `0` | 是 |
| `MOCK_AI` | `0` | 是 |
| `SECRET_KEY` | 随机长字符串 | 是 |
| `DEEPSEEK_API_KEY` | 你的 API Key | 是 |
| `DEEPSEEK_BASE_URL` | 如 `https://llm.chudian.site/v1` | 按你的代理填写 |
| `DEEPSEEK_MODEL` | 如 `deepseek-v4-pro` | 是 |
| `SESSION_COOKIE_SECURE` | `1` | 是 |
| `ENABLE_DB_BACKUP` | `0` | 建议（免费实例磁盘非持久） |

6. 点击 **Create Web Service**，等待 Build 和 Deploy 完成（约 3～8 分钟）

7. 部署成功后，访问：`https://你的服务名.onrender.com`

---

## 三、使用 Blueprint 一键部署（可选）

仓库已包含 `project/render.yaml`：

1. Render Dashboard → **New +** → **Blueprint**
2. 选择本仓库
3. 手动补充 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL` 等密钥
4. 确认 `rootDir: project` 后部署

---

## 四、免费版限制（写进实训报告）

| 项目 | 说明 |
|------|------|
| **冷启动** | 15 分钟无访问会休眠，首次打开需等待 30～60 秒 |
| **SQLite 数据** | 免费实例磁盘不持久，**重新部署后用户/历史可能清空**；适合演示，不适合长期生产 |
| **并发** | 免费版资源有限，同时在线用户不宜过多 |
| **HTTPS** | Render 自动提供，无需自己配证书 |

---

## 五、部署后自检

1. 打开 `https://xxx.onrender.com/health`，应返回 `{"status":"ok"}`
2. 注册 → 登录 → 输入提示词优化 → 查看历史
3. 若 AI 报错，检查 `DEEPSEEK_API_KEY` 与 `DEEPSEEK_BASE_URL`

---

## 六、Railway 简要步骤

1. 登录 [https://railway.app](https://railway.app)，New Project → Deploy from GitHub
2. 设置 **Root Directory** 为 `project`
3. Railway 会自动识别 `Procfile`
4. 在 Variables 中配置与 Render 相同的环境变量
5. 生成 Domain 后即可访问

---

## 七、本地与线上命令对照

| 环境 | 启动方式 |
|------|----------|
| 本地开发 | `python backend/app.py` |
| 生产（Render/Railway） | `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120` |

---

## 八、常见问题

**Q：Build 失败 `ModuleNotFoundError: backend`？**  
A：确认 Root Directory 设为 `project`，且 Start Command 使用 `wsgi:app`。

**Q：登录后刷新又退出？**  
A：确认 `SECRET_KEY` 已设置且 `SESSION_COOKIE_SECURE=1`（HTTPS 环境）。

**Q：想持久保存数据库？**  
A：免费版建议仅作演示；正式环境可升级 Render 付费盘或改用 PostgreSQL（需额外改造）。
