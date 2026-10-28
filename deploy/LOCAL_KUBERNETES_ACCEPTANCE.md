# Local Kubernetes acceptance — 28 October 2026

Phase 1 local deployment passed. Application source, algorithms, Dockerfile and Kubernetes manifests were unchanged. No cloud resources, registry push, commit or Git push were performed. This report supersedes the earlier statement that local container/cluster execution was unverified; it does not establish cloud readiness.

## Environment and prerequisite evidence

- Checkout: `5f2f4fba5c55f6ff50a42028ded3812671a58a03`; clean before work.
- GitHub Actions: [run 40624473140](https://github.com/wQingyang/DSA2111-OutdoorWiseSG/actions/runs/40624473140), `contracts-and-integration`, completed **success**, exact checkout SHA. GitHub API job inspection confirmed both `python -m pytest -q` and `npm test` steps succeeded. This workflow does not run browser tests or deploy containers.
- macOS host: ARM64. Docker Desktop 4.92.0, Engine 29.8.0, Linux/ARM64. Docker context `desktop-linux`; Kubernetes context explicitly `docker-desktop` throughout.
- Kubernetes v1.36.1; one Ready node `desktop-control-plane`, Linux ARM64, containerd 2.3.1. Default StorageClass `standard`, provisioner `rancher.io/local-path`, RWO, WaitForFirstConsumer.
- Built `outdoorwise:submission` using `docker build --platform linux/arm64 -t outdoorwise:submission .`. Image and both actual Pod image IDs matched SHA256 `e6817d3b5a3efe4a230cea253b407913dc62f3f274a9f167a688de18187c3895`.
- Docker Desktop's local image mirror made the image available to the cluster: successful image-pull events, no registry push or manual import needed on this installation. Other cluster configurations may need explicit loading; see [Docker Desktop Kubernetes documentation](https://docs.docker.com/desktop/use-desktop/kubernetes/).

## Results

| Check | Result | Evidence |
|---|---|---|
| Existing Compose configuration/runtime | PASS | `docker compose config --quiet`; app healthy, `/api/health` and `/api/ready` HTTP 200; collector running, 1,184 observations and all eight source attempts successful at inspection. |
| Full previous Compose acceptance | NOT TESTED | No saved complete acceptance report was found. Current health and ingestion were verified; provider workflows and restart persistence were accepted on Kubernetes, not retroactively attributed to Compose. |
| All Kubernetes manifests inspected | PASS | `app.yaml`, `collector.yaml`, `config.yaml`, `kustomization.yaml`, `namespace.yaml`, `storage.yaml`; rendering and server-side dry run succeeded. |
| ARM64 image compatibility | PASS | Native ARM64 build; both Pods ran the exact built digest. Historical imports and frozen dataset worked in the image. |
| Workloads | PASS | Exactly two application Deployments in namespace `outdoorwise`: `outdoorwise-app` and `outdoorwise-collector`, each desired/ready/available 1. One uvicorn worker; Recreate strategies. Kubernetes system workloads are separate. |
| Secrets | PASS | ORS/OpenRouter keys transferred from existing Compose container configuration directly to Kubernetes Secret via stdin; values never printed or written into repository files or command arguments. Optional data.gov key present as empty string; public collection succeeded without it. Collector receives only the data.gov key. |
| Shared persistent storage | PASS | PVC `outdoorwise-runtime`, 2 GiB RWO Bound, volume `pvc-93d5e430-e5ed-409d-9e68-bd3ba4cd79d3`; both Pods mount `/app/data/runtime` on the same node. CSV, SQLite, personalization JSON and generated routes persisted there. Both nonroot processes could write. |
| Single collector | PASS | Compose stopped without volume deletion before Kubernetes rollout. One Kubernetes collector. Nonblocking exclusive flock attempt from app Pod was rejected while collector owned `.ingestion_worker.lock`, including after collector replacement. No second worker was launched for the test. |
| Health/readiness/logs | PASS | Both Pods 1/1 Ready, zero unplanned restarts; API health/readiness HTTP 200; collector health module exit 0. Startup connection-refused probe during initial boot recovered normally; transient PVC scheduling resource-version conflict also recovered. Final logs show normal requests/cycles. |
| Tab 1 live | PASS | HTTP 200, `app_mode=live`, `data_mode=live`, `environmental_source=live_repository`, 12 catalog routes/recommendations; delayed departure +30 rejected HTTP 422. All eight real NEA source attempts successful. After restart, 543 observations present and collector still running. Availability remains governed by existing per-source freshness rules. |
| Tab 1 historical | PASS | Same API Deployment temporarily set to historical while repository/collector stayed live. Now/+30/+60 each returned 12 recommendations against `snapshot_20261015`, reference `2026-10-15T19:15:00+08:00`. Now: complete risk, `risk_weighted_v1`; delays: incomplete risk, `legacy_non_environmental` fallback. Restored live afterwards. |
| Tab 2 OpenRouter | PASS | Real `/api/llm/parse` request parsed an easy 4 km East Coast Park run into distance 4, difficulty 2, green/quiet/avoid-steps true. No mock or provider override. |
| Tab 2 ORS | PASS | Real `/api/generated-routes`, start longitude 103.898/latitude 1.298, distance 4 km, 3 candidates, tolerance 30%, difficulty 2: three validated ORS candidates and three assessments; generated-route GPX HTTP 200. |
| Personalization/account/session | PASS | New acceptance account, favourite persisted, derived profile favourite count 1/completed-run count 0, authenticated personalized recommendations, HttpOnly session, cross-user access HTTP 403. Original session and favourite survived replacement. No simulated completed runs were saved to the deployed runtime. |
| Deployed browser frontend | PASS | Chromium rendered 12 historical cards and historical banner; Tab 2 parse control visible. After restoration, live banner, 12 cards and visible Tab 2 parse control also passed in Chromium. Screenshots are local `/tmp/outdoorwise-k8s-historical.png` and `/tmp/outdoorwise-k8s-live.png`. |
| API Pod replacement persistence | PASS | Collector paused cleanly; SHA256 hashes for **all 23 runtime files** identical before/after API Pod replacement, including CSV versions, SQLite, personalization and generated-route storage. |
| Collector Pod replacement persistence | PASS | Scaled collector 1→0→1; replacement acquired lease, health exit 0, collection resumed with retained data. API account/session/favourite and SQLite integrity `ok` verified after both replacements. |
| Cloud deployment / multi-node storage | NOT TESTED | Acceptance used one Docker Desktop kind node with local-path storage; it establishes neither cloud operation nor cross-node storage/failover. |
| Crash/power-loss/cluster reset recovery | NOT TESTED | Tested controlled Pod replacement, not forced process kill, VM loss, cluster recreation or PVC deletion. |
| Populated deployed run-history adaptation | NOT TESTED | Did not insert fabricated completed runs into the persistent deployment. History/feedback/adaptation exercised by regression tests in temporary storage. Deployed check covers cold-start personalization and favourite/session persistence. |

## Regression verification

- `.venv/bin/python -m pytest -q`: **176 passed**, one Starlette/httpx deprecation warning, 139.71 seconds.
- `npm test`: **29 passed**, zero failures.
- `npm run test:browser`: **PASS on retry**, both suites, including actual isolated FastAPI live/historical modes. First attempt timed out waiting 30 seconds for a historical response; retry completed all checks. A separate redirected attempt inside the sandbox failed to bind localhost (`EPERM`); rerun with local server access succeeded. These suites use temporary data and provider fixtures, distinct from the real Kubernetes provider tests above.
- `docker compose config --quiet`, `kubectl kustomize deploy/k8s`, server-side dry run and `git diff --check`: **PASS**.
- Browser attempts overlapping Pod replacement or stale port-forwards failed to connect; reconnecting to the current Pod resolved access. Port-forward must be restarted after app Pod replacement.

## Commands used during the accepted run

These commands preserve the historical execution record, not a fresh-machine bootstrap. For reproducible setup without existing containers or credentials, use [the local Kubernetes guide](README.md#local-kubernetes-fresh-machine-setup). Run from the repository root. Always specify the Docker Desktop context; do not apply these commands to a cloud context. Keep existing volumes/PVCs. The Secret bootstrap below intentionally reuses the existing local Compose credentials without printing them; it requires the existing `outdoorwise-main-app-1` container, which can be stopped.

```bash
docker compose config --quiet
docker compose ps --all
docker compose exec -T collector python -m outdoorwise.cli status
docker build --platform linux/arm64 -t outdoorwise:submission .
docker image inspect outdoorwise:submission --format '{{.Id}} {{.Architecture}}'
kubectl --context docker-desktop get nodes -o wide
kubectl --context docker-desktop get storageclass
kubectl --context docker-desktop apply -f deploy/k8s/namespace.yaml
kubectl --context docker-desktop apply --dry-run=server -k deploy/k8s
docker compose stop

python3 - <<'PY'
import json
import subprocess
names = ['ORS_API_KEY', 'OPENROUTER_API_KEY', 'DATA_GOV_API_KEY']
container = json.loads(subprocess.check_output(
    ['docker', 'inspect', 'outdoorwise-main-app-1']))[0]
env = dict(item.split('=', 1) for item in container['Config']['Env'])
assert all(env.get(name) for name in names[:2]), 'Required credentials missing'
secret = {
    'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
    'metadata': {'name': 'outdoorwise-secrets', 'namespace': 'outdoorwise'},
    'stringData': {name: env.get(name, '') for name in names},
}
subprocess.run(
    ['kubectl', '--context', 'docker-desktop', 'apply', '--server-side', '-f', '-'],
    input=json.dumps(secret).encode(), check=True,
)
PY

kubectl kustomize deploy/k8s
kubectl --context docker-desktop apply -k deploy/k8s
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-app --timeout=60s
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-collector --timeout=60s
kubectl --context docker-desktop -n outdoorwise get deployments,pods,pvc,service -o wide
kubectl --context docker-desktop -n outdoorwise logs deployment/outdoorwise-app --tail=100
kubectl --context docker-desktop -n outdoorwise logs deployment/outdoorwise-collector --tail=100
kubectl --context docker-desktop -n outdoorwise exec deployment/outdoorwise-collector -- python -m outdoorwise.pipeline.collector_health
kubectl --context docker-desktop -n outdoorwise exec deployment/outdoorwise-collector -- python -m outdoorwise.cli status
kubectl --context docker-desktop -n outdoorwise port-forward --address 127.0.0.1 service/outdoorwise 8000:80
```

While port-forward runs, open <http://127.0.0.1:8000>. API checks in another terminal:

```bash
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/ready
curl --fail -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8000/api/route-recommendations
curl --fail -H 'Content-Type: application/json' \
  -d '{"text":"I want an easy 4 km green and quiet run at East Coast Park, avoiding stairs."}' \
  http://127.0.0.1:8000/api/llm/parse
curl --fail -H 'Content-Type: application/json' \
  -d '{"start":{"lon":103.898,"lat":1.298},"target_distance_km":4,"candidate_count":3,"distance_tolerance_pct":30,"target_difficulty":2}' \
  http://127.0.0.1:8000/api/generated-routes
```

Historical acceptance and restoration commands (reconnect port-forward after each rollout):

```bash
kubectl --context docker-desktop -n outdoorwise set env deployment/outdoorwise-app OUTDOORWISE_APP_MODE=historical
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-app --timeout=60s
# POST /api/route-recommendations with start_delay_min 0, 30, then 60.
kubectl --context docker-desktop -n outdoorwise set env deployment/outdoorwise-app OUTDOORWISE_APP_MODE=live
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-app --timeout=60s
```

Controlled persistence test sequence used (capture/compare hashes while collector is paused, before allowing new writes):

```bash
kubectl --context docker-desktop -n outdoorwise scale deployment/outdoorwise-collector --replicas=0
kubectl --context docker-desktop -n outdoorwise wait --for=delete pod -l app=outdoorwise-collector --timeout=60s
# Capture runtime file hashes via exec into app; replace app using live-mode command above.
# Compare hashes after rollout before restarting collector. No PVC deletion.
kubectl --context docker-desktop -n outdoorwise scale deployment/outdoorwise-collector --replicas=1
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-collector --timeout=60s
```

The tested hash command, run before and after API replacement, was:

```bash
kubectl --context docker-desktop -n outdoorwise exec deployment/outdoorwise-app -- python -c 'from pathlib import Path; import hashlib,json; p=Path("/app/data/runtime"); print(json.dumps({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob("*") if f.is_file()},sort_keys=True,indent=2))'
```

## Data/security implications and remaining cloud blockers

A fresh Kubernetes PVC was created; existing host and Compose runtime data were not copied, migrated or removed. Compose is stopped with its named volume retained. The Kubernetes runtime contains newly collected real observations, generated routes and an acceptance account/favourite/session. No credentials or session tokens are included in this report. Image build excludes `.env`, host runtime and local credential directories. Kubernetes Secrets still require cluster access controls and appropriate at-rest protection.

Before cloud deployment, select and validate durable storage with POSIX locks/SQLite semantics, backup/restore and recovery procedures; the tested Docker Desktop local-path volume is node-local with a Delete reclaim policy and is not cloud durability evidence. Retain one app replica/worker and one collector until storage coordination supports scaling. Pin/release a cloud-accessible immutable image, verify target architecture and image pull credentials, and measure capacity/disk growth. Configure HTTPS/ingress, secure cookies, secret management/access controls, provider quotas, authentication exposure/rate limits, monitoring and operational recovery. Validate on the actual target platform. None of these cloud operations was performed.

## Final verification

Final state: Tab 1 live, environmental repository live; app and collector each 1/1 Ready, same retained PVC, collector running. The local port-forward exposes only `127.0.0.1:8000`; it is a development process and must be restarted if its Pod or terminal/session stops. No Kubernetes deployment blockers required a code or manifest fix.
