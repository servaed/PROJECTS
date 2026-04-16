# 04 — Cloudera Data Warehouse: Quota Management

## Overview

Cloudera Data Warehouse (CDW) manages resources through a namespace-based quota model. Each CDW component — Database Catalog, Virtual Warehouse (Hive or Impala), and Data Visualization instance — runs in its own Kubernetes namespace, and CDW creates and manages the associated resource pool assignments and Kubernetes quota objects. Autoscaling is a core part of the CDW resource model and interacts directly with quota boundaries.

---

## 1. Quota Model

### 1.1 Component Namespace Structure

```
Resource Pool (Management Console)
└── CDW Environment  (top-level namespace + resource pool)
    ├── Database Catalog  (namespace + resource pool)
    ├── Virtual Warehouse A — Hive  (namespace + resource pool)
    ├── Virtual Warehouse B — Impala  (namespace + resource pool)
    └── Data Visualization Instance  (namespace + resource pool)
```

Each CDW component occupies a dedicated Kubernetes namespace. CDW creates and manages the namespace, the associated ResourceQuota, and the resource pool assignment. **Do not manually modify CDW namespace quotas in the Management Console.**

### 1.2 Quota Dimensions

| Dimension | Unit | Notes |
|-----------|------|-------|
| CPU | Cores | Applied as Kubernetes CPU requests/limits |
| Memory | GiB | Applied as Kubernetes memory requests/limits |
| GPU | Count (whole units) | Not typically used in CDW; applies only if GPU-accelerated query nodes are deployed |

---

## 2. CDW Environment and Pool Assignment

### 2.1 Environment-Level Pool

When activating a CDW environment in the Management Console:
1. Select the target Kubernetes cluster.
2. Assign the CDW environment to a resource pool. CDW creates a top-level namespace for the environment within this pool.
3. All CDW components (Database Catalogs, Virtual Warehouses) created within the environment inherit their quota from this pool hierarchy.

> **Warning:** Do not modify CDW-managed namespace ResourceQuota objects in the Management Console or via `kubectl`. CDW manages these objects throughout the component lifecycle (create, scale, upgrade, delete). Manual changes cause state drift.

### 2.2 Pool Sizing for the CDW Environment

Size the CDW environment pool to accommodate:
- The sum of all active Virtual Warehouse CPU and memory allocations at maximum scale.
- Database Catalog metadata service overhead.
- Data Visualization instance resource requirements.
- CDW control-plane component overhead (typically 5–10% of environment pool).

---

## 3. Virtual Warehouse Quotas and Autoscaling

### 3.1 Virtual Warehouse Types

CDW supports two Virtual Warehouse (VW) types, each with different autoscaling behavior:

| Type | Query Engine | Autoscaling Model |
|------|-------------|-------------------|
| Hive | Apache Hive on Tez | Scales executor pods based on query queue depth |
| Impala | Apache Impala | Scales coordinator and executor pods based on concurrent query demand |

### 3.2 Autoscaling Configuration

Each Virtual Warehouse has two scale parameters:

| Parameter | Definition |
|-----------|------------|
| **Minimum nodes** | The minimum number of nodes (or pods) the VW maintains. Determines the baseline resource consumption. |
| **Maximum nodes** | The upper bound on nodes the VW may scale to. Combined with node size, this determines the maximum quota consumed. |

> **Recommendation:** Set minimum nodes to the lowest value that meets SLA requirements for cold-start query latency. Setting minimum nodes too high reserves capacity unnecessarily; setting too low increases cold-start time.

### 3.3 Autoscaling and Quota Interaction

- When a Virtual Warehouse scales out, new pods are created in its namespace, consuming quota from the namespace ResourceQuota.
- If the namespace quota is exhausted, scale-out is blocked — new pods remain in `Pending` state, and queries queue or fail depending on VW configuration.
- The maximum node count configuration in the CDW VW UI acts as a soft ceiling within the CDW model, but the Kubernetes namespace quota acts as the hard ceiling.
- If the cluster autoscaler is enabled, scale-out can provision new nodes, but only up to the namespace quota limit.

> **Note:** CDW quota limits and Kubernetes namespace quota limits must be consistent. If the CDW VW is configured for 10 nodes maximum but the namespace quota only allows 5 nodes worth of CPU/memory, the effective ceiling is 5 nodes.

### 3.4 Scale-In Behavior

- CDW Virtual Warehouses scale in when query load drops below the threshold that justifies the current node count.
- Scale-in is subject to a configurable delay to prevent oscillation during bursty workloads.
- Scale-in to zero (full suspension) is supported for some VW configurations and can be used to reclaim quota when the VW is not in use. [verify on upgrade]

### 3.5 Configuring Virtual Warehouse Quotas

Virtual Warehouse resource configuration is managed in the CDW UI:
- Navigate to **Virtual Warehouse > Edit**.
- Set node size (CPU and memory per node).
- Set minimum and maximum node counts.
- The effective quota range is: `node_size × min_nodes` (baseline) to `node_size × max_nodes` (maximum).

---

## 4. Database Catalog Quotas

### 4.1 Database Catalog Resource Consumption

The Database Catalog runs the Hive Metastore (HMS) and associated metadata services. It does not execute analytical queries but is required for all Hive Virtual Warehouses and for Impala VWs that use Hive Metastore for metadata.

- The Database Catalog namespace receives a fixed resource allocation at provisioning time.
- It does not autoscale in the same way as Virtual Warehouses.
- Resource requirements are primarily driven by the number of databases, tables, and partitions in the metastore, and by the number of concurrent metadata operations.

