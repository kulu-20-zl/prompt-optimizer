# -*- coding: utf-8 -*-
"""Generate enriched test plan docx per 实训要求 Step 2 + 附件3 template."""

from pathlib import Path

from docx_helpers import LEADER, MEMBER_B, MEMBER_C, REPO_ROOT, TEAM_MEMBERS, DocBuilder

OUT_PATH = REPO_ROOT / f"{TEAM_MEMBERS}-综合测试计划.docx"


def build():
    b = DocBuilder("综合测试实践 — 测试计划", OUT_PATH)

    # ===== 三、实践总结（验收标准 / 交付物 / 体会）=====
    b.at("实践总结")
    b.heading("3.1 发布门禁与验收标准（实训要求）")
    b.para(
        "依据实训说明书及本测试计划，发布前须满足以下量化门禁。核心功能用例通过率不低于 95%，"
        "不得存在 S1 致命缺陷，S2 严重缺陷须全部关闭或经评审接受并文档化。"
    )
    b.table(
        ["验收指标", "通过标准", "验证方式"],
        [
            ("计划内用例通过率", "≥ 95%", "执行记录统计"),
            ("自动化通过率", "pytest 100% 通过", "CI / 本地回归"),
            ("后端代码覆盖率", "backend/ ≥ 70%", "pytest-cov HTML"),
            ("S1 缺陷", "= 0", "缺陷台账"),
            ("S2 缺陷", "= 0 或评审接受", "缺陷台账"),
            ("P0/P1 缺陷", "发布前全部关闭", "缺陷台账"),
            ("性能(Mock)", "/api/polish P95 < 3s；history P95 < 500ms", "Locust 报告"),
            ("性能(真实API)", "流式首 chunk < 10s（参考）", "Staging 抽样"),
        ],
    )
    b.heading("3.2 业务验收清单（UAT）")
    b.para("以下为系统测试与验收测试抽样清单，执行后勾选并归档至测试报告：")
    b.bullets([
        "□ 新用户可注册、登录并刷新页面保持登录态",
        "□ 四种优化模式（通用/写作/代码/数据）均可完成一次流式优化",
        "□ 继续优化弹窗生成新提示词（非思考过程、非直接调研答案）",
        "□ 历史可分页、删除、评分；仅能操作本人记录",
        "□ 收藏可在「我的收藏」查看并继续优化",
        "□ AI 失败时有明确提示且历史可见 failed 记录",
    ])
    b.heading("3.3 项目风险与应对")
    b.table(
        ["风险", "影响", "概率", "缓解措施"],
        [
            ("DeepSeek API 不稳定/限额", "联调阻塞", "中", "默认 MOCK_AI=1；Staging 配额与重试"),
            ("AI 输出不可控", "继续优化体验差", "中", "启发式检测+重试；人工抽样"),
            ("Selenium 依赖 Chrome", "E2E 失败", "中", "headless + WebDriverWait"),
            ("SQLite 多环境混淆", "数据丢失误判", "低", "测试统一内存库"),
            ("文本长度限制", "refine 失败", "中", "前后端分拆传参"),
            ("实训周期紧", "覆盖不足", "高", "优先 P0 路径；自动化优先 API"),
        ],
    )
    b.heading("3.4 交付物清单")
    b.table(
        ["序号", "文档/产物", "说明", "责任人"],
        [
            ("1", "测试计划", "范围、策略、进度（本文档）", LEADER),
            ("2", "测试用例集", "pytest 用例或 Excel 对照表", "全员"),
            ("3", "自动化测试报告", "pytest 结果 + cov HTML", f"{LEADER}/{MEMBER_B}"),
            ("4", "系统测试报告", "E2E、手工执行记录", "全员"),
            ("5", "性能测试简报", "Locust RPS/P95/错误率", LEADER),
            ("6", "缺陷分析报告", "Severity/模块统计", f"{LEADER}/{MEMBER_C}"),
            ("7", "测试总结报告", "验收结论与发布建议", LEADER),
            ("8", "CI 构建记录", "GitHub Actions 日志", LEADER),
        ],
    )
    b.heading("3.5 实践体会、不足与改进措施")
    b.para(
        "① 专业知识在实践中的应用：本计划将等价类划分、边界值分析、场景法、错误推测、状态迁移等"
        "黑盒用例设计技术应用于认证、优化、refine、历史、评分等模块；将单元测试、接口测试、"
        "系统测试、性能测试四层策略与 pytest、Selenium、Locust 工具链结合，形成可重复执行的回归体系。"
    )
    b.para(
        "② 总体结论：测试计划明确了 In-Scope/Out-Scope 边界、环境矩阵、自动化与手工划分及 12 天里程碑，"
        "为项目质量活动提供了可操作的路线图，符合实训说明书 Step 2 对测试计划编制的要求。"
    )
    b.para(
        "③ 不足与改进：手工与 UAT 用例需补充正式编号与执行记录；Selenium 用例可扩展至收藏与继续优化弹窗；"
        "validators、rate_limit、backup 等模块覆盖率可进一步提升；性能报告建议补充图表截图。"
    )

    # ===== 二、课程实践内容（环境/策略/用例/数据/缺陷/进度）=====
    b.at("课程实践内容")
    b.para(
        "被测系统为「AI 提示词优化助手」——基于 Flask + SQLite + DeepSeek API 的 Web 应用，"
        "实现用户认证、多模式提示词优化（含 SSE 流式）、继续优化（refine）、历史记录、评分、"
        "收藏（localStorage）及 Markdown 渲染等功能。本节按实训要求阐述测试环境、策略、用例、"
        "数据、缺陷管理与人员进度安排。"
    )

    b.heading("2.1 测试环境（操作系统 / 浏览器 / 数据库）")
    b.table(
        ["类别", "配置项", "规格/版本"],
        [
            ("硬件", "开发测试机", "CPU 4核+，内存 8GB+，磁盘 ≥ 2GB"),
            ("操作系统", "主环境", "Windows 10/11"),
            ("操作系统", "CI 环境", "Ubuntu 22.04（GitHub Actions）"),
            ("运行时", "Python", "3.13（要求 3.11+）"),
            ("框架", "Flask", "≥ 2.0"),
            ("数据库", "SQLite", "instance/grammar_assistant.db"),
            ("浏览器", "功能/E2E", "Chrome/Edge/Firefox 120+"),
            ("WebDriver", "Selenium", "Chrome + webdriver-manager 4.x"),
            ("应用地址", "本地", "http://127.0.0.1:5000"),
            ("第三方", "DeepSeek API", "DEEPSEEK_API_KEY / BASE_URL / MODEL"),
            ("Mock", "日常回归", "MOCK_AI=1 不调用真实 API"),
        ],
    )
    b.heading("2.2 环境矩阵")
    b.table(
        ["环境", "用途", "数据库", "AI 模式"],
        [
            ("DEV", "开发自测", "本地 SQLite", "Mock 或真实 Key"),
            ("TEST", "自动化执行", "sqlite:///:memory:", "Mock 为主"),
            ("STAGING", "预发布联调", "独立库+备份", "真实 API（限额）"),
        ],
    )

    b.heading("2.3 测试策略（单元 / 集成 / 系统 / 性能）")
    b.para("按实训说明书要求，测试策略覆盖四个层级，并与测试类型、工具对应如下：")
    b.table(
        ["测试层级", "覆盖范围", "本项目落点", "工具"],
        [
            ("单元测试", "纯函数、服务层、校验逻辑", "ai_client、pagination、rating、prompt_modes", "pytest"),
            ("集成/API测试", "路由+DB+Session", "auth、polish、history、rating", "pytest+Flask client"),
            ("系统测试", "端到端业务流程", "Selenium 主流程+手工探索", "Selenium 4"),
            ("性能测试", "高频接口并发", "/api/history、/api/polish", "Locust 2.x"),
            ("验收测试UAT", "业务场景与易用性", "优化、refine、收藏、历史走查", "手工清单"),
        ],
    )
    b.table(
        ["测试类型", "方法", "工具/手段"],
        [
            ("功能", "用例驱动+场景法", "pytest、手工"),
            ("接口", "契约与状态码断言", "pytest + Flask test client"),
            ("性能", "负载与并发", "Locust"),
            ("安全", "越权、限流、未授权", "pytest + 手工"),
            ("兼容性", "多浏览器冒烟", "手工 + Selenium headless"),
            ("易用性", "走查清单", "手工"),
        ],
    )
    b.heading("2.4 工具与版本汇总")
    b.table(
        ["用途", "工具", "版本"],
        [
            ("单元/API", "pytest、pytest-cov、pytest-mock", "9.x"),
            ("E2E", "Selenium、webdriver-manager", "4.x / 4.x"),
            ("性能", "Locust", "2.44.0"),
            ("缺陷跟踪", "GitHub Issues / Excel", "实训简化"),
            ("API 调试", "curl、Postman", "—"),
            ("CI", "GitHub Actions", "ubuntu-latest"),
        ],
    )
    b.heading("2.5 自动化与手工划分")
    b.table(
        ["类别", "自动化", "手工补充"],
        [
            ("单元/API回归", "✅ pytest 约63条", "边界与新需求"),
            ("CI门禁", "✅ GitHub Actions", "—"),
            ("E2E", "✅ Selenium 1条主流程", "refine弹窗、收藏、Markdown"),
            ("性能", "✅ Locust脚本", "分析报告、瓶颈定位"),
            ("AI输出质量", "❌", "抽样评审"),
            ("易用性/视觉", "❌", "走查"),
        ],
    )

    b.heading("2.6 测试用例设计")
    b.para("采用等价类划分、边界值分析、场景法、错误推测、状态迁移等技术。关键模块用例示例如下：")
    b.heading("模块A：提示词优化 POST /api/polish/stream")
    b.table(
        ["用例ID", "标题", "前置条件", "预期结果"],
        [
            ("POL-01", "合法文本流式优化", "已登录", "200，SSE有chunk，status=success"),
            ("POL-02", "空文本", "已登录", "400，文本不能为空"),
            ("POL-03", "超长文本2001字", "已登录", "400，文本过长"),
            ("POL-04", "未登录", "无Session", "401"),
            ("POL-05", "AI超时", "Mock抛超时", "503，DB记录failed"),
        ],
    )
    b.heading("模块B：继续优化 refine")
    b.table(
        ["用例ID", "标题", "步骤", "预期结果"],
        [
            ("REF-01", "正常继续优化", "polished+direction合法", "200，返回新提示词"),
            ("REF-02", "空优化方向", "direction为空", "400"),
            ("REF-03", "思考过程拦截", "模型返回推理文本", "重试或400"),
        ],
    )
    b.heading("模块C：认证与限流")
    b.table(
        ["用例ID", "标题", "步骤", "预期结果"],
        [
            ("AUTH-01", "注册成功", "合法用户名密码邮箱", "201"),
            ("AUTH-02", "登录成功", "正确凭据", "200，建立Session"),
            ("AUTH-RL-01", "连续错误登录", "超LOGIN_RATE_LIMIT", "429"),
        ],
    )
    b.heading("模块D：前端收藏（手工）")
    b.table(
        ["用例ID", "标题", "预期结果"],
        [
            ("FAV-01", "收藏后进入我的收藏", "列表展示原文/优化文，可继续优化"),
            ("FAV-02", "取消收藏", "列表移除，按钮恢复收藏"),
        ],
    )

    b.heading("2.7 测试数据与隔离策略")
    b.table(
        ["数据类型", "准备方式"],
        [
            ("用户账号", "pytest fixture 动态创建；Locust 用 perfuser_*"),
            ("优化记录", "API调用或db_session插入PolishRecord"),
            ("AI响应", "MOCK_AI=1 或 mock_openai 固定文本"),
            ("继续优化", "预制polished长文本+短direction样本"),
        ],
    )
    b.bullets([
        "自动化：测试库统一使用 sqlite:///:memory:，每用例/模块隔离，防止污染生产库。",
        "手工：使用专用测试账号，不与演示/生产账号混用。",
        "性能：Locust 虚拟用户独立注册，用户名加随机后缀。",
        "敏感数据：DEEPSEEK_API_KEY 仅存 .env；报告摘录打码 sk-****；优化内容截断至200字。",
    ])

    b.heading("2.8 缺陷管理流程与回归策略")
    b.para("缺陷严重级别与优先级定义：")
    b.table(
        ["Severity", "定义", "示例"],
        [
            ("S1致命", "系统不可用或数据丢失", "无法登录、数据误删"),
            ("S2严重", "核心功能不可用", "流式中断、refine始终失败"),
            ("S3一般", "功能受损可绕行", "收藏迁移提示不友好"),
            ("S4轻微", "体验/文案", "Toast文案、对齐"),
        ],
    )
    b.table(
        ["Priority", "说明"],
        [("P0", "发布阻塞，24h内修复"), ("P1", "当前迭代必须修复"), ("P2", "可延后"), ("P3", "建议改进")],
    )
    b.para(
        "缺陷生命周期：新建 → 确认 → 指派开发 → 修复 → 待验证 → 关闭（或延期/拒绝需说明原因）。"
        "每条缺陷至少包含：标题、环境、复现步骤、实际/预期、截图/日志、关联用例ID、Severity、Priority。"
    )
    b.para(
        "回归策略：P0/P1 缺陷修复后须执行关联用例 + 全量 pytest tests/unit tests/api；"
        "S2 及以上缺陷修复后须追加 Selenium E2E 主流程回归；发布前执行全量自动化 + UAT 清单走查。"
    )

    b.heading("2.9 测试进度与人员分工")
    b.table(
        ["阶段", "时间", "活动", "产出"],
        [
            ("M1 计划与评审", "第1天", "评审测试计划、确认范围", "计划定稿"),
            ("M2 用例设计", "第2-3天", "编写用例、准备数据", "用例集"),
            ("M3 单元/API", "第4-6天", "pytest、修CI", "自动化报告、覆盖率"),
            ("M4 系统/E2E", "第7-8天", "Selenium+手工", "E2E记录"),
            ("M5 性能安全", "第9天", "Locust、安全抽查", "性能简报"),
            ("M6 回归UAT", "第10-11天", "全量回归、验收走查", "回归清单"),
            ("M7 总结", "第12天", "测试报告、缺陷分析", "测试总结报告"),
        ],
    )
    b.table(
        ["成员", "原定职责", "实际完成情况"],
        [
            (f"{LEADER}（组长）", "项目统筹、后端、单元/性能/Selenium、测试计划", "后端全部模块、24条单元测试、E2E、Locust、计划牵头撰写"),
            (MEMBER_B, "前端开发、API接口测试", "index.html/script.js等前端页面、tests/api/下39条API测试"),
            (MEMBER_C, "测试文档、缺陷汇总、答辩材料", "参与讨论，测试汇报等文档由曾露补位完成"),
        ],
    )
    b.heading("2.10 测试资产目录对照")
    b.table(
        ["目录", "内容", "用例规模", "建议"],
        [
            ("tests/unit/", "ai_client、pagination、rating", "24条", "补充validators、rate_limit"),
            ("tests/api/", "auth、polish、history、rating", "39条", "补充refine非法参数"),
            ("tests/auto/", "Selenium主流程", "1条", "扩展收藏、refine弹窗"),
            ("tests/performance/", "Locust历史+优化", "2场景", "可增加stream压测"),
        ],
    )

    # ===== 一、课程实践目的（测试范围与目标）=====
    b.at("课程实践目的")
    b.para(
        "「综合测试实践」是软件测试方向核心实训课程。本测试计划针对三人小组自研项目"
        "「AI 提示词优化助手」编制，旨在明确测试范围与目标、测试策略、测试环境、"
        "工具版本、人员分工与进度、缺陷管理流程及发布门禁，为后续测试执行与报告撰写提供依据。"
        "编制依据：实训说明书04《综合测试实践》Step 2「制定测试计划」。"
    )
    b.heading("1.1 功能测试范围")
    b.table(
        ["模块", "覆盖功能点"],
        [
            ("用户认证", "注册、登录、登出、忘记密码、/api/me会话恢复"),
            ("提示词优化", "四种模式、同步/流式SSE、文本长度校验"),
            ("继续优化", "refine接口、方向合并、思考过程拦截与重试"),
            ("历史记录", "分页查询、删除、仅本人可见"),
            ("评分", "1-5星评价、覆盖更新、权限校验"),
            ("前端交互", "对话式UI、Markdown、对比视图、收藏、refine弹窗"),
            ("数据运维", "SQLite持久化、启动备份、failed状态、登录限流"),
        ],
    )
    b.heading("1.2 非功能测试范围")
    b.table(
        ["类型", "关注点"],
        [
            ("性能", "优化响应时间、SSE首包、历史分页、Locust并发"),
            ("安全", "未登录拦截、越权删除/评分、登录限流、Session"),
            ("兼容性", "Chrome/Edge/Firefox；分辨率1280×720+"),
            ("可靠性", "AI超时异常记录、DB路径固定、重启数据不丢"),
            ("易用性", "操作流程、Toast错误提示、空状态展示"),
        ],
    )
    b.heading("1.3 不在测试范围")
    b.bullets([
        "第三方 AI 模型内容质量的主观评审（仅测接口契约与异常处理）",
        "生产级邮件验证码找回密码（实训简化版）",
        "收藏云端同步（当前仅 localStorage）",
        "多租户、水平扩展与 K8s 部署",
    ])
    b.heading("1.4 核心测试目标")
    b.bullets([
        "验证核心业务路径（注册→登录→优化→历史/评分→继续优化）可稳定完成",
        "接口与前端行为符合 API 约定，异常场景有明确错误码与提示",
        "自动化回归满足 CI 门禁（单元+API 100%通过，覆盖率≥70%）",
        "识别 P0/P1 缺陷并在发布前清零或制定规避方案",
    ])
    b.heading("1.5 文档属性")
    b.table(
        ["属性", "内容"],
        [
            ("文档版本", "V1.0"),
            ("项目名称", "AI 提示词优化助手"),
            ("项目版本", "实训版（Flask 单体 Web）"),
            ("技术栈", "Flask 2.x、SQLite、DeepSeek API、HTML/JS"),
            ("编写角色", f"测试工程师（{LEADER}，组长）"),
            ("编写日期", "2026年6月"),
        ],
    )

    b.save()


if __name__ == "__main__":
    build()
