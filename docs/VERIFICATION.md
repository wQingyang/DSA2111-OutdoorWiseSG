# Actual verification — 2026-10-05

在原项目运行一次默认 live `python -m outdoorwise.cli collect`，2026-10-05 03:38:16–03:39:52 UTC（新加坡 11:38–11:39）。8 来源全部成功、各 1 次请求，实际新增 **234 条 live 观测**，没有 mock 回退。原始计数和时间见 verification.json / data/runtime/ingestion_runs.csv。

| 来源 | 收到 / 新增 |
|---|---:|
| rainfall | 89 |
| wind speed | 17 |
| wind direction | 17 |
| temperature | 18 |
| humidity | 18 |
| PM2.5 | 5 |
| PSI + PM10 | 10 |
| WBGT + heat stress | 60 |

两路线共 20 条最新指标汇总、20 条来源映射，10 指标均有真实观测。完整 HTTP run 见 example_run.json。本次来源如下：

| 指标 | Marina Bay | Woodlands Waterfront |
|---|---|---|
| 降雨 | S119 | S104 |
| 风速 / 风向 | S108 | S104 |
| 温度 / 湿度 | S111 | S104 |
| PM2.5 / PSI / PM10 | south | north |
| WBGT / heat stress | S144 (Hong Lim Park) | S125 |

## Tests and frontend

`python -m pytest -q`：12 passed。覆盖真实录制响应 parser、单位变化拒收、去重、旧值修订、带时区同瞬间去重、历史 as_of、missing/stale、失败继续采集与 live 缓存、retry、单 writer/日志恢复、原降雨迁移、模块边界、API、agent 工具链。LLM 工具循环用测试响应验证，并非真实供应商请求。

原 frontend/app.js 在 jsdom DOM 中实际请求本地 FastAPI HTTP 服务，验证 2 卡片、20 真实指标行、0 missing、2 原路线备用 SVG。运行入口：

```bash
python -m uvicorn outdoorwise.api.app:app --port 8765
# 另一个终端，在项目根目录；Node 20+，仅验证需要 jsdom
npm install --prefix /tmp/outdoorwise-ui-check jsdom
NODE_PATH=/tmp/outdoorwise-ui-check/node_modules BASE_URL=http://127.0.0.1:8765 node tests/frontend_smoke.cjs
```

未完成完整浏览器截图/Leaflet 在线地图视觉验证：浏览器下载返回损坏压缩包，无法安装。DOM 与 HTTP 检查成功，不能把它描述成完整浏览器端到端视觉测试。Docker 构建未实际运行；Dockerfile 已补上新增 config 目录。外部 LLM 未提供 key，本次未验证真实 agent provider。

数据时间会过期，这是正常状态。服务使用查询时刻重新计算 fresh/stale/cache，不沿用快照的旧 fresh 标签。没有把现在的观测当成未来 30/60 分钟预测；live forecast 与综合 risk 均 unavailable。