### 4.2 Sizing the Database Catalog

| Factor | Guidance |
|--------|----------|
| Number of Hive tables and partitions | More partitions increase HMS memory requirements |
| Number of concurrent VWs sharing the catalog | More VWs increase HMS CPU and connection load |
| Metastore backend database | PostgreSQL or MySQL; size appropriately for the partition count |

> **Recommendation:** Start with the default Database Catalog sizing and monitor HMS memory usage under load. Increase the namespace quota if HMS restarts or exhibits OOM conditions.

---

## 5. Data Visualization Quotas

### 5.1 Data Visualization Resource Model

Cloudera Data Visualization (CDV) instances run in their own namespace within the CDW environment. CDV is a web application serving dashboards and visualizations; its resource requirements are driven by:
- Number of concurrent users.
- Complexity and frequency of dashboard queries.
- Number of configured data connections.

### 5.2 Sizing Data Visualization Instances

| Factor | Guidance |
|--------|----------|
| Concurrent dashboard viewers | Drives web server CPU and memory |
| Background query execution | Drives executor CPU and memory |
| Caching configuration | In-memory caching increases memory requirements |

> **Recommendation:** Allocate Data Visualization instances a dedicated pool with fixed quota rather than sharing the pool with compute-intensive Virtual Warehouses. CDV traffic patterns (many small queries, interactive users) differ from bulk analytical workloads.

---

## 6. Autoscaling Best Practices

### 6.1 Autoscaling vs. Quota Relationship

| Principle | Details |
|-----------|---------|
| Quota ceiling must align with maximum scale | Set namespace quota to accommodate `max_nodes × node_size` plus overhead |
| Do not over-provision maximum scale | Setting max nodes too high wastes quota and node pool capacity |
| Align autoscaler node pool limits | The Kubernetes cluster autoscaler node pool maximum must be ≥ the sum of all VW maximum node counts in the pool |
| Monitor scale events | Track scale-out frequency; frequent scale-outs to maximum suggest the maximum needs increasing |

### 6.2 Autoscaling Do's and Don'ts

| Do | Don't |
|----|-------|
| Align CDW VW max nodes with namespace quota | Set max nodes higher than the namespace quota allows |
| Set scale-in delay appropriate to query patterns | Use aggressive scale-in for SLA-sensitive VWs |
| Test cold-start latency before setting min nodes to 0 | Assume min-0 is safe for all VWs without testing latency impact |
| Monitor VW utilization metrics for sizing validation | Set max nodes and never review against actual peak usage |

---

## 7. Common Pitfalls

| Pitfall | Impact | Mitigation |
|---------|--------|------------|
| Manually editing CDW namespace quotas | State drift; CDW lifecycle operations fail | Always use the CDW UI for quota and scaling configuration |
| VW max nodes exceeds namespace quota | VW cannot reach configured maximum scale | Align namespace quota with VW max node configuration |
| All VWs at maximum scale simultaneously | Total pool quota exhausted; some VWs blocked from scaling | Size the CDW environment pool for expected peak aggregate demand, not worst-case simultaneous maximums |
| Database Catalog undersized | HMS OOM restarts; metadata operations fail | Monitor HMS memory and increase namespace quota proactively |
| Data Visualization sharing pool with heavy VWs | CDV users experience latency during peak VW scaling | Assign CDV to a separate sub-pool |

---

## 8. Do's and Don'ts

| Do | Don't |
|----|-------|
| Use the CDW UI for all VW and catalog configuration | Modify CDW namespace ResourceQuota objects in the Management Console or kubectl |
| Size the CDW environment pool for aggregate peak demand | Assume individual VW maximums will never overlap |
| Create separate pools for production and development CDW environments | Share a single pool across all CDW environments |
| Monitor scale-out events and adjust VW sizing accordingly | Ignore autoscaler events until a production incident |
| Assign Data Visualization to a separate sub-pool | Co-locate CDV with compute-heavy VWs without dedicated quota |
| Validate Database Catalog sizing under representative load | Apply default HMS sizing without testing under actual partition counts |

---

## 9. Troubleshooting

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| Virtual Warehouse fails to scale out | Namespace quota or pool quota exhausted | Check CDW VW resource usage; check Management Console pool utilization; increase namespace or pool quota |
| Queries queuing despite available nodes | VW at max scale; namespace quota ceiling reached | Review max node configuration vs. namespace quota; increase if needed |
| Database Catalog repeatedly restarting | HMS OOM; insufficient memory quota | Increase Database Catalog namespace memory quota via CDW UI |
| Data Visualization dashboards slow to load | CDV namespace CPU or memory constrained | Check CDV pod resource usage; increase namespace quota |
| CDW component creation fails | Parent pool lacks capacity | Check Management Console pool utilization; increase pool or add nodes |

---

## References and Notes

- **[Warning]** CDW manages namespace ResourceQuota objects programmatically. Manual edits will be overwritten or cause inconsistency during CDW operations.
- **[Assumption]** Scale-to-zero behavior for Virtual Warehouses is available in select CDW versions; verify feature availability for your CDP release. [verify on upgrade]
- **[Assumption]** Database Catalog sizing guidance is based on general Hive Metastore operational practice. Actual sizing depends on partition count, query patterns, and CDP version.
- **[Recommendation]** All sizing guidelines are operational best practices, not platform-enforced constraints.
- Refer to the Cloudera Data Warehouse documentation for authoritative Virtual Warehouse configuration and autoscaling procedures.
