# 03 — Cloudera Data Engineering: Quota Management

## 3.1 Overview

Cloudera Data Engineering (CDE) uses a two-level resource model:

1. **CDE Service** — a logical grouping backed by a Kubernetes namespace and a resource
   pool allocated from the cluster. The service defines the overall resource ceiling for
   all virtual clusters beneath it.
2. **Virtual Cluster (VC)** — an isolated Spark execution environment within a CDE
   service. Each virtual cluster has its own CPU and memory quotas (guaranteed and maximum),
   and optionally a GPU quota.

Quota management for CDE is performed through the **CDE service UI** and the
**Management Console**. Sub-pools created by CDE should not be edited directly in the
Management Console UI.

> **Important:** If a CDE service or virtual cluster was created through the CDE service
> UI, its resource pool configuration must be managed through the same UI. Editing CDE-
> created pools directly in the Management Console can cause inconsistency between the
> CDE metadata and the underlying Kubernetes resource quotas, potentially breaking
> the virtual cluster or causing unexpected scheduling behavior.

---

## 3.2 CDE Service Resource Pool

When a CDE service is created, the Management Console provisions a Kubernetes namespace
and a resource pool for that service from the parent cluster pool. This service-level
pool is the aggregate ceiling for all virtual clusters within the service.

| Parameter | Description |
|---|---|
| CPU minimum (guaranteed) | Minimum CPU cores permanently reserved for the service |
| CPU maximum | Hard ceiling for all workloads in the service |
| Memory minimum (guaranteed) | Minimum memory permanently reserved |
| Memory maximum | Hard ceiling for memory usage |
| GPU quota (optional) | GPU devices available to virtual clusters in this service |

**Best practices for CDE service sizing:**

- Size the service pool to accommodate the sum of all virtual cluster maximums plus
  a buffer for CDE control-plane components (Airflow scheduler, API server, etc.).
- Allocate separate CDE services for production and non-production workloads.
  Sharing a service between environments risks resource contention during prod peak hours.
- If multiple business units run CDE workloads, consider a service per unit, or at
  minimum a virtual cluster per unit with enforced quotas.

---

## 3.3 Virtual Cluster Quota Configuration

Each virtual cluster has independent CPU and memory quotas. CDE supports two quota modes:

| Mode | Description | When to use |
|---|---|---|
| **Guaranteed (minimum)** | Resources always available to the VC, regardless of overall load | SLA-critical production pipelines |
| **Maximum** | Resources available when free; VC is throttled to this ceiling under contention | Development, ad-hoc, burst workloads |

**Example virtual cluster allocation within a CDE service:**

Service pool: 400 vCPU / 3,200 GiB (total ceiling)

| Virtual Cluster | CPU Guaranteed | CPU Max | RAM Guaranteed | RAM Max | Purpose |
|---|---|---|---|---|---|
| vc-etl-prod | 100 vCPU | 150 vCPU | 800 GiB | 1,200 GiB | Production ETL |
| vc-streaming-prod | 80 vCPU | 120 vCPU | 640 GiB | 960 GiB | Production streaming |
| vc-reporting-prod | 40 vCPU | 80 vCPU | 320 GiB | 640 GiB | Scheduled reports |
| vc-dev | 0 vCPU | 100 vCPU | 0 GiB | 800 GiB | Developer experimentation |
| vc-ml-feature-eng | 20 vCPU | 60 vCPU | 160 GiB | 480 GiB | Feature engineering |
| CDE control plane | ~20 vCPU | ~30 vCPU | ~160 GiB | ~240 GiB | Airflow, API, metadata |
| **Headroom** | — | ~40 vCPU | — | ~320 GiB | Burst buffer |

> Sum of guaranteed values (240 vCPU) should not exceed the service pool guaranteed value.
> Sum of maximums (540 vCPU) may exceed the service pool maximum — this is intentional
> (statistical multiplexing), but ensure the service pool maximum is the hard stop.

---

## 3.4 GPU Quota in CDE

CDE supports GPU allocation at the virtual cluster level for GPU-accelerated Spark
workloads (e.g., RAPIDS, GPU UDFs).

**GPU quota allocation guidance:**

1. **Create a GPU-enabled virtual cluster only within a CDE service that has GPU quota
   allocated.** GPU workloads scheduled in a non-GPU virtual cluster will fail at runtime.

2. **Specify GPU quota explicitly** when creating the virtual cluster. The GPU count
   defines the maximum number of GPU devices available to executors within the VC.

3. **Do not mix GPU and CPU-only workloads in the same virtual cluster** unless you
   have carefully characterized demand. GPU workloads that request GPUs block those
   devices for the lifetime of the Spark executor, even if the GPU is not actively used.

