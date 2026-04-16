# 03 — Cloudera Data Engineering: Quota Management

## Overview

Cloudera Data Engineering (CDE) manages resources through a two-tier quota model: the **CDE Service** (backed by a Kubernetes namespace with a resource pool) and **Virtual Clusters** (logical compute units within a service, each carrying its own guaranteed and maximum quota). All quota configuration is performed in the CDE UI. Do not edit CDE-managed namespace quotas directly in the Management Console.

---

## 1. Quota Model

### 1.1 Tier Structure

```
Resource Pool (Management Console)
└── CDE Service  (namespace-level Kubernetes ResourceQuota)
    ├── Virtual Cluster A  (guaranteed quota + max quota)
    ├── Virtual Cluster B  (guaranteed quota + max quota)
    └── Virtual Cluster C  (guaranteed quota + max quota)
```

- The **CDE Service** consumes a resource pool assignment made at provisioning time. The namespace and its quota objects are created and managed entirely by CDE.
- **Virtual Clusters** are logical partitions within a service. Each virtual cluster receives a guaranteed allocation and a maximum (burst) ceiling.

### 1.2 Quota Dimensions

| Dimension | Unit | Notes |
|-----------|------|-------|
| CPU | Cores | Applied as Kubernetes CPU requests/limits |
| Memory | GiB | Applied as Kubernetes memory requests/limits |
| GPU | Count (whole units) | Applied as Kubernetes extended resource limits; requires GPU node pool |

---

## 2. CDE Service Quota

### 2.1 Service-Level Pool Assignment

When creating a CDE Service in the Management Console or CDE UI:
1. Select the target cluster and assign the service to a resource pool.
2. Set the total CPU, memory, and GPU limits for the service. These become the namespace-level ResourceQuota.
3. The CDE operator creates and manages all Kubernetes namespace objects. **Do not modify these objects directly in the Management Console or via `kubectl`.**

> **Warning:** Manually editing the CDE service namespace quota in the Management Console — or directly modifying the Kubernetes ResourceQuota object — can cause state drift. CDE lifecycle operations (scale, upgrade, delete) may fail or produce unpredictable behavior.

### 2.2 Sizing the Service Quota

The service quota must accommodate the sum of all virtual cluster guaranteed quotas, plus burst headroom for maximum quotas.

| Factor | Guidance |
|--------|----------|
| Sum of guaranteed quotas | Must not exceed service quota |
| Peak burst demand | Service quota ceiling should cover expected peak across all virtual clusters |
| CDE overhead | Reserve 5–10% of service quota for CDE control-plane components (e.g., Airflow scheduler, Spark history server) |

---

## 3. Virtual Cluster Quotas

### 3.1 Guaranteed vs. Maximum Quota

Each virtual cluster has two quota values:

| Parameter | Definition |
|-----------|------------|
| **Guaranteed quota** | Minimum resources reserved for the virtual cluster at all times. These resources are not available to other virtual clusters, even when idle. |
| **Maximum quota** | Upper bound on resources the virtual cluster may consume, including burst beyond the guaranteed amount. |

- Resources between the guaranteed and maximum quota are available on a best-effort (burstable) basis.
- Resources above the maximum quota are never available to the virtual cluster, regardless of cluster capacity.

> **Recommendation:** Set guaranteed quotas to reflect the steady-state workload baseline. Set maximum quotas to reflect peak demand. Avoid setting maximum quotas far above guaranteed; this fragments capacity and makes planning difficult.

### 3.2 Workload Behavior at Quota Boundaries

| Condition | Behavior |
|-----------|----------|
| Spark job fits within guaranteed quota | Job runs immediately; resources are reserved |
| Spark job requires burst (between guaranteed and maximum) | Job runs if burst capacity is available; may queue if other VCs are using it |
| Spark job exceeds maximum quota | Job is rejected or queued indefinitely; does not run |
| Virtual cluster at maximum quota, more jobs submitted | Jobs queue in FIFO order within the virtual cluster |

### 3.3 Configuring Virtual Cluster Quotas

Virtual cluster quotas are set in the CDE UI when creating or editing a virtual cluster:
- Navigate to **CDE Service > Virtual Clusters > Create / Edit**.
- Set CPU and memory for guaranteed and maximum separately.
- For GPU virtual clusters, specify the GPU count in the guaranteed and/or maximum fields.

> **Recommendation:** Create separate virtual clusters for production and development workloads, with different guaranteed and maximum quotas, rather than sharing a single virtual cluster across tiers.

---

## 4. GPU Quota Management in CDE

### 4.1 GPU Allocation Model

GPUs in CDE virtual clusters are allocated per Spark executor pod. Each executor requesting a GPU receives one exclusive GPU unit for the duration of the job. GPUs are returned to the pool when the job completes.

- GPU support in CDE requires a GPU node pool and the appropriate device plugin to be configured at the cluster level. [verify on upgrade]
- GPU quotas are specified per virtual cluster using the same guaranteed/maximum model as CPU and memory.

