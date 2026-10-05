# API configuration and source semantics

所有地址在 `config/environment.toml`，collector 在 `outdoorwise/collectors/`。公共访问本次不需要 key；可选 DATA_GOV_API_KEY 通过 x-api-key 发送，不写入 CSV。`OUTDOORWISE_ENV_CONFIG` 可替换 TOML 路径，`OUTDOORWISE_DATA_ROOT` 可换数据目录。

基础地址 `https://api-open.data.gov.sg/v2/real-time/api/`；下表 URL 列追加在该地址后。已实际请求全部 8 个地址，并通过各自 parser 写入真实 CSV。

| URL / collector | 实际字段 | 原始 → 统一单位 | 统计窗口 | 官方发布间隔 / 本版采集间隔 |
|---|---|---|---|---|
| rainfall / rainfall.py | readings[].data[].value; TB1 Rainfall 5 Minute Total F | mm | 5 分钟累计 PT5M | 5 分钟 / 300s |
| wind-speed / wind_speed.py | value; Wind Speed AVG(S)10M M1M | knots → m/s（×1852/3600） | 10 分钟均值 PT10M，字段包含分钟分辨率 | 5 分钟 / 300s |
| wind-direction / wind_direction.py | value; Wind Dir AVG (S) 10M M1M | degrees → degree | 10 分钟均值 PT10M | 5 分钟 / 300s |
| air-temperature / temperature.py | value; DBT 1M F | deg C → degC | 1 分钟 PT1M | 5 分钟 / 300s |
| relative-humidity / humidity.py | value; RH 1M F | percentage → % | 1 分钟 PT1M | 5 分钟 / 300s |
| pm25 / pm25.py | items[].readings.pm25_one_hourly[region] | µg/m³ → ug/m3 | 1 小时 PT1H | 15 分钟 / 900s |
| psi / psi.py | psi_twenty_four_hourly[region] | 无量纲 → index | 24 小时 PT24H | 15 分钟 / 900s |
| psi / psi.py | pm10_twenty_four_hourly[region] | µg/m³ → ug/m3 | 24 小时 PT24H | 15 分钟 / 900s |
| weather?api=wbgt / wbgt.py | records[].item.readings[].wbgt | 字符串摄氏度 → degC | 15 分钟均值 PT15M | 15 分钟 / 900s |
| weather?api=wbgt / wbgt.py | records[].item.readings[].heatStress | Low / Moderate / High → category_value | 官方对应 WBGT 的 PT15M | 15 分钟 / 900s |

发布间隔、统计窗口、返回时间分辨率是三个概念。PM2.5 的一小时窗口不能误记为 15 分钟；PSI/PM10 不能称为即时浓度。PM10 使用浓度字段，**不使用 pm10_sub_index**。站点接口当前没有提供可靠 source_updated_at，此列留空，不能用 fetched_at 冒充。regional 使用 items[].timestamp/updatedTimestamp；WBGT 使用 records[].datetime/updatedTimestamp，只接 observation 且 isStationData=true 的站点数据。WBGT 与 heat stress 均来自官方，不由温湿度推算。

官方数据集（字段与发布周期参考）：
- rainfall: https://data.gov.sg/datasets/d_6580738cdd7db79374ed3152159fbd69/view
- wind speed: https://data.gov.sg/datasets/d_7677738484067741bf3b56ab5d69c7e9/view
- wind direction: https://data.gov.sg/datasets/d_534cf203023b51f51f879145ccc56ff9/view
- temperature: https://data.gov.sg/datasets/d_66b77726bbae1b33f218db60ff5861f0/view
- humidity: https://data.gov.sg/datasets/d_2d3b0c4da128a9a59efca806441e1429/view
- PM2.5: https://data.gov.sg/datasets/d_e1058d6974c877257e32048ab128ad83/view
- PSI: https://data.gov.sg/datasets/d_fe37906a0182569d891506e815e819b7/view
- WBGT: https://data.gov.sg/datasets/d_87884af1f85d702d4f74c6af13b4853d/view

## Transport and freshness policy

TOML：timeout_seconds=20，max_retries=2（最多 3 次请求），指数退避与 Retry-After，最长单次退避 30 秒，各来源请求间隔 1.5 秒。429/5xx/网络错误可重试；解析/单位变化不重试，会记失败。每个 API 故障独立记录，其他来源继续。

stale_after_seconds 为项目策略，并非官方健康标准：站点 900s、regional 7200s、WBGT 2700s。依据 observed_at 判断状态，依据抓取间隔/最近失败判断缓存。无观测 missing；真零仍显示 0。返回未来时间的观测不进入当前查询。配置间隔不会自动启动 scheduler。

空气区域为人工确认的 source region 配置：Marina Bay=south，Woodlands=north；没有官方区域多边形包含计算，区域 labelLocation 不代表路线站点距离，因此 regional 的 station_distance_km 为空。扩大路线目录时必须补充 route_regions 并复核。
