# Quota and Resource Management in Cloudera Data Services (On-Premises)

This documentation set covers best practices for configuring, managing, and governing
resource quotas across Cloudera Data Services on premises. It is intended for platform
administrators, data platform architects, SRE / operations teams, and pre-sales engineers.

---

## Scope

| Data Service | Covered |
|---|---|
| Cloudera AI (CAI) | Yes |
| Cloudera Data Engineering (CDE) | Yes |
| Cloudera Data Warehouse (CDW) | Yes |
| Management Console (resource visibility) | Yes |

---

## Document Index

| File | Topic |
|---|---|
| [docs/01-platform-overview.md](docs/01-platform-overview.md) | Platform-level resource pools, hierarchy, and quota mechanics |
| [docs/02-cloudera-ai.md](docs/02-cloudera-ai.md) | Cloudera AI quota management for users, groups, and resource pools |
| [docs/03-cloudera-data-engineering.md](docs/03-cloudera-data-engineering.md) | CDE virtual clusters, guaranteed vs. maximum quotas, GPU allocation |
| [docs/04-cloudera-data-warehouse.md](docs/04-cloudera-data-warehouse.md) | CDW environments, Database Catalogs, Virtual Warehouses, Data Viz |
| [docs/05-governance-and-operating-model.md](docs/05-governance-and-operating-model.md) | Governance model, naming conventions, change process, ownership |
| [docs/06-checklists.md](docs/06-checklists.md) | Pre-deployment checklists, day-2 review checklist, troubleshooting FAQ |

---

## Key Principles

1. **Hierarchical resource pools** — all quota management in Cloudera Data Services on
   premises builds on a tree of resource pools rooted at the cluster's default pool.
2. **Service-owned sub-pools** — each data service (CAI, CDE, CDW) creates and manages
   its own resource pools. Do not edit service-created pools directly in the Management
   Console UI.
3. **Headroom is mandatory** — never allocate 100% of cluster capacity to named pools.
   Reserve capacity for control-plane components, shared services, and burst headroom.
4. **Isolation by design** — separate production and non-production workloads into
   distinct pools from day one. Retrofitting isolation is disruptive.
5. **Least-privilege allocation** — start with conservative quotas and expand based on
   observed utilisation. Unused guaranteed capacity is wasted capacity.

---

## Audience Guide

| Role | Start here |
|---|---|
| Platform administrator | [01-platform-overview.md](docs/01-platform-overview.md) → [05-governance-and-operating-model.md](docs/05-governance-and-operating-model.md) → [06-checklists.md](docs/06-checklists.md) |
| Data platform architect | [01-platform-overview.md](docs/01-platform-overview.md) → service-specific files → [05-governance-and-operating-model.md](docs/05-governance-and-operating-model.md) |
| SRE / operations | [06-checklists.md](docs/06-checklists.md) → [05-governance-and-operating-model.md](docs/05-governance-and-operating-model.md) |
| Pre-sales / solution engineer | [01-platform-overview.md](docs/01-platform-overview.md) → service-specific files |

---

## Version and Assumptions

- Applies to Cloudera Data Platform (CDP) Private Cloud Base and CDP Private Cloud Data Services.
- Where behavior is not explicitly documented in Cloudera public documentation, statements
  are labeled **[RECOMMENDATION]** or **[ASSUMPTION]**.
- Screenshots and exact UI field names may vary across CDP versions; verify against your
  installed release.
