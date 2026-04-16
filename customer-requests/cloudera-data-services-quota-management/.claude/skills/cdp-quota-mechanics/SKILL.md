---
name: cdp-quota-mechanics
description: Core mechanics of resource pools, quota dimensions, guaranteed vs. maximum quotas, and insufficient-quota behavior in CDP Private Cloud Data Services.
---

# Skill: CDP Quota Mechanics

## Resource Pool Hierarchy

All quota management in CDP Private Cloud Data Services is hierarchical:

```
default (cluster root)
├── production
│   ├── cdw-prod
│   ├── cde-prod
│   └── cai-prod
├── non-production
│   ├── cdw-dev
│   ├── cde-dev
│   └── cai-dev
├── gpu-workloads        ← GPU-capable nodes only
└── shared-services      ← control plane, monitoring (always reserved)
```

- The **default pool** is the schedulable root of the cluster. Sub-pools are carved from it.
- Capacity not assigned to a named pool stays in the default pool (available to unscheduled workloads).
- Each data service (CAI, CDE, CDW) creates its own sub-pool tree. **Never edit service-created pools in the Management Console UI.**

## Quota Dimensions

| Dimension | Unit | Notes |
|---|---|---|
| CPU | vCPU (millicores in Kubernetes) | Controlled independently of memory |
| Memory | GiB | Controlled independently of CPU |
| GPU | device count | No implicit sharing; must be explicitly allocated |

## Guaranteed vs. Maximum

| Mode | Kubernetes equivalent | Behavior |
|---|---|---|
| Guaranteed (minimum) | `requests` aggregate | Always available, even under full cluster load |
| Maximum | `limits` / `hard` quota | Ceiling; workload is throttled or blocked above this |

- **guaranteed = maximum** → hard-reserved pool. Predictable, no sharing.
- **guaranteed < maximum** → elastic pool. Bursts to maximum when capacity is free; falls to guaranteed under contention.
- Production workloads: set meaningful guaranteed. Dev/ad-hoc: guaranteed = 0, max only.

## Insufficient Quota Behavior

| Scenario | Result |
|---|---|
| Creation request exceeds parent pool max | Service creation fails with capacity error |
| Autoscale hits pool maximum | Scale-out stops; work queues |
| Scheduler cannot fit pod | Pod stays Pending; may trigger cluster autoscaler |
| Kubernetes Guaranteed QoS pods | Evicted last; BestEffort pods evicted first |

## Headroom Rules

- Reserve **10–15%** of cluster capacity for `shared-services` (control plane, monitoring). Never allocate this.
- Leave **10–20% headroom** at each pool level. If all child pool maximums equal the parent maximum, any burst by one child starves others.
- Target **≥ 30% free** at the cluster level at all times.

## Where to Configure Quotas

| Layer | Tool |
|---|---|
| Cluster-level pools | Management Console |
| CAI workspace | CAI workspace admin UI |
| CDE service + virtual clusters | CDE service UI |
| CDW environments + VWs + VCs | CDW UI |

## GPU Pool Rules

- Allocate GPU nodes to a dedicated pool; taint/label them to prevent non-GPU pod scheduling.
- Set GPU guaranteed = 0 for most pools (no need to permanently reserve GPUs unless SLA requires it).
- Never create GPU profiles or GPU VCs without GPU quota in the parent pool.

## Key Constraint

> Data services that create resource pools own those pools. CDE and CDW created pools must be
> managed through their own service UIs, not the Management Console. Editing externally causes
> metadata desync and scaling failures.
