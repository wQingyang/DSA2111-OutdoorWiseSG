<<<<<<< HEAD
# OutdoorWise — existing demo upgraded to v2

原前端、Marina Bay / Woodlands Waterfront、GeoJSON 与降雨流程均保留。本次在同一个项目内增加 8 个官方 API collector、10 个环境指标、CSV 数据层与共享读取服务。默认数据模式为 **live**，agent 默认仍为规则演示。既有推荐只根据距离/降雨基线排序，尚未加入综合环境风险模型。

## Run

Python 3.11+，推荐 Linux / macOS；Windows 请用 WSL 或 Docker（CSV 跨进程锁使用 fcntl）。

```bash
cd outdoorwise-demo
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
export OUTDOORWISE_DATA_MODE=live
python -m outdoorwise.cli collect
python -m outdoorwise.cli run --horizon 30
python -m uvicorn outdoorwise.api.app:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000 ，原路线卡片会展示每个指标的值、来源、距离、观测/抓取时间，以及 fresh/stale/missing 和 live/cache/demo/unavailable。鼠标悬停显示匹配方法、修订时间和原因。`/docs` 为接口文档。前端刷新按钮重新采集全部来源，单来源失败返回 partial，并继续其他来源。

包内附本次真实采集的 CSV。时间会自然变旧；重新 collect 可刷新。live 启动不偷偷联网或切换 mock，直接读取已存真实数据。

```bash
python -m outdoorwise.cli collect --due   # 只采集达到配置间隔的来源
python -m pytest -q
OUTDOORWISE_DATA_MODE=demo python -m outdoorwise.cli collect
OUTDOORWISE_DATA_MODE=demo python -m uvicorn outdoorwise.api.app:app
```

`--due` 是可重复调用的任务入口，本版不启动后台调度器；由团队自己的 scheduler 调用。强制 collect 忽略间隔。demo 和 live 观测按 source_kind 隔离；最新路线视图代表最近运行的模式，服务读取时始终按所选模式重算。

## Where everything lives

| 内容 | 文件 |
|---|---|
| API 地址、间隔、超时、重试、stale 阈值 | config/environment.toml |
| 每个来源的独立 collector | outdoorwise/collectors/ |
| 字段、单位、统计窗口与类型校验 | outdoorwise/contracts/environment.py |
| 模块 Protocol | outdoorwise/contracts/ports.py |
| 单 writer、去重、修订、原子写入 | outdoorwise/storage/repository.py |
| 各指标独立匹配与共享读取接口 | outdoorwise/services/route_environment.py |
| 采集与模块编排 | outdoorwise/pipeline/runner.py |
| 唯一模块组装入口 | outdoorwise/bootstrap.py |
| 原前端（已增加环境表） | frontend/ |
| 原路线 catalog / geometry | data/catalog/ |
| 真实观测、映射、汇总、采集日志 | data/runtime/*.csv |
| 组员填充模板 | templates/module_template.py |

详细说明：[API_CONFIG](docs/API_CONFIG.md)、[CSV_SCHEMA](docs/CSV_SCHEMA.md)、[ARCHITECTURE](docs/ARCHITECTURE.md)、[TEAM_HANDOFF](docs/TEAM_HANDOFF.md)、[VERIFICATION](docs/VERIFICATION.md)。

## Shared interface

```python
from datetime import datetime, timezone
from outdoorwise.bootstrap import build_pipeline
from outdoorwise.config import Settings
pipeline = build_pipeline(Settings.from_env())
environment = pipeline.get_route_environment('marina_bay', datetime.now(timezone.utc))
```

HTTP：`GET /api/routes/marina_bay/environment?as_of=2026-10-05T03:40:00Z`。时间必须带时区。返回 typed RouteEnvironment，指标缺失值为 None/null。队友禁止直接读写 CSV 或各自请求环境 API。

## Prediction / AI

当前观测不是未来 30/60 分钟预测。live 的预测与风险模块返回 unavailable；demo 预测有 is_mock=true。预测输出在 predictions_latest.json，绝不进入环境观测长表。

真实 agent 配置仍沿用原 demo 的 chat-completions 工具循环：

```bash
export OUTDOORWISE_AGENT_MODE=llm
export LLM_BASE_URL=https://api.openai.com/v1
export LLM_MODEL=your-provider-model
export LLM_API_KEY=your-key
```

没有供应商 key，因此真实 LLM 调用本次未验证。默认 agent=demo 的固定工具链已验证，结构化环境与风险输出进入解释工具。`get_route_environment` 工具接受 route_id 与可选 as_of。不要把规则演示当成真实 LLM 接入。
=======
# DSA2111-OutdoorWiseSG
>>>>>>> 6bffe0e121fc91ff2e7c914b3754611cdb475381
