# 02 — Cloudera AI: Quota Management

## 2.1 Overview

Cloudera AI (CAI) workspaces run on Kubernetes and use resource pools to control how
much CPU, memory, and GPU is available to users, teams, and automated workloads.
Quota management in CAI is **user- and group-oriented**: administrators assign resource
profiles and pool limits at the workspace, team, or individual-user level.

Resource pools in CAI map to Kubernetes resource quotas and limit ranges within the
workspace namespace. The workspace itself occupies a resource pool that is a sub-pool
of the parent cluster pool.

---

## 2.2 Workspace Resource Pools

When a CAI workspace is created, the Management Console allocates a resource pool for
that workspace from the cluster's default or designated parent pool. This workspace
pool defines the ceiling for all workloads that run inside it.

| Scope | Where configured |
|---|---|
| Workspace pool (CPU, memory, GPU ceiling) | Management Console / CAI workspace creation wizard |
| User/team resource profiles | CAI workspace admin UI (Site Administration → Resource Profiles) |
| Per-user or per-group limits | CAI workspace admin UI (User Management → Resource Quotas) |

---

## 2.3 Resource Profiles

Resource profiles define the CPU and memory combinations that users can select when
launching sessions, jobs, models, or applications. Administrators create and manage
profiles from within the workspace.

Best practices for resource profiles:

- **Define a small set of standard sizes** (e.g., Small / Medium / Large / GPU-Small)
  rather than allowing arbitrary values. Unconstrained selection leads to over-allocation.
- **Include a GPU profile only if GPU nodes are available** and the workspace pool
  includes GPU quota. Offering a GPU profile with no GPU capacity causes launch failures.
- **Set memory:CPU ratios** consistent with node instance types to avoid fragmentation.
  If nodes are 8 vCPU / 64 GiB, avoid profiles like 1 vCPU / 32 GiB that leave CPU stranded.

Example profile set:

| Profile name | CPU request | Memory request | GPU | Intended use |
|---|---|---|---|---|
| Small | 1 vCPU | 4 GiB | 0 | Interactive exploration, notebooks |
| Medium | 2 vCPU | 8 GiB | 0 | Standard data science sessions |
| Large | 4 vCPU | 16 GiB | 0 | Heavy computation, model training on CPU |
| GPU-Small | 4 vCPU | 32 GiB | 1 | GPU model training, inference development |
| GPU-Large | 8 vCPU | 64 GiB | 2 | Large model training |
| Spark Driver | 2 vCPU | 8 GiB | 0 | Spark driver for CML Spark sessions |

---

## 2.4 User and Group Quota Management

CAI supports quota assignment at three granularities:

1. **Workspace-level defaults** — All users inherit these limits unless overridden.
2. **Team / group quotas** — A team's combined resource usage is bounded.
3. **Per-user quotas** — Individual users can be capped below the team default.

**Do's:**
- Apply workspace-level defaults conservatively. Users can always request an increase.
- Use group quotas to enforce department-level budgets (e.g., team A gets 40 vCPU max).
- Reserve a quota buffer for admin and system processes that run inside the workspace.

**Don'ts:**
- Do not set per-user maximums to the total workspace pool maximum. If one user exhausts
  the workspace, all others are blocked.
- Do not skip group-level quotas in multi-team workspaces. Without them, a single team
  can monopolise the workspace pool.

---

## 2.5 GPU Quota in CAI

GPU resources in CAI require explicit configuration:

1. The workspace pool must include GPU quota allocated from the cluster's GPU node pool.
2. GPU-enabled resource profiles must be created in the workspace admin UI.
3. Users must be permitted to launch GPU sessions (role and quota must both allow it).

**GPU-specific best practices:**

- **Allocate GPU quota only to workspaces that have GPU workloads.** GPU capacity is
  scarce; do not spread it across every workspace "just in case."
- **Set a per-user GPU maximum** to prevent a single user from holding all GPUs idle
  in a long-running session.
- **Enable session idle timeout** for GPU sessions. GPU sessions left running but idle
  consume expensive capacity. Configure an idle reclamation policy in workspace settings.
- **[RECOMMENDATION]** Create a separate GPU-enabled workspace for production model
  training and a separate one for experimentation, each with its own GPU pool share.
  This prevents experiment workloads from blocking production training jobs.

---

## 2.6 Autoscaling Behavior

CAI workloads (sessions, jobs, models) are scheduled as Kubernetes pods within the
workspace pool. Autoscaling behavior:

- If the workspace pool has available headroom, new sessions start immediately.
- If the workspace pool is at maximum, new session requests queue and users see a
  "Waiting for resources" state until capacity is released.
- CAI does not automatically expand the workspace pool. Pool resizing requires an
  administrator action in the Management Console or CAI workspace settings.

**[RECOMMENDATION]** Set up alerting on workspace pool utilisation. When sustained
utilisation exceeds 80% of the workspace maximum for more than 30 minutes, treat it
as a capacity expansion signal, not a one-off event.

---

## 2.7 Isolation Between Workspaces

Each CAI workspace runs in its own Kubernetes namespace with its own resource quota.
This provides hard isolation between workspaces.

**For multi-team deployments:**

| Pattern | When to use |
|---|---|
| One workspace per team | Strong isolation required; teams have independent LDAP groups |
| One workspace, multiple teams | Teams collaborate; workspace admin manages internal quotas |
| One workspace per environment (prod/dev) | Lifecycle isolation; different LLM endpoints or data access |

Regardless of pattern, always ensure:
- Production workspaces have dedicated pools, not shared with dev.
- GPU-enabled workspaces are explicitly separated from CPU-only workspaces.
- Access to workspace admin settings is restricted to named platform administrators.

---

## 2.8 Common Pitfalls

| Pitfall | Impact | Mitigation |
|---|---|---|
| No idle timeout on GPU sessions | GPU capacity held by idle sessions for hours | Enable idle session reclamation in workspace settings |
| All users in same large profile | No differentiation; over-allocation for simple tasks | Define Small/Medium/Large profiles; apply per-user defaults |
| Workspace pool = cluster total | No capacity for control plane or other services | Reserve at least 10–15% of cluster capacity outside CAI |
| GPU profile with no GPU quota | Launch failures, confusing errors for users | Only create GPU profiles when GPU quota is allocated |
| Single workspace for prod and dev | Dev experiments impact production model serving | Separate workspaces with separate pools |

---

## 2.9 Do's and Don'ts Summary

**Do:**
- Define a named resource profile for each workload class (interactive, batch, GPU).
- Set idle timeouts for all session types, especially GPU.
- Assign workspace pools from the Management Console during workspace creation.
- Monitor workspace-level utilisation weekly and right-size pools.
- Document who owns each workspace and the approved resource profile set.

**Don't:**
- Allow users to select arbitrary CPU/memory values without a profile constraint.
- Create GPU profiles in workspaces that have no GPU quota.
- Share a workspace pool between production workloads and exploratory experiments.
- Ignore "Waiting for resources" queuing signals — they are early capacity warnings.

---

## References and Notes

- CAI workspace resource pool management is performed through the CAI workspace admin UI
  and the Management Console. The exact path may vary by CDP version.
- **[ASSUMPTION]** Per-user GPU idle timeout and reclamation policies are available as
  workspace-level settings in recent CAI releases. Verify availability in your version.
- **[ASSUMPTION]** Group-level quota enforcement within a workspace is supported;
  verify the exact configuration path in your CAI workspace admin documentation.
- GPU node scheduling requires nodes to be labeled and tainted appropriately in Kubernetes.
  This is an infrastructure prerequisite, not a CAI-only configuration.
