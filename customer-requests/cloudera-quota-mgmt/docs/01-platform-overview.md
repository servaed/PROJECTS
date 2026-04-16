# 01 — Platform-Level Resource Pool Model

## Overview

Cloudera Data Services on-premises runs on Kubernetes and uses a hierarchical resource pool model to partition cluster capacity across services, business units, and workload tiers. Understanding this model is a prerequisite for configuring quotas in any individual data service.

---

## 1. How Resource Pools Work

### 1.1 Hierarchical Structure

Resource pools form a tree. Each pool defines a quota (CPU, memory, GPU) that is carved from its parent pool. A child pool cannot be allocated more resources than its parent allows.

```
Cluster Capacity (total node pool)
└── Default Pool  (root pool — the standard node pool)
    ├── Production Pool
    │   ├── CAI-Prod Pool
    │   ├── CDE-Prod Pool
    │   └── CDW-Prod Pool
    └── Non-Production Pool
        ├── CAI-Dev Pool
        ├── CDE-Dev Pool
        └── CDW-Dev Pool
```

> **Recommendation:** Always subdivide the default pool into at least production and non-production tiers before provisioning any data service.

### 1.2 The Default Pool

The **default pool** is the standard node pool created when a cluster is registered in the Management Console. It represents the full schedulable capacity of the cluster (minus reserved system capacity). It can be subdivided into child pools to allocate resources to different services or tenants.

- All newly registered clusters start with a single default pool.
- Child pools are created within the Management Console under **Resource Utilization > Resource Pools**.
- The sum of all child pool allocations must not exceed the parent pool's total quota.

### 1.3 Quota Dimensions

Each resource pool enforces three quota dimensions:

| Dimension | Unit | Notes |
|-----------|------|-------|
| CPU | Cores (or millicores) | Applied as Kubernetes CPU requests/limits |
| Memory | GiB | Applied as Kubernetes memory requests/limits |
| GPU | Count (whole units) | Applied as Kubernetes extended resource limits |

All three dimensions are independently configurable. A pool can enforce CPU and memory without restricting GPU, or vice versa.

---

## 2. Management Console vs. Data Service UIs

### 2.1 Division of Responsibility

| Action | Where to Perform |
|--------|-----------------|
| Create / modify top-level resource pools | Management Console |
| View cluster-level pool utilization | Management Console |
| Set CAI workspace and user/team quotas | Cloudera AI UI |
| Set CDE service and virtual cluster quotas | CDE UI |
| Set CDW Virtual Warehouse and namespace quotas | CDW UI |
| Monitor per-service resource consumption | Data service UI or Management Console |

> **Warning:** Do not edit quotas for namespaces created by CDE or CDW directly in the Management Console. These namespaces are lifecycle-managed by their respective services. Manual edits in the Management Console can cause state drift and break service operations such as scaling, upgrades, and deletion.

### 2.2 Management Console Capabilities

The Management Console provides:
- Cluster-level resource pool tree visualization.
- Aggregate CPU, memory, and GPU utilization per pool.
- Pool creation, renaming, and deletion (for pools not managed by a data service).
- Assignment of data service namespaces to pools.

It does **not** expose per-workload or per-user quota controls — those are managed within each data service.

---

## 3. Quota Hierarchy: Recommended Design

### 3.1 Example Hierarchy

```
Default Pool  [Total: 1000 CPU, 4000 GiB RAM, 16 GPU]
├── Control-Plane Reserve  [100 CPU, 400 GiB RAM, 0 GPU]  ← never allocated to workloads
├── Production  [600 CPU, 2400 GiB RAM, 12 GPU]
│   ├── CAI-Prod       [200 CPU, 800 GiB RAM, 8 GPU]
│   ├── CDE-Prod       [250 CPU, 1000 GiB RAM, 4 GPU]
│   └── CDW-Prod       [150 CPU, 600 GiB RAM, 0 GPU]
└── Non-Production  [300 CPU, 1200 GiB RAM, 4 GPU]
    ├── CAI-Dev        [100 CPU, 400 GiB RAM, 2 GPU]
    ├── CDE-Dev        [100 CPU, 400 GiB RAM, 2 GPU]
    └── CDW-Dev        [100 CPU, 400 GiB RAM, 0 GPU]
```

### 3.2 Design Principles

- **Reserve control-plane headroom.** Allocate 10–20% of total cluster capacity to a control-plane reserve pool that is never assigned to workloads. This ensures Kubernetes system components, Management Console agents, and CDP control-plane services always have resources.
- **Separate production and non-production at the top level.** This prevents development workloads from starving production services.
- **Assign GPU pools explicitly.** Create dedicated GPU sub-pools only where GPU workloads are expected. Leaving GPUs in the default pool without explicit allocation makes GPU capacity opaque and can lead to contention.
- **Size child pools conservatively.** Start with smaller allocations and expand as workloads are onboarded. Over-allocating up front leads to fragmentation and stranded capacity.

