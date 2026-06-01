# AI 提示词优化助手

基于 Flask + SQLite + DeepSeek（OpenAI 兼容 API）的 Web 应用，将用户输入的原始提示词优化为更清晰、结构化的高质量提示词。包含单元测试、接口测试、性能测试（Locust）与 Selenium 自动化测试。

## 项目结构

```text
project/
├── backend/
│   ├── app.py              # Flask 主应用与 API 路由
│   ├── config.py           # 配置（环境变量）
│   ├── models.py           # User、PolishRecord 模型
│   └── services/
│       ├── ai_client.py    # AI 提示词优化调用与 Mock
│       ├── pagination.py   # 历史分页
│       └── rating.py       # 评分校验与均值
├── frontend/
│   ├── index.html
│   └── static/
│       ├── style.css
│       └── script.js
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── api/
│   ├── auto/
│   └── performance/
├── requirements.txt
└── README.md
```

## 环境要求

- Python 3.9+
- Chrome 浏览器（Selenium 测试需要）

## 安装

```bash
cd project
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

## 配置

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek 代理 API Key | 空 |
| `DEEPSEEK_BASE_URL` | 代理地址 | 空 |
| `DEEPSEEK_MODEL` | 模型名 | `deepseek-v4-pro` |
| `MOCK_AI` | 设为 `1` 时使用 Mock，不调用真实 AI | `0` |
| `MOCK_AI_DELAY` | Mock 模式下模拟延迟（秒） | `0` |
| `DATABASE_URI` | 数据库连接（一般不用改） | `project/instance/grammar_assistant.db` |

**开发/测试建议**：始终设置 `MOCK_AI=1`，避免消耗 API 额度。

```bash
# Windows PowerShell
$env:MOCK_AI="1"
```

## 启动开发服务器

```bash
cd project
$env:MOCK_AI="1"   # PowerShell 测试用
python backend/app.py
```

浏览器访问：<http://127.0.0.1:5000>

启动时终端会显示**数据库文件路径**和已有用户数、优化记录数。

**数据存储说明**：
- 用户账号保存在 `project/instance/grammar_assistant.db` 的 `user` 表
- 提示词优化记录保存在 `polish_record` 表（仅优化**成功**后写入）

使用真实 AI 时，在 `.env` 中配置 `DEEPSEEK_API_KEY` 并设置 `MOCK_AI=0`。

## 运行测试

```bash
$env:MOCK_AI="1"
pytest tests/unit tests/api -v
pytest tests/unit tests/api --cov=backend --cov-report=html
pytest tests/auto/test_selenium_flow.py -v
```

## API 一览

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/register` | POST | 注册 |
| `/api/login` | POST | 登录 |
| `/api/logout` | POST | 登出 |
| `/api/polish` | POST | 提示词优化（路由名保留，功能为优化提示词） |
| `/api/history` | GET | 分页历史 |
| `/api/record/<id>` | DELETE | 删除记录 |
| `/api/record/<id>/rate` | POST | 对优化效果评分 1-5 |

## 功能说明

1. **注册/登录**：Session 认证，支持忘记密码
2. **提示词优化**：输入原始提示词，AI 输出优化后的结构化提示词
3. **优化对话**：微信风格对话界面，可上滑查看历史
4. **历史记录**：分页查看、删除
5. **评分反馈**：对优化效果打 1-5 星

## 使用示例

| 原始提示词 | 优化方向 |
|-----------|----------|
| 写一篇关于气候变化的文章 | 明确角色、字数、结构、风格 |
| 给我一些营销点子 | 补充行业、目标用户、输出格式 |
| 帮我写 Python 爬虫 | 明确目标网站、数据字段、技术约束 |
