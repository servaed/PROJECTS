# 02 — Cloudera AI: Quota Management

## Overview

Cloudera AI (CAI), formerly Cloudera Machine Learning (CML), provides quota management at multiple levels: the workspace level, and within a workspace at the user, group, and team level. Quotas control CPU, memory, and GPU consumption for interactive sessions, jobs, applications, and model deployments.

---

## 1. Quota Model

### 1.1 Levels of Quota Enforcement

CAI enforces quotas at two levels:

```
Resource Pool (Management Console)
└── CAI Workspace (namespace-level quota)
    ├── Default User Quota  (applied to all users without explicit overrides)
    ├── User Quota          (per-user override)
    ├── Group Quota         (applied to an LDAP/AD group)
    └── Team Quota          (applied to a CAI team)
```

- The **workspace quota** is the ceiling for all resources consumed within a workspace. It is backed by a Kubernetes namespace ResourceQuota and maps to a resource pool in the Management Console.
- **User, group, and team quotas** are enforced within the workspace and cannot exceed the workspace's total quota.

### 1.2 Resource Dimensions

| Dimension | Scope | Notes |
|-----------|-------|-------|
| CPU | Per session/job/application | Expressed as cores; can set minimum and maximum per resource profile |
| Memory | Per session/job/application | Expressed in GiB; minimum and maximum per resource profile |
| GPU | Per session/job/application | Expressed as whole GPU units; exclusively allocated per workload |

### 1.3 Resource Profiles

Resource profiles define the CPU, memory, and GPU combinations available to users when launching sessions, jobs, or applications. Administrators create profiles; users select from the available profiles.

> **Recommendation:** Define a tiered set of resource profiles (e.g., Small, Medium, Large, GPU) rather than allowing arbitrary resource requests. This simplifies quota accounting and prevents users from inadvertently requesting oversized allocations.

---

## 2. Workspace Quota Configuration

### 2.1 Assigning a Workspace to a Resource Pool

When provisioning a CAI workspace in the Management Console:
1. Select the target Kubernetes cluster.
2. Assign the workspace to a resource pool. The workspace namespace will inherit the pool's quota limits.
3. Set workspace-level CPU, memory, and GPU limits within the assigned pool's available capacity.

> **Recommendation:** Create a dedicated resource pool per workspace (e.g., `CAI-Prod`, `CAI-Dev`) rather than sharing a pool across multiple workspaces. This provides clear isolation and simplifies utilization tracking.

### 2.2 Workspace-Level Quota Limits

The workspace quota acts as the hard ceiling. No combination of user, group, or team activity within the workspace can exceed these values.

- Set workspace CPU and memory limits based on the number of expected concurrent users and their typical session sizes.
- Set workspace GPU limits based on the number of available GPU devices allocated to the pool.

---

## 3. User, Group, and Team Quotas

### 3.1 Default User Quota

The default user quota applies to all users in the workspace who do not have an explicit quota override. It controls:
- Maximum CPU cores a single user may consume concurrently.
- Maximum memory a single user may consume concurrently.
- Maximum GPU units a single user may hold concurrently.

> **Recommendation:** Set the default user quota conservatively to prevent any single user from monopolizing workspace resources. Increase quotas for specific users or groups as needed.

### 3.2 User Quota Overrides

Individual users can be granted higher (or lower) quotas than the workspace default. This is configured in the CAI workspace admin settings under **User and Group Quotas**.

Common use cases for user quota overrides:
- Data scientists running large-scale distributed training jobs requiring more GPUs.
- Service accounts running automated pipelines that need guaranteed capacity.
- Guest or restricted users who should be limited to minimal resources.

### 3.3 Group Quotas

Group quotas apply to LDAP or Active Directory groups synchronized into the workspace. A group quota sets the aggregate maximum for all members of the group combined, not a per-member limit.

> **Note:** If a user belongs to multiple groups with different quotas, CAI applies the most permissive group quota. Verify this behavior against your specific CAI release.  [verify on upgrade]

### 3.4 Team Quotas

CAI teams are workspace-level constructs (distinct from LDAP groups) that can be used to group collaborators on a project. Team quotas set aggregate limits for all team members.

- Teams provide a convenient way to apply shared budgets to project-based allocations.
- A user can belong to multiple teams; the effective quota is the most permissive.

---

## 4. GPU Quota Management in CAI

### 4.1 GPU Allocation Model