### 4.2 Recommended GPU Configuration

| Configuration | Recommendation |
|---------------|---------------|
| GPU virtual cluster isolation | Create a dedicated GPU virtual cluster rather than enabling GPU on a general-purpose virtual cluster |
| Guaranteed GPU quota | Match the number of GPU-intensive jobs expected to run concurrently |
| Maximum GPU quota | Set based on total GPU nodes allocated to the CDE service pool |
| Job-level GPU request | Set Spark executor GPU resource request to `1` per executor; do not over-request |

> **Recommendation:** Separate GPU and CPU virtual clusters within the same CDE service. This prevents GPU workloads from consuming CPU quota and vice versa, and simplifies utilization monitoring.

### 4.3 GPU Pool Assignment

Ensure the CDE service resource pool targets nodes with GPU hardware. The Management Console pool assignment must align with the Kubernetes node pool that contains GPU nodes. Without this alignment, GPU jobs will fail to schedule even if the quota allows it.

---

## 5. Autoscaling Interaction

CDE virtual clusters interact with cluster autoscaling as follows:

- Spark jobs submitted to a virtual cluster trigger pod scheduling within the virtual cluster's quota.
- If the virtual cluster's maximum quota allows and the cluster autoscaler has capacity, new GPU or CPU nodes are provisioned to accommodate demand.
- The virtual cluster's maximum quota acts as an autoscaling ceiling: the autoscaler will not provision nodes beyond what the quota permits.
- If the CDE service pool quota is exhausted, autoscaling does not help — new pods are blocked at the namespace ResourceQuota level before the scheduler sees them.

> **Note:** CDE's dynamic resource allocation (DRA) for Spark can return executor resources to the cluster when they are no longer needed. Ensure DRA is enabled for workloads with variable parallelism to improve quota utilization efficiency.

---

## 6. Operational Considerations

### 6.1 Quota Utilization Monitoring

Monitor virtual cluster quota utilization through:
- **CDE UI > Virtual Cluster > Resources**: shows current CPU, memory, and GPU usage vs. guaranteed/maximum.
- **Management Console > Resource Utilization**: shows pool-level aggregates.
- **Kubernetes metrics**: `kubectl top pods -n <cde-namespace>` for real-time pod resource consumption.

### 6.2 Quota Adjustment Process

1. Identify the virtual cluster requiring adjustment in the CDE UI.
2. Verify the parent CDE service has sufficient headroom (service quota minus current sum of all VC maximums).
3. Edit the virtual cluster quota in the CDE UI. Do not modify namespace objects directly.
4. Verify the change is reflected in the Management Console pool utilization view.

---

## 7. Common Pitfalls

| Pitfall | Impact | Mitigation |
|---------|--------|------------|
| Editing CDE namespace quota in Management Console | State drift; CDE lifecycle operations fail | Always use the CDE UI for quota changes |
| Guaranteed quotas sum exceeds service quota | Virtual cluster creation fails | Audit VC guaranteed allocations before adding new VCs |
| No GPU virtual cluster isolation | CPU and GPU jobs compete for quota | Create separate GPU and CPU virtual clusters |
| Maximum quota set too close to guaranteed | No burst capacity; bursty jobs queue unnecessarily | Set maximum 1.5–2× the guaranteed baseline |
| CDE service quota does not include overhead | Control-plane pods evicted or fail to schedule | Reserve 5–10% of service quota for CDE components |

---

## 8. Do's and Don'ts

| Do | Don't |
|----|-------|
| Use the CDE UI for all quota configuration | Edit CDE namespace objects in the Management Console or via kubectl |
| Reserve CDE service quota headroom for control-plane overhead | Allocate 100% of service quota to virtual clusters |
| Create dedicated GPU virtual clusters | Mix GPU and CPU workloads in the same virtual cluster |
| Enable Spark DRA for variable-parallelism jobs | Leave DRA disabled, causing idle executor quota waste |
| Monitor VC utilization before increasing quotas | Increase quotas reactively during production incidents without root cause analysis |
| Document virtual cluster ownership and workload assignments | Create virtual clusters with no owner documentation |

---

## References and Notes

- **[Warning]** CDE manages its namespace ResourceQuota objects programmatically. Manual edits via Management Console or `kubectl` will be overwritten or cause inconsistency during CDE service operations.
- **[Assumption]** GPU support requires a GPU device plugin and appropriate node pool labeling; these are prerequisites managed at the cluster level outside CDE. [verify on upgrade]
- **[Recommendation]** Guaranteed and maximum quota ratio guidance (1.5–2×) is an operational best practice, not a platform-enforced constraint.
- **[Assumption]** CDE Dynamic Resource Allocation availability and configuration may vary by CDE version. Refer to the CDE release notes.
- Refer to the Cloudera Data Engineering documentation for authoritative quota configuration procedures and supported CDP release versions.
