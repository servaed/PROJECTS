# 04 — Cloudera Data Warehouse: Quota Management

## 4.1 Overview

Cloudera Data Warehouse (CDW) on premises creates and manages a hierarchy of Kubernetes
resource pools for each component it provisions. When CDW activates an environment,
creates a Database Catalog, provisions a Virtual Warehouse, or deploys a Data Visualization
instance, it automatically creates corresponding resource pools and namespaces in Kubernetes.

**CDW manages its own resource pool sub-tree.** Administrators must not edit CDW-created
resource pools directly in the Management Console UI. All quota changes for CDW
components must be made through the CDW UI.

> **Critical rule:** Resource pools created by the CDW service for its environments,
> Database Catalogs, Virtual Warehouses, and Data Visualization instances are owned by
> CDW. Editing these pools outside the CDW UI can corrupt the CDW metadata state and
> cause provisioning or scaling failures.

---

## 4.2 CDW Resource Pool Hierarchy

When CDW provisions components, it creates nested namespaces and resource pools:

```
cluster default pool
└── cdw-<environment-name>              ← CDW environment namespace + pool
    ├── cdw-<env>-shared                ← Shared CDW services (Hue, HMS, etc.)
    ├── db-catalog-<name>               ← Database Catalog namespace + pool
    ├── vw-hive-<name>                  ← Hive Virtual Warehouse namespace + pool
    ├── vw-impala-<name>                ← Impala Virtual Warehouse namespace + pool
    └── dataviz-<name>                  ← Data Visualization instance namespace + pool
```

Each namespace has its own resource quota reflecting the sizing configured in the CDW UI.

---

## 4.3 CDW Environment Resource Pool

The CDW environment pool is the root pool for all CDW workloads in a given environment
(production, staging, etc.). It is created when the environment is activated.

**Environment pool sizing guidance:**

- The environment pool must be large enough to accommodate:
  - All Database Catalogs in the environment
  - All Virtual Warehouses (at their maximum configured size)
  - All Data Visualization instances
  - CDW shared services (Hue, Hive Metastore, autoscaling controller)
- Shared services typically consume 10–15% of the environment pool.
- **[RECOMMENDATION]** Add 15–20% headroom beyond the sum of component maximums
  to absorb CDW internal scaling operations.

---

## 4.4 Database Catalog Resource Pool

A Database Catalog (Hive Metastore + associated services) is provisioned with its own
namespace and resource pool. It is shared by all Virtual Warehouses in the environment
that use it.

**Sizing considerations:**

- Database Catalog resource consumption grows with the number of concurrent Virtual
  Warehouses and the volume of metadata operations.
- For environments with many large Virtual Warehouses or high metadata query rates,
  allocate a larger Database Catalog pool.
- **[RECOMMENDATION]** Do not share a single Database Catalog between production and
  development environments. Use separate Database Catalogs for isolation.

---

## 4.5 Virtual Warehouse Resource Pools

Virtual Warehouses (Hive LLAP or Impala) are the primary query execution environments
in CDW. Each Virtual Warehouse has its own namespace and resource pool.

### Sizing a Virtual Warehouse

Virtual Warehouse size (number of executor nodes or clusters) is configured in the CDW
UI when the VW is created. This determines the resource pool ceiling.

| VW Type | Key resource parameters |
|---|---|
| **Hive LLAP** | Number of executors, executor memory, driver memory |
| **Impala** | Number of coordinators, number of executors per cluster, executor memory |

**Sizing best practices:**

- Start with the smallest size that meets the baseline concurrency requirement.
  CDW autoscaling (see 4.6) handles burst.
- Allocate dedicated VWs for workload classes with different SLAs:
  - Interactive BI (low latency, high concurrency)
  - Batch reporting (high throughput, tolerant of latency)
  - Data engineering queries (large scans, infrequent)
- Do not size a VW to consume the entire environment pool maximum — this leaves no
  capacity for the Database Catalog or other VWs in the same environment.

**Multi-tenant VW isolation:**

| Pattern | Use case |
|---|---|
| One VW per business unit | Hard isolation; each BU gets dedicated capacity |
| One VW per workload type | Shared capacity but SLA differentiation by query type |
| Workload management (WM) rules within a VW | Resource pools inside a single VW for query prioritization |

> **Note:** Impala and Hive both support internal workload management (query queues,
> admission control). These operate within the VW's resource pool and are separate from
> the Kubernetes resource quota. See CDW workload management documentation for details.

---

## 4.6 CDW Autoscaling Behavior

CDW Virtual Warehouses support automatic scaling of executor capacity based on query load.

**How it works:**

1. When query concurrency or queue depth increases, CDW scales up executor pods
   within the VW's resource pool.
2. When load decreases and executor pods are idle beyond the configured timeout,
   CDW scales down.
3. Scaling is bounded by the VW's resource pool maximum. CDW cannot scale beyond
   what the resource pool allows.
4. If the VW pool is exhausted and the parent environment pool has headroom,
   **[ASSUMPTION]** CDW may expand the VW pool temporarily up to the environment pool
   maximum. Verify this behavior in your CDW release notes.

**Autoscaling configuration parameters (in CDW UI):**

