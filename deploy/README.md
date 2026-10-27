# Demonstration deployment

This is deployment preparation. Docker image construction, running Compose containers, Kubernetes API validation and a cloud rollout remain unverified by the current submission checks. No container or cluster rollout is performed as part of repository validation. Kustomize rendering and Compose configuration validation pass.

## Local Compose

From the repository root:

```bash
cp .env.example .env
# Edit .env: ORS_API_KEY, OPENROUTER_API_KEY, optional DATA_GOV_API_KEY.
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/ready
docker compose logs --tail=100 app collector
```

Open http://127.0.0.1:8000. Confirm fresh source timestamps after collection; external API failure must show stale/missing, not synthetic replacement. Confirm manual dynamic generation with ORS, then OpenRouter parsing and coordinate confirmation. Inspect `docker compose exec collector python -m outdoorwise.cli status`.

```bash
# Stop/restart without deleting observations or user state.
docker compose stop collector
docker compose start collector
docker compose down
```

Do not use volume-deletion flags unless deliberately deleting all users/history/observations. Compose now creates a fresh named runtime volume; it does not migrate the old host bind mount. Image runtime excludes tracked demonstration accounts, active sessions and credentials. Docker copies the fixed snapshot (~35 MB) solely for the opt-in historical experiment; live inference never reads it.

## Kubernetes prerequisites

Use a small Linux cluster with a default dynamic StorageClass supporting ReadWriteOnce, POSIX file locks and SQLite semantics. A single-node local cluster is sufficient. Keep **one API replica, one uvicorn worker, one collector replica**. API and collector share one PVC and are co-located by required pod affinity. Recreate updates avoid overlapping writers. Do not use autoscaling or network filesystems with unverified locking behavior.

Build and load an image into your local cluster runtime, or push it manually to a registry you control. The manifests default to `outdoorwise:submission` with IfNotPresent; building on the host alone does not load an image into a cluster.

```bash
docker build -t outdoorwise:submission .
# For an existing kind cluster (if used):
kind load docker-image outdoorwise:submission
# For an existing minikube cluster (alternative):
# minikube image load outdoorwise:submission
```

For a remote registry, tag/push explicitly, then use a local Kustomize overlay setting both deployment images to the same immutable image digest. Configure imagePullSecrets if required. No registry or cloud deployment is performed by this repository.

## Secrets and rollout

Export keys in your shell through your normal secret-management workflow. They must never enter Git, ConfigMaps, image layers or frontend code. Generate the Secret from a temporary file to avoid putting key values in kubectl process arguments:

```bash
kubectl apply -f deploy/k8s/namespace.yaml
python - <<'PY'
import os
from pathlib import Path
path = Path('/tmp/outdoorwise-secrets.env')
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as handle:
    for name in ['ORS_API_KEY', 'OPENROUTER_API_KEY', 'DATA_GOV_API_KEY']:
        value = os.environ.get(name, '')
        if '\n' in value or '\r' in value:
            raise ValueError('Secret values must be single-line')
        handle.write(name + '=' + value + '\n')
print('Temporary Secret input created; remove it after the next command.')
PY
kubectl -n outdoorwise create secret generic outdoorwise-secrets \
  --from-env-file=/tmp/outdoorwise-secrets.env \
  --dry-run=client -o yaml | kubectl apply -f -
python - <<'PYCODE'
from pathlib import Path
Path('/tmp/outdoorwise-secrets.env').unlink()
PYCODE
kubectl kustomize deploy/k8s > /tmp/outdoorwise-rendered.yaml
kubectl apply --dry-run=server -f /tmp/outdoorwise-rendered.yaml
kubectl apply -k deploy/k8s
kubectl -n outdoorwise rollout status deployment/outdoorwise-app
kubectl -n outdoorwise rollout status deployment/outdoorwise-collector
kubectl -n outdoorwise get pods,pvc,service
kubectl -n outdoorwise logs deployment/outdoorwise-collector --tail=100
kubectl -n outdoorwise port-forward service/outdoorwise 8000:80
```

Secret permissions/encoding do not encrypt Kubernetes etcd; apply your cluster's normal access controls. Both ORS/OpenRouter keys can be empty for catalog-only demonstration; their endpoints return clear errors. Collector receives only the data.gov key.

For public HTTPS, set `OUTDOORWISE_SECURE_COOKIES: "1"` in the ConfigMap and use an existing TLS ingress/gateway. The supplied ClusterIP + localhost port-forward is an HTTP demonstration configuration, not a public ingress. Restart deployments after updating Secrets/ConfigMaps. Restrict public access and provider quotas before exposure; the existing refresh/ORS/LLM endpoints have no per-user rate limiter.

## Probes, storage and limits

The API runs as UID/GID 10001, with no privilege escalation or service-account token. The PVC uses fsGroup 10001; verify your CSI driver applies permissions. Startup/liveness probe `/api/health`; readiness `/api/ready` checks catalog/runtime access. It intentionally remains ready when external weather sources fail: missing/stale data is disclosed per response.

Collector readiness/liveness runs `python -m outdoorwise.pipeline.collector_health`, checking a running heartbeat within 1800 seconds. Eight source retry sequences can take many minutes. Source failures must appear in ingestion status rather than cause restart storms. Disk failure stops the worker. SIGTERM allows 180 seconds to finish the current bounded source request.

App requests 100m CPU/256 MiB, limits 1 CPU/1 GiB. Collector requests 100m/128 MiB, limits 500m/512 MiB. These are initial demonstration budgets, not measured capacity guarantees. CSV rewrites and full-history snapshots grow with collected history; monitor memory/disk/cycle duration. A growing dataset may need larger limits and partitioned repository storage.

Back up the PVC with the API/collector stopped or through an application-consistent storage snapshot. Do not delete a PVC as an update mechanism. Scaling requires a coordinated storage/repository design for CSV, account SQLite, per-user JSON, generated routes and sessions; adding replicas is not safe. Required affinity may leave collector pending if the API cannot schedule. Inspect PVC binding, image availability, node capacity and volume permissions first.

## Deployment acceptance checks

- Image imports all API and historical modules; `/api/health` and `/api/ready` pass.
- One collector owns the worker lease; restart retains observations/revisions.
- Partial API failure retains data and reports stale/missing.
- New deployment starts without synthetic accounts or active sessions.
- Anonymous catalog, registration/login/profile, two-user isolation and GPX work.
- ORS generation works; parser credentials stay server-side; unresolved location cannot auto-submit.
- Unified Live/Historical Tab 1 modes remain visibly distinct; supplementary baselines remain backend-only.
- PVC data survives pod replacement; CPU/memory and collection duration are observed.
- Capture actual cluster rollout evidence before marking cloud deployment complete.
