# Demonstration deployment

Local Docker Desktop Kubernetes acceptance was completed on 28 October 2026; see [the acceptance report](LOCAL_KUBERNETES_ACCEPTANCE.md) for exact commands, PASS/FAIL/NOT TESTED evidence and remaining cloud blockers. Cloud rollout remains unverified. Repository regression checks alone do not establish deployment success.

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

## Local Kubernetes: fresh-machine setup

Follow these steps from a fresh checkout; no existing Compose container, runtime data,
image, Secret or temporary file is needed. This guide targets **Docker Desktop's
built-in kind provisioner, one node, macOS ARM64**. The accepted combination was
Docker Desktop **4.92.0**, Engine **29.8.0**, Kubernetes **v1.36.1**. Other versions
and operating systems have not been independently accepted for this project.

### 1. Install tools, clone and configure Docker Desktop

Install Git, Docker Desktop for Apple silicon, `kubectl` (bundled with Docker
Desktop; ensure it is on PATH), and Python 3. Python is used only for the
standard-library Secret helper below; no virtual environment, project Python
installation, Node or standalone kind CLI is needed to run Kubernetes. Internet
access is needed for the base image, Python packages and external providers.
Start Docker Desktop before running the Docker checks below.

```bash
git clone https://github.com/wQingyang/DSA2111-OutdoorWiseSG.git
cd DSA2111-OutdoorWiseSG
docker --context desktop-linux version
kubectl version --client
python3 --version
```