GPUs in CAI are allocated as whole units per workload (session, job, or application). When a user launches a GPU session:
- The GPU is exclusively reserved for that session until the session is stopped.
- Other users cannot share the same GPU while it is allocated.
- The GPU is returned to the pool when the session terminates.

> **Warning:** GPU sessions that are left idle but not stopped continue to hold the GPU allocation. This is a common cause of GPU starvation for other users.

### 4.2 Recommended GPU Controls

| Control | Recommendation |
|---------|---------------|
| Default user GPU quota | Set to 0 for most users; enable GPU access only for users who need it |
| GPU-enabled resource profiles | Create separate GPU profiles and restrict their availability by group or role |
| Session timeout policies | Configure automatic session timeout for idle GPU sessions to reclaim capacity |
| GPU pool sizing | Allocate GPU quota strictly; do not rely on burst beyond the pool ceiling |

### 4.3 GPU Pool Assignment

Ensure the CAI workspace resource pool is assigned to a node pool that contains GPU nodes. The Management Console pool configuration must map to Kubernetes node selectors or taints that target GPU-capable nodes.

> **Assumption:** Node pool labeling and GPU device plugin configuration are prerequisites managed at the cluster level before CAI GPU quotas can be enforced. Verify with your cluster administrator.

---

## 5. Autoscaling Interaction

CAI workspaces do not directly control cluster autoscaling. However, workspace quota limits interact with cluster autoscaling as follows:

- If autoscaling is enabled on the Kubernetes cluster and the workspace quota allows it, new pods can trigger node scale-out up to the quota ceiling.
- If the workspace quota is exhausted, autoscaling will not help — new workloads are blocked at the quota level before reaching the scheduler.
- If autoscaling is disabled or constrained, workloads may queue even when the quota has not been reached, because physical nodes are unavailable.

> **Recommendation:** Align workspace quota ceilings with the maximum node count that the autoscaler is permitted to provision for the CAI node pool. Quota should not exceed the maximum physical capacity the autoscaler can provide.

---

## 6. Common Pitfalls

| Pitfall | Impact | Mitigation |
|---------|--------|------------|
| No default user quota set | A single user can consume the entire workspace allocation | Always set a default user quota |
| GPU sessions left idle | GPU starvation for other users | Enforce session timeout policies |
| Workspace quota exceeds parent pool | Creation fails or is silently constrained | Verify parent pool capacity before setting workspace quota |
| Over-permissive group quotas | Groups consume more than their fair share | Audit group quotas quarterly |
| Resource profiles not curated | Users request arbitrary resource sizes, making quota planning impossible | Define a fixed set of resource profiles |

---

## 7. Do's and Don'ts

| Do | Don't |
|----|-------|
| Create dedicated resource pools per workspace | Share a single pool across all workspaces without sub-pools |
| Set a conservative default user quota | Leave default user quota unlimited |
| Create separate GPU resource profiles | Mix GPU and non-GPU profiles indiscriminately |
| Enable session auto-timeout for GPU sessions | Allow idle GPU sessions to persist indefinitely |
| Review user and group quota utilization monthly | Set quotas once and never revisit them |
| Document which groups map to which quota tiers | Leave group quota assignments undocumented |

---

## 8. Troubleshooting

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| Session fails to start with "Insufficient resources" | User quota or workspace quota exhausted | Check workspace admin quota view; check pool utilization in Management Console |
| GPU session cannot acquire GPU | GPU workspace quota exhausted or no GPU nodes available | Check GPU allocation in workspace admin; verify node pool has GPU nodes |
| User can start sessions but no GPU option appears | User's quota or resource profile does not include GPU | Grant user a GPU-enabled resource profile or increase GPU quota |
| Workspace provisioning fails | Parent resource pool lacks sufficient capacity | Increase parent pool quota in Management Console |

---

## References and Notes

- **[Assumption]** The behavior of applying the most permissive group quota when a user belongs to multiple groups should be verified against the specific CAI/CML release in use. [verify on upgrade]
- **[Recommendation]** Session timeout policies for GPU reclamation are operational best practices; actual timeout configuration options may vary by CAI version.
- **[Assumption]** GPU allocation is exclusive per workload (one GPU per session). Fractional GPU sharing is not described as a standard CAI feature.
- Refer to the Cloudera Machine Learning / Cloudera AI Administration Guide for authoritative quota configuration procedures.