---

## 4. Insufficient Quota Behavior

### 4.1 What Happens When Quota Is Exhausted

When a data service attempts to create or scale a component and the requested resources exceed the available quota in the assigned pool, the following behaviors occur:

| Scenario | Behavior |
|----------|----------|
| Creating a new Virtual Warehouse (CDW) | Creation fails with an error indicating insufficient quota in the target pool |
| Creating a new CDE virtual cluster | Creation fails; the CDE UI displays a quota-exceeded message |
| Creating a new CAI workspace | Creation fails if the parent pool does not have sufficient CPU/memory/GPU |
| Autoscaling a Virtual Warehouse | Scale-out is blocked at the pool quota ceiling; existing workloads continue running |
| Submitting a Spark job (CDE) | Job queues or fails at the virtual cluster quota ceiling depending on configuration |
| Starting a CAI session or application | Session start fails if user or workspace quota is exhausted |

> **Note:** Quota exhaustion at the pool level is distinct from quota exhaustion at the Kubernetes namespace level. Pool-level exhaustion blocks service UI operations. Namespace-level exhaustion blocks pod scheduling and results in pods remaining in `Pending` state.

### 4.2 Diagnosing Quota Exhaustion

1. **Check the data service UI** for explicit quota-exceeded error messages.
2. **Check the Management Console** Resource Utilization view to see current pool consumption vs. limit.
3. **Check Kubernetes events** in the affected namespace: `kubectl describe namespace <ns>` and `kubectl get events -n <ns>` will surface ResourceQuota admission rejections.
4. **Check pod status**: `kubectl get pods -n <ns>` — pods stuck in `Pending` with `Insufficient cpu` or `Insufficient memory` events indicate namespace-level quota exhaustion.

### 4.3 Resolution Steps

- Increase the quota of the affected pool in the Management Console (if parent pool has headroom).
- Increase the quota of a child pool or virtual cluster within the data service UI.
- Reduce quota allocated to another component in the same pool to free capacity.
- Add nodes to the cluster and expand the parent pool accordingly.

> **Recommendation:** Set up alerting on pool utilization thresholds (e.g., 80% consumed) before exhaustion occurs. Reactive quota changes during production incidents carry higher risk.

---

## 5. Capacity Planning

### 5.1 Sizing Inputs

Before assigning quotas, gather the following inputs per service and environment tier:

| Input | Description |
|-------|-------------|
| Number of concurrent users / jobs | Drives CPU and memory sizing |
| Workload peak-to-average ratio | Determines burst headroom needed |
| GPU workload requirements | Number of concurrent GPU sessions or jobs |
| SLA requirements | Determines whether guaranteed quota is needed |
| Growth forecast (6–12 months) | Prevents premature quota exhaustion |

### 5.2 Sizing Guidelines

- **CPU**: Allocate based on peak concurrent workload CPU requests, plus 20–30% burst margin.
- **Memory**: Memory is typically the binding constraint. Size based on peak concurrent memory requests, plus 15–20% margin.
- **GPU**: Allocate whole GPU units only. GPUs are exclusively assigned per workload in standard configurations. Do not over-commit GPU pools.
- **Control-plane reserve**: Minimum 10% of total cluster CPU and memory; increase to 15–20% for clusters with many active namespaces.

### 5.3 Review Cadence

- Review pool utilization monthly during steady state.
- Review quarterly against growth forecasts and upcoming workload onboarding.
- Review immediately following any major incident involving quota exhaustion.

---

## 6. Do's and Don'ts

| Do | Don't |
|----|-------|
| Create a dedicated control-plane reserve pool | Allocate 100% of cluster capacity to workload pools |
| Separate production and non-production pools | Mix prod and non-prod workloads in the same pool |
| Define GPU pools explicitly | Leave GPU resources unallocated in the default pool |
| Monitor pool utilization and set alerts | Wait for quota exhaustion to trigger a review |
| Document pool ownership and quota rationale | Leave pools unnamed or undocumented |
| Use the data service UI for service quotas | Manually edit CDE/CDW namespace quotas in Management Console |
| Expand pools incrementally as workloads grow | Pre-allocate maximum capacity before workloads are onboarded |

---

## References and Notes

- **[Assumption]** The 10–20% control-plane headroom recommendation is based on general Kubernetes operational practice; Cloudera documentation may specify different values for specific cluster sizes.
- **[Assumption]** GPU allocation is described as whole-unit exclusive; fractional GPU sharing is not a standard CDP feature as of the time of writing.
- **[Recommendation]** All sizing guidelines in Section 5 are operational best practices, not product-enforced constraints.
- Cloudera Management Console documentation: refer to the CDP Private Cloud Data Services Administration Guide for authoritative pool management procedures.
- Kubernetes ResourceQuota reference: [kubernetes.io/docs/concepts/policy/resource-quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