| Parameter | Description |
|---|---|
| Minimum clusters / executors | Floor; CDW never scales below this |
| Maximum clusters / executors | Ceiling; CDW never scales beyond this |
| Scale-up threshold | Query queue depth or wait time that triggers scale-up |
| Scale-down idle timeout | Time before idle capacity is released |

**Best practices:**

- Set minimum clusters > 0 for production VWs to eliminate cold-start latency.
  A minimum of 1 cluster ensures a baseline executor is always ready.
- Set maximum clusters based on the VW resource pool maximum, not the environment
  pool maximum. CDW does not enforce this automatically — the administrator is responsible.
- Monitor autoscaling events. Frequent rapid scale-up and scale-down cycles may indicate
  workload spikes that are better served by pre-warming or batch scheduling.

---

## 4.7 Data Visualization Instance Resource Pool

CDW Data Visualization (Data Viz) instances run within their own namespace and resource pool.
Data Viz is typically a persistent service (unlike VWs, which scale to zero when idle).

**Sizing guidance:**

- Data Viz instances are relatively lightweight compared to VWs. Typical allocation:
  2–4 vCPU / 8–16 GiB for a shared multi-user instance.
- **[RECOMMENDATION]** Allocate a dedicated Data Viz instance per environment (prod/dev)
  rather than sharing one instance across environments.
- Do not undersize Data Viz; insufficient memory causes dashboard rendering failures
  when many users access the instance concurrently.
- Data Viz is not a query engine — it delegates queries to the connected VW.
  Size the Data Viz instance for UI serving, not query execution.

---

## 4.8 Insufficient Quota: CDW-Specific Behavior

When CDW cannot fit a component into the available resource pool:

| Scenario | Behavior |
|---|---|
| VW creation requested; environment pool has insufficient headroom | CDW returns an error at creation time; VW is not created |
| VW autoscale up; VW pool at maximum | Autoscaling stops; new queries queue in admission control |
| VW autoscale up; environment pool at maximum but VW pool has headroom | **[ASSUMPTION]** Scale-up is blocked at the environment pool boundary; queries queue |
| Database Catalog starved of resources | Metadata queries slow; VW query planning degrades; may surface as slow query starts |

**Handling insufficient quota:**
1. Check the CDW UI environment overview for pool utilisation.
2. If a VW pool is exhausted, increase the VW maximum (CDW UI → VW settings → resize).
3. If the environment pool is exhausted, increase the environment pool allocation
   (Management Console → resource pools → CDW environment pool). Note: this reduces
   available capacity for other services.
4. If total cluster capacity is exhausted, capacity planning or hardware expansion is
   required.

---

## 4.9 CDW Quota Management: Do's and Don'ts

**Do:**
- Set VW minimums > 0 for production workloads (eliminates cold-start latency).
- Size the environment pool as the sum of all VW maximums + Database Catalog + Data Viz + 15% overhead.
- Use separate Database Catalogs for production and non-production environments.
- Monitor VW autoscaling events and queue depth daily in the CDW UI.
- Resize VWs based on observed query concurrency, not estimated peak.
- Assign dedicated VWs to workloads with different SLA classes.

**Don't:**
- Edit CDW-created namespaces or resource pools in the Management Console UI or kubectl.
- Provision VWs whose combined maximum exceeds the environment pool maximum (leaves no headroom).
- Share one VW between interactive BI and batch ETL — their scaling patterns conflict.
- Set maximum clusters = minimum clusters unless the workload is perfectly constant.
- Deploy Data Viz and Virtual Warehouses in the same resource pool (they are separate CDW components with separate pools).

---

## 4.10 Common Pitfalls

| Pitfall | Impact | Mitigation |
|---|---|---|
| Environment pool sized exactly to VW sum | No headroom for Database Catalog or CDW services | Add 20% overhead buffer to environment pool |
| Single VW for all query types | Interactive queries compete with batch scans | Dedicated VWs by workload class |
| Manual kubectl edits to CDW namespaces | CDW metadata/runtime desync; scaling failures | Never edit CDW namespaces outside CDW UI |
| Data Viz undersized | Dashboard load failures under concurrent access | Size Data Viz for concurrent user count, not data volume |
| No VW minimum set for production | Cold-start delay of 2–5 min on first query of the day | Set minimum clusters ≥ 1 for production VWs |
| Shared Database Catalog for prod/dev | Dev DDL operations affect prod metadata performance | Separate Database Catalog per environment |

---

## References and Notes

- CDW namespace and resource pool creation behavior is described in the CDW Private
  Cloud documentation for your CDP release.
- **[IMPORTANT]** The restriction on editing CDW-created pools outside the CDW UI is
  a documented operational constraint. Always use the CDW service UI.
- **[ASSUMPTION]** Exact autoscaling behavior at the environment pool boundary may vary
  between CDW releases. Test and document observed behavior in your environment.
- **[ASSUMPTION]** Data Visualization resource requirements listed are estimates based on
  typical deployments; verify actual consumption in your environment.
- CDW workload management (internal query queues, admission control) is a separate topic
  from Kubernetes resource quotas and is not covered in this document.
