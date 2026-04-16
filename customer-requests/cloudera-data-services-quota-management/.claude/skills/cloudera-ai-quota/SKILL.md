---
name: cloudera-ai-quota
description: Quota management patterns for Cloudera AI workspaces — resource pools, resource profiles, user/group limits, GPU idle policy, and isolation best practices.
---

# Skill: Cloudera AI Quota Management

## Quota Scope Hierarchy

```
Cluster pool
└── CAI workspace pool        ← set in Management Console at workspace creation
    ├── resource profiles      ← CPU+memory+GPU combinations (workspace admin UI)
    ├── group/team quotas      ← aggregate cap per team
    └── per-user limits        ← cap for individual users
```

## Workspace Pool

- Allocated from the cluster default (or a named parent pool) when the workspace is created.
- Defines the hard ceiling for all sessions, jobs, models, and apps in the workspace.
- Resize via Management Console; requires admin access.
- **[ASSUMPTION]** Pool resize does not restart running sessions, but availability of new capacity depends on cluster headroom.

## Resource Profiles

Standard profile set (recommended starting point):

| Profile | CPU request | Memory request | GPU | Use case |
|---|---|---|---|---|
| Small | 1 vCPU | 4 GiB | 0 | Interactive notebooks |
| Medium | 2 vCPU | 8 GiB | 0 | Standard data science |
| Large | 4 vCPU | 16 GiB | 0 | CPU-heavy training |
| GPU-Small | 4 vCPU | 32 GiB | 1 | GPU training/inference dev |
| GPU-Large | 8 vCPU | 64 GiB | 2 | Large model training |
| Spark Driver | 2 vCPU | 8 GiB | 0 | CML Spark sessions |

Rules:
- Do not offer GPU profiles unless the workspace pool has GPU quota.
- Match memory:CPU ratio to node instance types to avoid resource fragmentation.
- Use a small profile as the workspace default. Users escalate as needed.

## User and Group Quotas

- **Workspace defaults** → apply to all users unless overridden.
- **Group quotas** → cap aggregate usage for a team/BU.
- **Per-user limits** → cap individual users below the group default.
- Never set a per-user maximum equal to the full workspace pool maximum.

## GPU Rules

1. Workspace pool must include GPU quota before GPU profiles are created.
2. Enable idle session timeout for GPU sessions (reclaim idle GPU capacity).
3. Set a per-user GPU maximum to prevent one user holding all GPUs.
4. Separate production training workspaces from experimentation workspaces; give each its own GPU pool share.

## Autoscaling Behavior

- CAI does **not** auto-expand the workspace pool. Pool expansion requires admin action.
- If the pool is exhausted, new sessions enter "Waiting for resources" state.
- Alert at 80% sustained pool utilisation (warn) and treat it as a capacity expansion signal.

## Isolation Patterns

| Pattern | When to use |
|---|---|
| One workspace per team | Strong isolation; independent LDAP groups |
| One workspace per environment (prod/dev) | Lifecycle isolation; different LLM endpoints |
| One workspace, multiple teams | Collaborative; admin manages internal quotas |

- Production workspaces must have dedicated pools (not shared with dev).
- Never share a workspace pool between production model serving and exploratory experiments.

## Common Pitfalls

| Pitfall | Fix |
|---|---|
| GPU sessions idle for hours | Enable idle session timeout |
| All users on Large profile by default | Set Small as default; let users escalate |
| GPU profile without GPU quota | Remove profile or allocate GPU quota first |
| Workspace pool = cluster total | Reserve headroom for other services + control plane |
