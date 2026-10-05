# Six-person ownership and integration

以下为建议责任边界，可按你们原组员名字替换；你的职责是第 1 行。共享接口修改需要团队审查。

| Owner | 独占主要目录 | 接口 / 交付物 |
|---|---|---|
| 1 你：database + pipeline | storage、pipeline、bootstrap、contracts | repository adapter、CSV key/revision、get_route_environment、模块组装与集成验证 |
| 2 环境数据接入 | collectors、config/environment.toml 的 sources | collect()->(CollectionBatch,attempts)，source/单位/窗口契约和实测 fixture |
| 3 路线/空间数据 | data/catalog、services 中 geometry strategy | 保留 route_id，人工区域映射审核，未来 GeoJSON 采样扩展 |
| 4 降雨预测 | modules/predictor.py | predict(conditions,horizon_min)->每路线一个 Prediction；通过注入 reader 获取全指标，不直接读取 CSV |
| 5 环境风险/推荐/agent | modules/risk.py、modules/recommender.py、agent | assess(environments)->EnvironmentRisk；rank(...)->Recommendation；结构化证据与工具解释 |
| 6 前端/API 展示 | frontend、api | 消费 v2 HTTP 合约，显示 null/state/delivery/source/time，保持原地图与表单 |

## Fixed contracts

- `get_route_environment(route_id, as_of=None) -> RouteEnvironment` 是所有消费方共用入口。as_of 必须带时区，省略为当前。
- `EnvironmentCollector.collect() -> tuple[CollectionBatch,int]`，不写文件。transport 错误用 CollectionFailure；字段变化使该来源失败，不吞成成功。
- `EnvironmentRepository` / `RouteEnvironmentReader` / `Predictor` / `EnvironmentRiskAssessor` / `Recommender` 在 contracts/ports.py。
- Predictor 保留原条件入参以兼容现有 demo，可像 templates/module_template.py 一样构造时注入 reader。输出生成时间、horizon、source、is_mock、status 不可省略；unknown 为 None。live 禁止 mock forecast。
- RiskAssessor 本版 unavailable；官方 heat stress 原样展示，不冒充组员的综合模型。
- BaselineRecommender 保留原距离/降雨规则。组员可通过注入 reader 使用新环境指标；该规则尚未使用所有新增指标。
- Agent 工具只能返回已验证的数据/模块输出。原 LLM tool loop 沿用；本次未提供 key，不宣称真实 LLM 验证成功。demo agent 固定序列可检查 trace。

## Collaboration rules

只修改自己目录，接口新增先修改 contracts 和 schema 文档，由 integrator 审核。禁止业务模块 open/read CSV、自己调环境 API、缺失值填零、把预测写进观测表、把当前观测当成未来概率。新 collector 必须有真实字段 fixture 与单位校验。新模块从模板接入 bootstrap，再做 pipeline 集成测试。运行 `python -m pytest -q` 检查 import ownership 和关键数据行为。