4. **Set GPU maximum conservatively.** GPU over-allocation does not cause failures at
   VC creation time but will cause job failures at runtime when the GPU device is not
   physically available.

5. **[RECOMMENDATION]** Allocate a dedicated VC for GPU workloads per team or use case,
   rather than a shared GPU VC. This simplifies quota accounting and chargeback.

**Insufficient GPU quota behavior:**
If a Spark job requests GPU executors and the virtual cluster has reached its GPU
maximum, the job's GPU stages will queue until GPU devices are released. The job does
not fail immediately but may time out if GPUs are never freed.

---

## 3.5 Autoscaling in CDE

CDE virtual clusters support autoscaling of Spark executors within the VC's quota bounds:

- When a Spark job submits, CDE allocates executors up to the VC's maximum CPU/memory.
- When jobs complete, executors scale down after an idle timeout (configurable per VC).
- The VC never scales beyond its maximum quota, regardless of overall cluster availability.
- If multiple jobs are queued, Spark's dynamic allocation shares the VC's capacity
  across concurrent jobs.

**Autoscaling best practices:**

- Set executor idle timeout appropriately. A low timeout (e.g., 30 s) returns resources
  quickly but incurs overhead from frequent scale-up/down. A high timeout (e.g., 5 min)
  improves throughput for bursty workloads but holds capacity longer.
- Monitor queue depth in the CDE UI. Persistent queue depth signals that the VC
  maximum or the service pool is undersized for the workload.
- **[RECOMMENDATION]** Enable job-level resource requests in job definitions
  (driver CPU/memory, executor CPU/memory) so jobs self-describe their requirements
  and the scheduler can make informed placement decisions.

---

## 3.6 Airflow and Control-Plane Resource Needs

Each CDE service runs an Airflow instance for job orchestration. Airflow (scheduler,
webserver, metadata database) consumes resources from the CDE service pool.

**Do not size the service pool to exactly the sum of virtual cluster quotas.** Always
include overhead for:

| Component | Approximate overhead |
|---|---|
| Airflow scheduler | 1–2 vCPU / 4–8 GiB |
| Airflow webserver | 0.5–1 vCPU / 2–4 GiB |
| CDE API server | 0.5–1 vCPU / 2–4 GiB |
| Metadata / auxiliary pods | 1–2 vCPU / 4–8 GiB |
| **Total overhead (estimate)** | **3–6 vCPU / 12–24 GiB** |

> **[ASSUMPTION]** Exact resource consumption of CDE control-plane components varies
> by CDE version and configuration. The values above are estimates; verify with
> `kubectl top pods -n <cde-namespace>` against your running service.

---

## 3.7 CDE Quota Management: Do's and Don'ts

**Do:**
- Size each virtual cluster based on measured job profiling, not intuition.
- Set guaranteed quota only for production VCs that have SLA requirements.
- Use a separate VC for each major workload class (ETL, streaming, ML feature engineering).
- Leave headroom in the service pool for control-plane components and burst.
- Monitor VC utilisation in the CDE UI and right-size quarterly.
- Name VCs and services descriptively (e.g., `cde-finance-prod`, `vc-daily-reconciliation`).

**Don't:**
- Edit CDE-created resource pools in the Management Console UI.
- Create GPU-enabled VCs unless the parent CDE service has GPU quota.
- Set all VC guaranteed values to their maximums — this wastes capacity during off-peak.
- Share a single VC between production and development jobs.
- Ignore Airflow / control-plane overhead when sizing the service pool.

---

## 3.8 Common Pitfalls

| Pitfall | Impact | Mitigation |
|---|---|---|
| Editing CDE pools in Management Console | VC enters inconsistent state; may fail to scale | Always use CDE service UI for VC quota changes |
| Service pool too small for VC sum + overhead | Airflow or API server starved; jobs fail to submit | Add 15–20% buffer to service pool over VC total |
| GPU VC created without GPU service quota | Jobs fail at runtime with no device error | Verify service pool GPU quota before creating GPU VC |
| All VCs share same guaranteed quota | Production jobs compete with dev during peak | Separate guaranteed pools per environment |
| No idle executor timeout | Executors hold capacity for hours after job completion | Set executor idle timeout per VC (30 s–5 min) |

---

## References and Notes

- CDE virtual cluster quota management is described in the Cloudera Data Engineering
  documentation for your CDP Private Cloud Data Services release.
- **[IMPORTANT]** The restriction on editing CDE-created pools in the Management Console
  is explicitly documented by Cloudera. Always use the CDE service UI for VC quota changes.
- **[ASSUMPTION]** GPU quota fields in the CDE virtual cluster creation wizard are available
  in CDE 1.x on CDP Private Cloud. Verify field availability in your release.
- Airflow overhead estimates are based on typical deployments; actual consumption
  depends on DAG count, concurrency settings, and CDE version.
