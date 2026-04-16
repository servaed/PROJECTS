# 01 — Platform Overview: Resource Pools and Quota Mechanics

## 1.1 What Are Resource Pools?

Cloudera Data Services on premises uses **hierarchical resource pools** to partition
cluster compute capacity among data services, business units, and workload types.
A resource pool defines the maximum and, optionally, the guaranteed share of CPU,
memory, and GPU that a workload or service may consume.

Resource pools are rooted at the **default pool**, which represents the full schedulable
capacity of the cluster. All other pools are sub-divisions of this root, forming a tree.

```
default (cluster root)
├── cdw-env-production          ← CDW environment pool
│   ├── vw-hive-prod
│   ├── vw-impala-prod
│   └── db-catalog-prod
├── cde-service-prod            ← CDE service pool
│   ├── vc-etl-large
│   └── vc-streaming-medium
├── cai-workspace-prod          ← CAI workspace pool
│   ├── team-data-science
│   └── team-ml-platform
└── shared-services             ← control plane, monitoring, etc.
```

> **Key point:** The default pool is the standard allocation root. It can be subdivided
> into named pools for each service or team. Capacity not assigned to a named pool
> remains in the default pool and is available for unscheduled workloads.

---

## 1.2 Resource Dimensions

Quotas can be applied across three resource dimensions:

| Dimension | Unit | Notes |
|---|---|---|
| CPU | cores (vCPU) | Often expressed as millicores (m) in Kubernetes-backed services |
| Memory | GiB | Applies to working memory allocated to containers/pods |
| GPU | GPU units (devices) | Must be explicitly allocated; no implicit sharing |

All three dimensions are configured independently. A pool may have a CPU limit without
a GPU limit, or vice versa. Unset limits default to the parent pool's available capacity.

---

## 1.3 Guaranteed vs. Maximum Quotas

Two quota modes control how a pool behaves under contention:

| Mode | Behavior |
|---|---|
| **Guaranteed (minimum)** | The pool always receives at least this much capacity, even when the cluster is fully loaded. Useful for SLA-critical workloads. |
| **Maximum** | The pool may use up to this amount when capacity is available, but will be throttled or preempted to this ceiling under contention. |

- Setting guaranteed = maximum creates a **hard-reserved** pool. This ensures
  predictable performance but prevents capacity sharing.
- Setting guaranteed < maximum creates an **elastic** pool. The pool can burst up to
  maximum when capacity is free, but falls back to guaranteed under pressure.
- **[RECOMMENDATION]** For production workloads, set a meaningful guaranteed value.
  For development and ad-hoc pools, set guaranteed = 0 and rely on maximum only.

---

## 1.4 Where Quotas Are Set

Quota management spans two layers:

| Layer | Tool | Scope |
|---|---|---|
| **Cluster-level pool management** | Cloudera Manager / Management Console | View and edit top-level resource pools; set hardware partition boundaries |
| **Service-level quota management** | Each data service UI (CAI, CDE, CDW) | Create and manage service-specific sub-pools, user/team quotas, virtual cluster sizing |

> **Critical rule:** Data services create and manage their own resource pool sub-trees.
> If a pool was created by CDE or CDW, **do not edit or delete it in the Management
> Console UI**. Changes made outside the service UI can cause the service to enter an
> inconsistent state or fail to scale. See service-specific files for details.

The Management Console provides cluster-level resource visibility — total capacity, pool
utilisation, and node health — but quota configuration for workloads should be performed
within each data service.

---

## 1.5 Insufficient Quota: What Happens

When a workload or service requests more resources than its pool allows:

1. **Creation fails** — If a new Virtual Warehouse, virtual cluster, or workspace requires
   resources that exceed the parent pool's maximum, the creation request will fail with an
   insufficient-resource error. The service UI typically surfaces this as a capacity error.

2. **Autoscaling stalls** — If autoscaling is enabled and the pool is at its maximum, scale-out
   events will queue or fail. Existing workloads continue running; new work items wait.

3. **Preemption** — Depending on scheduler configuration, lower-priority workloads in
   the same pool may be preempted to free capacity for higher-priority requests.
   Preemption behavior is workload-scheduler-specific (YARN, Kubernetes).

4. **Eviction** — In Kubernetes-backed services, pods requesting more than available
   may be evicted. `Guaranteed` QoS class pods are evicted last.

> **Operational implication:** Always maintain headroom in the parent pool. If the sum of
> all child pool maximums equals the parent pool maximum, any burst by one child will
> starve others. The recommended practice is to leave 10–20% unallocated headroom at
> each pool level.

---

## 1.6 Recommended Pool Hierarchy

