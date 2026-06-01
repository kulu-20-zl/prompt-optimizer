# AI 提示词优化助手

基于 Flask + SQLite + DeepSeek（OpenAI 兼容 API）的 Web 应用，将用户输入的原始提示词优化为更清晰、结构化的高质量提示词。包含单元测试、接口测试、性能测试（Locust）与 Selenium 自动化测试。

## 主要特性

- **多模式优化**：通用 / 写作 / 代码 / 数据分析
- **流式输出**：SSE 逐字显示优化结果
- **微信式对话**：即时显示用户消息、对比视图、继续优化、收藏
- **失败也记录**：AI 异常时写入 `failed` 状态，便于排查
- **自动备份**：启动时备份 SQLite 到 `instance/backups/`
- **登录限流**：防止暴力尝试密码
- **Session 持久化**：刷新页面自动恢复登录态（`/api/me`）

## 项目结构

```text
project/
├── backend/
│   ├── app.py              # Flask 入口
│   ├── config.py           # 配置
│   ├── models.py           # User、PolishRecord
│   ├── routes/             # Blueprint 路由
│   │   ├── auth.py
│   │   ├── polish.py
│   │   └── history.py
│   ├── services/
│   │   ├── ai_client.py    # AI 调用 + 流式
│   │   ├── prompt_modes.py   # 优化模式
│   │   ├── backup.py         # 数据库备份
│   │   └── ...
│   └── utils/
├── frontend/
├── tests/
└── requirements.txt
```

## 安装与启动

```bash
cd project
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env         # 填入 DEEPSEEK_API_KEY
python backend/app.py
```

访问：<http://127.0.0.1:5000>

## 配置

| 环境变量 | 说明 | 默认 |
|----------|------|------|
| `DEEPSEEK_API_KEY` | API Key | 空 |
| `DEEPSEEK_BASE_URL` | 代理地址 | 空 |
| `DEEPSEEK_MODEL` | 模型名 | `deepseek-v4-pro` |
| `MOCK_AI` | `1` 时使用 Mock | `0` |
| `SECRET_KEY` | Session 密钥 | 开发默认值 |
| `FLASK_DEBUG` | `1` 开 debug | `1` |
| `LOGIN_RATE_LIMIT` | 登录限流次数 | `5` |
| `ENABLE_DB_BACKUP` | 启动时备份 | `1` |

## 数据存储

文件：`project/instance/grammar_assistant.db`

| 表 | 说明 |
|----|------|
| `user` | 用户账号 |
| `polish_record` | 优化记录（含 `status`、`mode`、`error_message`） |

备份目录：`project/instance/backups/`

**Navicat 提示**：连接上述 `.db` 文件后按 F5 刷新；最底部 NULL 行是新增空行，不是数据。

## API

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/me` | GET | 当前登录状态 |
| `/api/modes` | GET | 优化模式列表 |
| `/api/polish` | POST | 同步优化 |
| `/api/polish/stream` | POST | 流式优化（SSE） |
| `/api/register` | POST | 注册 |
| `/api/login` | POST | 登录 |
| `/api/history` | GET | 分页历史 |

## 测试

```bash
$env:MOCK_AI="1"
pytest tests/unit tests/api -v
pytest tests/unit tests/api --cov=backend --cov-report=html
```

CI：推送至 `main` 分支时 GitHub Actions 自动跑测试（见 `.github/workflows/test.yml`）。

## 生产部署建议

- 设置 `FLASK_DEBUG=0`
- 修改 `SECRET_KEY` 为随机长字符串
- 使用 gunicorn 等 WSGI 服务器
- 忘记密码功能应增加邮箱验证码（当前为实训简化版）
