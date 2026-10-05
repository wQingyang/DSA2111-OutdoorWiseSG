# CSV schema

UTF-8、header 固定；空字段代表 nullable None，不是零。时间为带时区 ISO8601，collector 统一 UTC。数值和类别分列。

## locations.csv

位置：`data/runtime/locations.csv`。字段顺序与 `Location` 合约一致。

| 字段 | Python 类型 |
|---|---|
| source | `<class 'str'>` |
| location_id | `<class 'str'>` |
| name | `<class 'str'>` |
| location_type | `Literal['station', 'region']` |
| lon | `<class 'float'>` |
| lat | `<class 'float'>` |
| source_kind | `Literal['live', 'demo']` |
| metadata_updated_at | `<class 'pydantic.types.AwareDatetime'>` |

## environment_observations.csv

位置：`data/runtime/environment_observations.csv`。字段顺序与 `EnvironmentObservation` 合约一致。

| 字段 | Python 类型 |
|---|---|
| source | `<class 'str'>` |
| location_id | `<class 'str'>` |
| observed_at | `<class 'pydantic.types.AwareDatetime'>` |
| source_updated_at | `pydantic.types.AwareDatetime | None` |
| fetched_at | `<class 'pydantic.types.AwareDatetime'>` |
| metric | `Literal['rainfall', 'wind_speed', 'wind_direction', 'air_temperature', 'relative_humidity', 'pm25', 'psi', 'pm10', 'wbgt', 'heat_stress_level']` |
| value | `float | None` |
| category_value | `str | None` |
| unit | `<class 'str'>` |
| aggregation_window | `<class 'str'>` |
| source_kind | `Literal['live', 'demo']` |
| raw_value | `float | None` |
| raw_unit | `str | None` |
| revision | `<class 'int'>` |
| first_fetched_at | `pydantic.types.AwareDatetime | None` |

## environment_observation_versions.csv

位置：`data/runtime/environment_observation_versions.csv`。字段顺序与 `EnvironmentObservation` 合约一致。

| 字段 | Python 类型 |
|---|---|
| source | `<class 'str'>` |
| location_id | `<class 'str'>` |
| observed_at | `<class 'pydantic.types.AwareDatetime'>` |
| source_updated_at | `pydantic.types.AwareDatetime | None` |
| fetched_at | `<class 'pydantic.types.AwareDatetime'>` |
| metric | `Literal['rainfall', 'wind_speed', 'wind_direction', 'air_temperature', 'relative_humidity', 'pm25', 'psi', 'pm10', 'wbgt', 'heat_stress_level']` |
| value | `float | None` |
| category_value | `str | None` |
| unit | `<class 'str'>` |
| aggregation_window | `<class 'str'>` |
| source_kind | `Literal['live', 'demo']` |
| raw_value | `float | None` |
| raw_unit | `str | None` |
| revision | `<class 'int'>` |
| first_fetched_at | `pydantic.types.AwareDatetime | None` |

## route_source_mapping.csv

位置：`data/runtime/route_source_mapping.csv`。字段顺序与 `RouteSourceMapping` 合约一致。

| 字段 | Python 类型 |
|---|---|
| route_id | `<class 'str'>` |
| metric | `Literal['rainfall', 'wind_speed', 'wind_direction', 'air_temperature', 'relative_humidity', 'pm25', 'psi', 'pm10', 'wbgt', 'heat_stress_level']` |
| source | `<class 'str'>` |
| location_id | `str | None` |
| source_kind | `Literal['live', 'demo']` |
| match_method | `<class 'str'>` |
| station_distance_km | `float | None` |
| representative_lon | `<class 'float'>` |
| representative_lat | `<class 'float'>` |
| mapped_at | `<class 'pydantic.types.AwareDatetime'>` |

## route_environment_latest.csv

位置：`data/runtime/route_environment_latest.csv`。字段顺序与 `RouteMetric` 合约一致。