Start Docker Desktop. In **Settings → General**, enable **Use containerd for pulling
and storing images**. In the **Kubernetes** view, create a cluster with provisioner
**kind**, **1 node**, and **v1.36.1** if offered. If that version is unavailable,
record the selected version and repeat acceptance rather than assuming equivalence.
Wait for cluster creation to finish. Do not reset an existing cluster containing
valuable PVCs to change settings. Docker documents the [Kubernetes provisioners](https://docs.docker.com/desktop/use-desktop/kubernetes/)
and [containerd image-store setting](https://docs.docker.com/desktop/features/containerd/).

### 2. Check context, node and storage

```bash
kubectl config get-contexts
kubectl config use-context docker-desktop
kubectl config current-context
kubectl --context docker-desktop wait --for=condition=Ready nodes --all --timeout=180s
kubectl --context docker-desktop get nodes -o wide
kubectl --context docker-desktop get storageclass
docker context show
docker --context desktop-linux info --format '{{json .DriverStatus}}'
```

Confirm active context **docker-desktop**, one **Ready** Linux ARM64 node, and a
**default** dynamic StorageClass. The accepted cluster had node
`desktop-control-plane`, `standard (default)`, provisioner `rancher.io/local-path`,
and `WaitForFirstConsumer`. The Docker driver output included
`io.containerd.snapshotter.v1`. If context or storage is missing, finish Docker
Desktop setup before proceeding. Every cluster command below also specifies the
context to avoid depending on a later shell's active selection.

Keep **one app replica, one uvicorn worker and one collector replica**. Both Pods
share one ReadWriteOnce PVC and required pod affinity places the collector on the
app's node. Multi-node storage/failover has not been accepted.

### 3. Stop other OutdoorWise startup options

If Compose has been used from this checkout, stop it without removing its volume:

```bash
docker --context desktop-linux compose stop
docker --context desktop-linux compose ps --all
```

On a new checkout there may be no Compose containers to stop. Stop any Local Python
app/collector with Ctrl+C in its terminal too. Do not run multiple collectors
against one runtime directory. Do not use `docker compose down -v`. Host runtime,
Compose's named volume and the Kubernetes PVC are separate stores; no automatic
migration occurs. Do not copy or delete existing operational data during setup.

### 4. Build the image and verify the Docker Desktop image bridge

```bash
docker --context desktop-linux build --platform linux/arm64 -t outdoorwise:submission .
docker --context desktop-linux image inspect outdoorwise:submission --format '{{.Id}} {{.Architecture}} {{json .RepoDigests}}'
```

Run at the repository root, where the Dockerfile copies the catalog and frozen
historical snapshot. Keep the tag **outdoorwise:submission**, matching both
Deployments' `image` and `imagePullPolicy: IfNotPresent`. The ARM64 flag targets the
accepted Apple-silicon node; an AMD64 node needs a matching `linux/amd64` build and
its own acceptance checks. Use Docker Desktop's default Docker builder; a custom
Buildx builder that only exports a build cache is insufficient unless its output
is loaded into Docker Desktop's containerd image store.

Docker Desktop kind's node has a **separate containerd store**. On the accepted
installation, Docker Desktop configures a bridge through its
`desktop-containerd-registry-mirror`; the node resolves/pulls the locally built
`docker.io/library/outdoorwise:submission` through that mirror. No push or manual
image import was used. This is Docker Desktop integration, not a promise that
arbitrary kind clusters can see host images. Read-only inspection on the accepted
installation confirmed the node's `/etc/containerd/certs.d/_default/hosts.toml`
points to `http://registry-mirror:1273`, and that mirror mounts Docker Desktop's
containerd socket. Docker's [Kubernetes documentation](https://docs.docker.com/desktop/use-desktop/kubernetes/)
lists this mirror among kind's components.

**Verify actual Pod image IDs after step 6**, comparing their manifest digest to
the local `RepoDigests` above (an image config ID can differ from a manifest digest). Do not treat a successful host build as image availability.
Do not use bare `kind load docker-image` here: it targets a standalone kind cluster
named `kind` by default, not this documented Docker Desktop setup. If the mirror
cannot serve the image, stop at the image-availability blocker and use the
troubleshooting steps below; no alternative import command has been validated by
this project.

### 5. Create the Kubernetes Secret without printing keys

Obtain separate keys from [OpenRouteService](https://openrouteservice.org/)
(geometry) and [OpenRouter](https://openrouter.ai/) (preference parsing).
`DATA_GOV_API_KEY` is optional. This helper prompts without echo, requires both
Tab 2 keys, and sends the Secret directly to kubectl stdin. It uses no previous
Compose container, `.env` or fixed `/tmp` file. Run it in an interactive terminal;
never enable shell tracing or paste keys into command arguments.

```bash
kubectl --context docker-desktop apply -f deploy/k8s/namespace.yaml
python3 - <<'PYCODE'
import getpass
import json
import subprocess
import sys
import warnings

warnings.simplefilter('error', getpass.GetPassWarning)
if not sys.stdin.isatty() and not sys.stderr.isatty():
    raise SystemExit('Run this helper in an interactive terminal.')
values = {}
for name in ('ORS_API_KEY', 'OPENROUTER_API_KEY', 'DATA_GOV_API_KEY'):
    optional = name == 'DATA_GOV_API_KEY'
    value = getpass.getpass(name + (' (optional; Enter to skip): ' if optional else ': '))
    if (not optional and not value.strip()) or '\n' in value or '\r' in value:
        raise SystemExit('Required keys must be nonempty; all values must be single-line.')
    values[name] = value
secret = {
    'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
    'metadata': {'name': 'outdoorwise-secrets', 'namespace': 'outdoorwise'},
    'stringData': values,
}
subprocess.run(
    ['kubectl', '--context', 'docker-desktop', 'apply', '--server-side', '-f', '-'],
    input=json.dumps(secret).encode(), check=True,
)
PYCODE
kubectl --context docker-desktop -n outdoorwise describe secret outdoorwise-secrets
```

`describe secret` displays key names and byte counts, not values. The optional
`DATA_GOV_API_KEY` entry must still exist (empty is allowed), because the collector
references that key. The app receives all three keys; the collector receives only
the data.gov key. `OPENROUTER_MODEL` comes from ConfigMap `outdoorwise-config` and
defaults to `openrouter/free`.

Kubernetes does not load `.env`. `.env.example` is a blank local/Compose template;
`.gitignore` and `.dockerignore` exclude `.env`, `.env.*` except `.env.example`,
and operational runtime data. Never put real keys in the example, manifests,
ConfigMaps, screenshots or Git. Do not dump Secrets as YAML/JSON or container
environments into logs. Kubernetes Secret encoding is not encryption; protect
local cluster access and apply appropriate secret management before cloud use.

### 6. Deploy and verify the two workloads

```bash
kubectl --context docker-desktop kustomize deploy/k8s
kubectl --context docker-desktop apply --dry-run=server -k deploy/k8s
kubectl --context docker-desktop apply -k deploy/k8s
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-app --timeout=180s
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-collector --timeout=300s
kubectl --context docker-desktop -n outdoorwise get deployments,pods,services,pvc -o wide
kubectl --context docker-desktop -n outdoorwise get pods -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.containerStatuses[0].imageID}{"\n"}{end}'
```

Expect exactly two OutdoorWise Deployments, each **1/1** Ready/Available; both Pods
Running/Ready; Service **outdoorwise**, ClusterIP port **80** → app port **8000**;
PVC **outdoorwise-runtime**, **Bound**, **2Gi**, RWO. On a first deployment,
`WaitForFirstConsumer` permits a Pending PVC until Pods schedule. The PVC mounts
at `/app/data/runtime`, covering environmental CSV/revisions, account/session
SQLite, personalization JSON and generated routes. A clean PVC starts without
host or Compose accounts/history. The catalog and historical dataset are in the
image outside that mount.

### 7. Check the collector and API

```bash
kubectl --context docker-desktop -n outdoorwise logs deployment/outdoorwise-app --tail=100
kubectl --context docker-desktop -n outdoorwise logs deployment/outdoorwise-collector --tail=100
kubectl --context docker-desktop -n outdoorwise exec deployment/outdoorwise-collector -- python -m outdoorwise.pipeline.collector_health
kubectl --context docker-desktop -n outdoorwise exec deployment/outdoorwise-collector -- python -m outdoorwise.cli status
```

The health command exits 0 for a running recent heartbeat. Repeat `status` and
inspect logs after later collection cycles: `worker.state` should be `running`,
`completed_cycles` and heartbeat should advance, and source attempts/observation
counts should reflect actual ingestion. A scheduling cycle with no due sources
can leave counts unchanged; `--tick-seconds 30` is a scheduler check interval.
Source errors are reported in ingestion status. Do not launch a second `watch`
process or use API requests to force collection as an acceptance shortcut.

### 8. Port-forward and test the workflows

Keep this running in a terminal:

```bash
kubectl --context docker-desktop -n outdoorwise port-forward --address 127.0.0.1 service/outdoorwise 8000:80
```

Open **http://127.0.0.1:8000** (API docs: `/docs`). From another terminal:

```bash
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/ready
curl --fail -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8000/api/route-recommendations
```

If port 8000 is occupied, on macOS use `lsof -nP -iTCP:8000 -sTCP:LISTEN` to identify
the owner. Stop your old port-forward with Ctrl+C or stop this project's Compose
services; do not terminate an unrelated process. Alternatively use
`kubectl --context docker-desktop -n outdoorwise port-forward --address 127.0.0.1 service/outdoorwise 8001:80`
and open **http://127.0.0.1:8001**, changing curl URLs too. Ctrl+C ends forwarding
without stopping workloads. Reconnect after app Pod replacement.

| Workflow | Manual acceptance check |
|---|---|
| Tab 1 live | Confirm LIVE MODE, submit Find Recommended Routes, inspect actual availability/provenance and map/GPX. Only departure Now is supported. |
| Tab 2 OpenRouter | Parse “I want an easy 4 km green and quiet run at East Coast Park, avoiding stairs.” Check preferences, then explicitly confirm starting coordinates. Parsing alone must not generate geometry. |
| Tab 2 ORS | Generate using the confirmed point (accepted example longitude 103.898, latitude 1.298, 4 km). Check validated geometry, current-environment assessments and GPX. ORS can also be tested using manual preferences without OpenRouter. Provider quotas/availability can affect results. |
| Personalization | Register/login, add a favourite, inspect profile and authenticated recommendations; logout/login and check favourite retention. Do not record a simulated run as completed. Populated-history adaptation remains covered by automated tests in temporary storage unless tested with genuine eligible history. |

Tab 1 historical requires temporarily replacing the **same app Deployment**, not
adding a workload. Leave the collector/repository in live mode:

```bash
kubectl --context docker-desktop -n outdoorwise set env deployment/outdoorwise-app OUTDOORWISE_APP_MODE=historical
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-app --timeout=180s
# Reconnect port-forward, reload the browser, test Now, +30 and +60.
# Check the fixed snapshot/reference and delayed incomplete-risk fallback.
kubectl --context docker-desktop -n outdoorwise set env deployment/outdoorwise-app OUTDOORWISE_APP_MODE=live
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-app --timeout=180s
```

Reconnect port-forward again and verify LIVE MODE. Tab 2 remains a current-environment
workflow in either app mode. Record your own PASS/FAIL/NOT TESTED results; the
[acceptance report](LOCAL_KUBERNETES_ACCEPTANCE.md) records the earlier tested run.

## Safe Kubernetes stop, restart and redeploy

To stop OutdoorWise while preserving its PVC, Secret, ConfigMap and Service, stop
the collector first, allow its normal termination (up to 180 seconds), then the app:

```bash
kubectl --context docker-desktop -n outdoorwise scale deployment/outdoorwise-collector --replicas=0
kubectl --context docker-desktop -n outdoorwise wait --for=delete pod -l app=outdoorwise-collector --timeout=240s
kubectl --context docker-desktop -n outdoorwise scale deployment/outdoorwise-app --replicas=0
kubectl --context docker-desktop -n outdoorwise wait --for=delete pod -l app=outdoorwise-app --timeout=120s
```

Resume with the app first so the collector's required affinity can be satisfied:

```bash
kubectl --context docker-desktop -n outdoorwise scale deployment/outdoorwise-app --replicas=1
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-app --timeout=180s
kubectl --context docker-desktop -n outdoorwise scale deployment/outdoorwise-collector --replicas=1
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-collector --timeout=300s
```

To replace Pods without deleting data (including after Secret/ConfigMap changes):

```bash
kubectl --context docker-desktop -n outdoorwise rollout restart deployment/outdoorwise-app
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-app --timeout=180s
kubectl --context docker-desktop -n outdoorwise rollout restart deployment/outdoorwise-collector
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-collector --timeout=300s
```

Recreate strategy prevents overlapping old/new replicas per Deployment. Check
health, collector status, login/favourite retention and the same Bound PVC after
replacement, and reconnect port-forward. For an exact file-hash comparison,
pause the collector and avoid API actions that write data; see the acceptance
report's controlled persistence procedure. Do not delete lock files.

`kubectl --context docker-desktop apply -k deploy/k8s` reapplies manifests without
deleting the PVC, but also sets both replica counts to 1. Use it when ready to
resume workloads. Rebuilding the same tag plus restarting may run a node's cached
old image because of `IfNotPresent`. For an intentional new local build, use a
unique tag and update **both** Deployments:

```bash
OUTDOORWISE_LOCAL_IMAGE="outdoorwise:local-$(date +%Y%m%d%H%M%S)"
docker --context desktop-linux build --platform linux/arm64 -t "$OUTDOORWISE_LOCAL_IMAGE" .
kubectl --context docker-desktop -n outdoorwise set image deployment/outdoorwise-app app="$OUTDOORWISE_LOCAL_IMAGE"
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-app --timeout=180s
kubectl --context docker-desktop -n outdoorwise set image deployment/outdoorwise-collector collector="$OUTDOORWISE_LOCAL_IMAGE"
kubectl --context docker-desktop -n outdoorwise rollout status deployment/outdoorwise-collector --timeout=300s
```

Inspect Pod image IDs again. This is an operational recipe, not a newly executed
acceptance test. A later `apply -k` restores the manifests' `outdoorwise:submission`
reference; reapply your chosen image to both Deployments after it, or maintain a
local Kustomize overlay for deliberate image overrides.

Do not use `kubectl delete -k deploy/k8s`, delete the namespace/PVC, reset the
cluster or factory-reset Docker Desktop to stop/redeploy this app: those actions
can destroy persistent data. The accepted local-path storage has a **Delete**
reclaim policy and is node-local. Pod persistence does not establish survival of
cluster deletion, VM loss or multi-node failover.

## Troubleshooting Kubernetes

Start with these read-only checks; do not share output containing credentials:

```bash
kubectl --context docker-desktop -n outdoorwise get deployments,pods,services,pvc -o wide
kubectl --context docker-desktop -n outdoorwise get events --sort-by=.lastTimestamp
kubectl --context docker-desktop -n outdoorwise describe deployment outdoorwise-app
kubectl --context docker-desktop -n outdoorwise describe deployment outdoorwise-collector
kubectl --context docker-desktop -n outdoorwise describe pvc outdoorwise-runtime
kubectl --context docker-desktop -n outdoorwise logs deployment/outdoorwise-app --tail=100
kubectl --context docker-desktop -n outdoorwise logs deployment/outdoorwise-collector --tail=100
```

For a failing Pod, copy its name from `get pods`, then use
`kubectl --context docker-desktop -n outdoorwise describe pod POD_NAME` and
`kubectl --context docker-desktop -n outdoorwise logs POD_NAME --previous --tail=100`
(the latter needs a previous terminated container).

| Symptom | Check and recovery |
|---|---|
| ImagePullBackOff / ErrImagePull | Confirm Docker context `desktop-linux`, containerd image store enabled, exact image tag and ARM64 architecture. Check Pod events and the mirror/containerd diagnostics below. A missing mirror or inability to resolve the local image is a setup blocker; host image existence alone is insufficient. Do not reset the cluster or invent an import command. |
| Wrong image after rebuild | `IfNotPresent` can reuse the node cache. Use the unique-tag procedure and compare actual image IDs; restarting alone does not guarantee an updated image. |
| Pending PVC / Pod | A first PVC may await its consumer. Confirm default StorageClass, node Ready/capacity, PVC events and local-path provisioner health. Collector required affinity needs a scheduled app Pod. Do not delete a bound PVC to solve scheduling. |
| CrashLoopBackOff / permission denied | Inspect current/previous logs and exit/OOM events. Verify PVC access for UID/GID 10001, fsGroup support, disk space and resource limits. Never solve permissions by deleting stored data. |
| CreateContainerConfigError / provider unavailable | Check Secret exists with all three key names using `describe secret`; an empty optional data.gov value is valid. Re-run the non-echoing helper for missing/wrong keys, then deliberately restart affected Deployments. Kubernetes does not source `.env`. Check provider account/quota/network access if keys are present; readiness alone does not validate ORS/OpenRouter. |
| Port-forward bind/error/disconnect | Identify port owner, use 8001 if needed, confirm Service selector/app Ready, and reconnect after Pod replacement. Keep the terminal/process running. No public ingress is configured. |
| Collector lease conflict | Stop any other collector sharing the mount, inspect workload counts/logs and allow graceful termination. The lock is an OS-held flock, not evidence that a file should be removed. Never delete `.ingestion_worker.lock` to bypass ownership. |
| Collector not Ready / no new observations | Check heartbeat health, completed cycles, per-source due attempts and logs. Initial collection/retries may take time. Do not start another worker; readiness checks heartbeat, not success of every provider call. |

On the accepted installation these read-only commands inspected the image bridge
without starting a workload. Internal container names/paths may differ by Docker
Desktop version; if they are absent, inspect Docker Desktop diagnostics instead
of treating them as a universal image-loading interface:

```bash
docker --context desktop-linux desktop kubernetes images list
docker --context desktop-linux inspect kind-registry-mirror --format '{{.Config.Image}}'
docker --context desktop-linux exec desktop-control-plane cat /etc/containerd/certs.d/_default/hosts.toml
docker --context desktop-linux exec desktop-control-plane crictl images --digests
```

## Probes, storage and limits

The API runs as UID/GID 10001, with no privilege escalation or service-account token. The PVC uses fsGroup 10001; verify your CSI driver applies permissions. Startup/liveness probe `/api/health`; readiness `/api/ready` checks catalog/runtime access. It intentionally remains ready when external weather sources fail: missing/stale data is disclosed per response.

Collector readiness/liveness runs `python -m outdoorwise.pipeline.collector_health`, checking a running heartbeat within 1800 seconds. Eight source retry sequences can take many minutes. Source failures must appear in ingestion status rather than cause restart storms. Disk failure stops the worker. SIGTERM allows 180 seconds to finish the current bounded source request.

App requests 100m CPU/256 MiB, limits 1 CPU/1 GiB. Collector requests 100m/128 MiB, limits 500m/512 MiB. These are initial demonstration budgets, not measured capacity guarantees. CSV rewrites and full-history snapshots grow with collected history; monitor memory/disk/cycle duration. A growing dataset may need larger limits and partitioned repository storage.

Back up the PVC with the API/collector stopped or through an application-consistent storage snapshot. Do not delete a PVC as an update mechanism. Scaling requires a coordinated storage/repository design for CSV, account SQLite, per-user JSON, generated routes and sessions; adding replicas is not safe. Required affinity may leave collector pending if the API cannot schedule. Inspect PVC binding, image availability, node capacity and volume permissions first.

For public HTTPS, set `OUTDOORWISE_SECURE_COOKIES: "1"` in the ConfigMap and use an existing TLS ingress/gateway. The supplied ClusterIP + localhost port-forward is an HTTP demonstration configuration, not a public ingress. Restart deployments after updating Secrets/ConfigMaps. Restrict public access and provider quotas before exposure; the existing refresh/ORS/LLM endpoints have no per-user rate limiter.

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
