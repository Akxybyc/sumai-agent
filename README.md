# 速卖通全托管智能上品 Agent — 骨架（Mock 版）

对话式完成 **1688 选品 → 生成提报内容 → 审核 → RPA 提报（全托管「发布商品」）→ 批量维护 SKU 编码**。
当前外部接口为 mock，界面与任务流完整，接入真实 RPA 时只替换工具层实现。

## 启动

双击 `start.bat`，或：

```powershell
cd D:\WorkBuddy\sumai_agent\server
..\.venv\Scripts\python.exe -m uvicorn main:app --port 8000
```

浏览器打开 http://127.0.0.1:8000

## 演示路径

1. 对话框输入「找厨房用品最近卖得好的新品」→ 出现 6 个候选商品；
2. 勾选 → 「确认选品，生成提报内容」→ 进度条走完生成草稿；
3. 审核台改标题 / 供货价 / 库存 / 重量 / SKU 编码 → 确认 → 提报；
4. 任务看板看进度与结果；设置页可配模型 Key、1688 Key、驱动模式（全托管默认 RPA）。

## 目录

```
server/
  main.py              FastAPI 接口
  agent/orchestrator.py 意图识别、任务编排、草稿生成（后续换 LangGraph）
  content.py           按提示词 7 项清单产出结构化内容（Mock 版大模型）
  llm.py               算力适配层：10 家供应商、备用切换、用量计费
  tools/base.py        工具接口（api / rpa 双驱动预留）
  mock/data.py         1688 商品与类目属性 mock
  prompts/             需求方提示词模板（v1 已接入）
web/                   前端（原生 HTML/CSS/JS，无构建）
data/settings.json     本机设置持久化
```

## 已知边界（刻意的）

- 数据在内存，重启服务后清空；正式版接 SQLite。
- 大模型、1688、速卖通 RPA 均为 mock，不产生真实请求。
- 初始化会读 `data/settings.json`，只保存店铺/模型/驱动配置。
