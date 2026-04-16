---
name: cloudera-data-engineering-quota
description: Quota configuration for Cloudera Data Engineering — service pool sizing, virtual cluster guaranteed/max, GPU VC allocation, Airflow overhead, and operational rules.
---

# Skill: Cloudera Data Engineering Quota

## CDE Quota Hierarchy

```
CDE service pool
├── Airflow + API server overhead  ← reserved at service level
├── virtual cluster A (prod-etl)
│   ├── guaranteed quota           ← always available
│   └── maximum quota              ← ceiling, burst only
├── virtual cluster B (dev-ml)
│   ├── guaranteed = 0
│   └── maximum quota
└── virtual cluster C (gpu-training)
    ├── guaranteed = 0
    └── maximum quota (GPU-enabled)
```

## CDE Service Pool Sizing

- The service pool is the container for all virtual clusters in the CDE service.
- Reserve **3–6 vCPU / 12–24 GiB** above the sum of all VC maximums for Airflow,
  the CDE API server, and metadata pods.
- **[IMPORTANT]** CDE-created resource pools must not be modified in the Management
  Console UI. Always use the CDE service UI.

**Minimum service pool formula:**

```
service_pool_max = sum(vc_maximums) + airflow_overhead
service_pool_guaranteed ≥ sum(vc_guaranteeds)
```

## Virtual Cluster Quota Configuration

| VC type | Guaranteed | Maximum | GPU quota | Executor idle timeout |
|---|---|---|---|---|
| Production ETL | Set (e.g., 16 vCPU / 64 GiB) | 1.5–2× guaranteed | No | 10–15 min |
| Streaming / ops | Set (e.g., 8 vCPU / 32 GiB) | 1.2× guaranteed | No | 5 min |
| ML / feature eng | 0 | Sized to peak job | No | 10 min |
| Dev / ad-hoc | 0 | Capped (prevent monopoly) | No | 5–10 min |
| GPU training | 0 | GPU count + matching CPU/mem | Yes | 10 min |

Rules:
- Production VCs must have a non-zero guaranteed quota.
- Dev VCs: guaranteed = 0; they burst from available pool capacity.
- Never set a dev VC maximum equal to the service pool maximum.
- Each major workload class (ETL, streaming, ML, dev) should have its own VC.

## GPU Virtual Cluster Rules

1. The CDE service pool must have GPU quota before a GPU VC can be created.
2. GPU VC maximum specifies the number of GPU devices available to executors.
3. Spark jobs must request GPUs explicitly: `spark.executor.resource.gpu.amount=1`
4. GPU worker nodes must be tainted; GPU pods must tolerate that taint.
5. Set executor idle timeout to prevent GPU executors from sitting idle.

## Executor Idle Timeout

- Idle executor timeout reclaims capacity from VCs that are not actively running jobs.
- **[RECOMMENDATION]** Set to 5–15 minutes depending on job frequency.
  Short timeout = faster reclaim; long timeout = faster job startup (warm executors).
- GPU VCs should use shorter timeouts (5–10 min) to reclaim expensive GPU capacity.

## Do's and Don'ts

| Do | Don't |
|---|---|
| Use the CDE service UI to adjust VC quotas | Edit CDE-created pools in Management Console |
| Set guaranteed quota for production VCs | Set dev VC guaranteed > 0 (wastes reserved capacity) |
| Include Airflow overhead in service pool sizing | Size service pool = sum of VC maximums only |
| Use a dedicated VC per workload class | Run ETL and dev jobs in the same VC |
| Enable executor idle timeout on all VCs | Leave idle timeout disabled on GPU VCs |
| Allocate GPU quota at both service and VC level | Create GPU profiles without GPU quota in parent |

## Common Sizing Starting Point (medium cluster, 48 nodes)

| VC | Guaranteed CPU | Guaranteed Mem | Max CPU | Max Mem |
|---|---|---|---|---|
| vc-etl-daily | 16 vCPU | 64 GiB | 32 vCPU | 128 GiB |
| vc-streaming-ops | 8 vCPU | 32 GiB | 16 vCPU | 64 GiB |
| vc-ml-featureeng | 0 | 0 | 24 vCPU | 96 GiB |
| vc-dev | 0 | 0 | 16 vCPU | 64 GiB |
| CDE service overhead | — | — | +6 vCPU | +24 GiB |
| **Service pool total** | **24 vCPU** | **96 GiB** | **94 vCPU** | **376 GiB** |