The following is a recommended starting hierarchy for a typical enterprise deployment.
Adjust based on actual workload counts and team structures.

```
default
├── production                    [guaranteed=70%, max=80%]
│   ├── cdw-prod                  [guaranteed=30%, max=40%]
│   ├── cde-prod                  [guaranteed=25%, max=35%]
│   └── cai-prod                  [guaranteed=15%, max=20%]
├── non-production                [guaranteed=10%, max=30%]
│   ├── cdw-dev
│   ├── cde-dev
│   └── cai-dev
├── gpu-workloads                 [guaranteed=5%, max=15%] ← GPU-capable nodes only
└── shared-services               [guaranteed=10%, max=15%] ← control plane, monitoring
```

> **[RECOMMENDATION]** Treat `shared-services` as untouchable. Control-plane components
> (Cloudera Manager agents, Kubernetes system pods, monitoring) must always have enough
> capacity. A cluster whose control plane is starved of resources is operationally unsafe.

---

## 1.7 Sample Quota Allocation Pattern (48-node cluster example)

Assume a cluster with: 48 worker nodes × 32 vCPU × 256 GiB RAM = 1,536 vCPU / 12,288 GiB.

| Pool | Guaranteed CPU | Max CPU | Guaranteed RAM | Max RAM | Notes |
|---|---|---|---|---|---|
| shared-services | 153 vCPU | 230 vCPU | 1,228 GiB | 1,843 GiB | 10% guaranteed |
| production | 1,075 vCPU | 1,229 vCPU | 8,601 GiB | 9,830 GiB | 70% guaranteed |
| → cdw-prod | 460 vCPU | 614 vCPU | 3,686 GiB | 4,915 GiB | |
| → cde-prod | 384 vCPU | 537 vCPU | 3,072 GiB | 4,301 GiB | |
| → cai-prod | 230 vCPU | 307 vCPU | 1,843 GiB | 2,457 GiB | |
| non-production | 153 vCPU | 460 vCPU | 1,228 GiB | 3,686 GiB | 10% guaranteed, 30% max |
| gpu-workloads | 76 vCPU | 230 vCPU | 614 GiB | 1,843 GiB | GPU nodes only |
| **Headroom** | ~76 vCPU | — | ~614 GiB | — | ~5% unallocated |

> Values are illustrative. Actual sizing depends on workload characterisation.

---

## 1.8 GPU Pool Considerations

GPUs are a discrete, non-divisible resource type. Guidelines:

- **Allocate GPU pools explicitly.** Do not leave GPU nodes in the default pool where
  non-GPU workloads may land and waste GPU capacity.
- Use node labels or taints to restrict GPU nodes to the GPU pool only.
- Set guaranteed GPU = 0 for most pools unless a service requires permanently reserved GPUs.
- In CDE, GPU resource pools are configured at the virtual cluster level.
  See [03-cloudera-data-engineering.md](03-cloudera-data-engineering.md).
- In CAI, GPU-enabled instance types are configured as resource profiles within a workspace.
  See [02-cloudera-ai.md](02-cloudera-ai.md).

---

## 1.9 Autoscaling and Pool Interaction

Autoscaling in CDP Private Cloud Data Services operates at two layers:

| Layer | Mechanism | Pool interaction |
|---|---|---|
| **Node-level autoscaling** | Cluster autoscaler adds/removes worker nodes | Bounded by cloud/bare-metal capacity; pool maximums still enforced |
| **Service-level autoscaling** | Virtual Warehouses, virtual clusters scale executor count | Bounded by the service's resource pool maximum |

When a service attempts to scale out:
1. It requests additional resources from its resource pool.
2. If the pool maximum allows it, pods are scheduled on available nodes.
3. If nodes are insufficient but the pool has headroom, the cluster autoscaler may provision
   new nodes (if configured and supported).
4. If the pool maximum is reached, scale-out stops. The service queues work until capacity frees.

> **[ASSUMPTION]** Node-level autoscaling availability depends on the underlying
> infrastructure (OpenShift, ECS, bare metal). Not all CDP Private Cloud deployments
> support automatic node provisioning. Verify with your infrastructure team.

---

## References and Notes

- Resource pool hierarchy as described here applies to CDP Private Cloud Data Services
  running on Kubernetes (OpenShift or ECS).
- The term "default pool" refers to the root Kubernetes namespace / resource quota from
  which data service namespaces inherit.
- Guaranteed and maximum quota semantics align with Kubernetes `requests` (guaranteed)
  and `limits` (maximum) concepts at the resource quota level.
- **[ASSUMPTION]** Exact UI field names for pool management may vary between CDP
  Private Cloud Base 7.x and Data Services releases. Verify field names in your release notes.
