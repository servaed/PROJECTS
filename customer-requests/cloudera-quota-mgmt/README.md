# Cloudera Data Services — Quota and Resource Management Best Practices

This documentation set provides best-practice guidance for quota and resource management in **Cloudera Data Services on-premises** deployments. It is intended for platform administrators, data platform architects, SRE/operations teams, and pre-sales/solution engineers.

---

## Scope

This guide covers:

| Service | Scope |
|---------|-------|
| **Cloudera AI (CAI)** | Workspace quotas, user/group/team resource profiles, GPU allocation |
| **Cloudera Data Engineering (CDE)** | Service and virtual cluster quotas, guaranteed/maximum allocation, GPU pools |
| **Cloudera Data Warehouse (CDW)** | Namespace resource pools, Virtual Warehouses, Database Catalogs, Data Visualization, autoscaling |
| **Management Console** | Cluster-level resource pool hierarchy, pool visibility and management |

> **Note:** This guide applies to **CDP Private Cloud Data Services** only. CDP Public Cloud quota management differs and is out of scope.

---

## Document Index

| # | File | Description |
|---|------|-------------|
| — | [CLAUDE.md](CLAUDE.md) | Authoring guidelines and project constraints |
| — | [SKILLS.md](SKILLS.md) | Domain expertise reference and key terminology |
| 1 | [docs/01-platform-overview.md](docs/01-platform-overview.md) | Platform-level resource pool model, quota hierarchy, insufficient quota behavior |
| 2 | [docs/02-cloudera-ai.md](docs/02-cloudera-ai.md) | Cloudera AI quota management: workspaces, user/group/team, GPU |
| 3 | [docs/03-cloudera-data-engineering.md](docs/03-cloudera-data-engineering.md) | CDE quotas: guaranteed/max, virtual clusters, GPU allocation |
| 4 | [docs/04-cloudera-data-warehouse.md](docs/04-cloudera-data-warehouse.md) | CDW quotas: namespaces, Virtual Warehouses, autoscaling, Data Viz |
| 5 | [docs/05-governance-and-operating-model.md](docs/05-governance-and-operating-model.md) | Naming conventions, change process, ownership, review cadence |
| 6 | [docs/06-checklists.md](docs/06-checklists.md) | Pre-deployment, operational, and periodic review checklists |

---

## Quick-Start Reading Paths

**I am a platform admin setting up quotas for the first time:**
1. [Platform Overview](docs/01-platform-overview.md) — understand the model
2. [Governance and Operating Model](docs/05-governance-and-operating-model.md) — establish structure
3. [Checklists](docs/06-checklists.md) — pre-deployment checklist

**I am an architect designing a multi-tenant environment:**
1. [Platform Overview](docs/01-platform-overview.md) — pool hierarchy design
2. [Governance and Operating Model](docs/05-governance-and-operating-model.md) — naming, isolation, ownership
3. Service-specific files ([CAI](docs/02-cloudera-ai.md), [CDE](docs/03-cloudera-data-engineering.md), [CDW](docs/04-cloudera-data-warehouse.md))

**I am an SRE responding to a quota exhaustion incident:**
1. [Platform Overview](docs/01-platform-overview.md) — insufficient quota behavior section
2. Relevant service-specific file for the affected service
3. [Checklists](docs/06-checklists.md) — operational checklist

**I am a pre-sales engineer sizing a new deployment:**
1. [Platform Overview](docs/01-platform-overview.md) — capacity planning section
2. Service-specific files for the services in scope
3. [Checklists](docs/06-checklists.md) — sizing checklist

---

## Key Principles

1. **Quotas are hierarchical.** Resource pools nest inside parent pools. A child pool cannot exceed its parent's allocation.
2. **Data services own their quotas.** CAI, CDE, and CDW manage quotas through their own UIs. Use the Management Console for cluster-level pool visibility only.
3. **Never manually edit CDE-created namespace quotas in the Management Console.** Doing so causes state drift and can break service lifecycle management.
4. **Reserve headroom.** Always reserve 10–20% of cluster capacity for control-plane components and shared services.
5. **Separate prod from non-prod.** Use distinct resource pools for production and non-production workloads to prevent resource contention.
6. **Allocate GPU pools explicitly.** Do not rely on the default pool for GPU workloads; create dedicated GPU pools with explicit limits.

---

## Version and Compatibility Notes

- Written against CDP Private Cloud Data Services. Specific release versions are noted within each document.
- Statements marked **[Recommendation]** are best practices not necessarily enforced by the platform.
- Statements marked **[Assumption]** are inferred behaviors; verify against your specific CDP version.
- Tag **[verify on upgrade]** indicates content that may change between CDP releases.