| 字段 | Python 类型 |
|---|---|
| route_id | `<class 'str'>` |
| metric | `Literal['rainfall', 'wind_speed', 'wind_direction', 'air_temperature', 'relative_humidity', 'pm25', 'psi', 'pm10', 'wbgt', 'heat_stress_level']` |
| value | `float | None` |
| category_value | `str | None` |
| unit | `<class 'str'>` |
| aggregation_window | `<class 'str'>` |
| source | `<class 'str'>` |
| location_id | `str | None` |
| location_name | `str | None` |
| source_kind | `Literal['live', 'demo']` |
| delivery | `Literal['live', 'cache', 'demo', 'unavailable']` |
| state | `Literal['fresh', 'stale', 'missing']` |
| match_method | `<class 'str'>` |
| station_distance_km | `float | None` |
| observed_at | `pydantic.types.AwareDatetime | None` |
| source_updated_at | `pydantic.types.AwareDatetime | None` |
| fetched_at | `pydantic.types.AwareDatetime | None` |
| as_of | `<class 'pydantic.types.AwareDatetime'>` |
| revision | `int | None` |
| reason | `<class 'str'>` |

## ingestion_runs.csv

位置：`data/runtime/ingestion_runs.csv`。字段顺序与 `IngestionRun` 合约一致。

| 字段 | Python 类型 |
|---|---|
| run_id | `<class 'str'>` |
| source | `<class 'str'>` |
| source_kind | `Literal['live', 'demo']` |
| started_at | `<class 'pydantic.types.AwareDatetime'>` |
| finished_at | `<class 'pydantic.types.AwareDatetime'>` |
| status | `Literal['success', 'failed', 'skipped']` |
| attempts | `<class 'int'>` |
| received_records | `<class 'int'>` |
| inserted_records | `<class 'int'>` |
| revised_records | `<class 'int'>` |
| unchanged_records | `<class 'int'>` |
| error | `<class 'str'>` |

## Keys and history

- locations：source + location_id + source_kind。不同 API 的同名站点不能合并。
- environment_observations：source + location_id + observed_at（同一时间瞬间）+ metric + aggregation_window + source_kind。重复抓取更新 fetched_at，不追加重复观测；上游改值/updatedTimestamp 改变会更新同一行并增加 revision。
- environment_observation_versions：同一观测 key + revision，保存修订前后版本和每版 first_fetched_at，供 as_of 查询，不能删除。
- route_source_mapping / route_environment_latest：路线 + 指标的当前物化视图；包含 source_kind。每次刷新替换，历史查询使用观测版本重算，不读取最新视图猜测过去。
- ingestion_runs：每来源每次实际尝试一条 run_id 日志，含收到/新增/修订/不变计数和失败原因。--due 跳过的来源不生成日志。
- routes.csv 和 GeoJSON 保留在 data/catalog，格式没有改变。

## as_of definition

读取 observed_at <= as_of 且该 revision 在 as_of 前已抓取的最新记录；若来源提供 updatedTimestamp，也必须 <= as_of。避免历史查询偷看后来修订的数据。locations 是当前目录而非完整历史地理目录；站点搬迁/改名的精确历史匹配尚未实现。重复抓取刷新时间的每次历史不单独保存，因此历史 delivery 可能保守标成 cache；数值版本不会穿越。

## Writer

所有 CSV IO 只在 repository。线程 RLock + 跨进程 flock 保证同路径单 writer；同目录临时文件写入、fsync、os.replace。多文件更新先存 durable pending journal，再逐一原子替换；重启构造 repository 时重放。不是跨文件的单次 OS 原子提交；服务读取共享同一锁，外部直接读取 CSV 无此保证。推荐本地磁盘，不宣称网络盘/突然掉电的完整数据库事务保证。

预测单独存 data/runtime/predictions_latest.json；latest_run.json 保存组合快照。真实观测 long table 不接受未来预测。旧 observations.csv 若存在会一次迁移降雨，文件保留审计。
