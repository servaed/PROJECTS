# CLAUDE.md — cloudera-data-services-quota-management

## Project Purpose

Technical documentation set covering best practices for quota and resource management
across Cloudera Data Services on premises (Cloudera AI, Cloudera Data Engineering,
Cloudera Data Warehouse). Intended for platform admins, architects, SRE teams, and
pre-sales engineers.

## Audience

| Role | Primary files |
|------|---------------|
| Platform administrator | 01, 05, 06 |
| Data platform architect | 01, 02, 03, 04, 05 |
| SRE / operations | 06 (checklists + troubleshooting), 05 |
| Pre-sales / solution engineer | 01, service-specific files (02–04) |

## Document Structure

```
cloudera-data-services-quota-management/
├── README.md                          ← Entry point, index, key principles
├── CLAUDE.md                          ← This file
└── docs/
    ├── 01-platform-overview.md        ← Resource pool hierarchy, quota mechanics
    ├── 02-cloudera-ai.md              ← CAI workspace pools, profiles, GPU
    ├── 03-cloudera-data-engineering.md← CDE services, VCs, guaranteed/max, GPU
    ├── 04-cloudera-data-warehouse.md  ← CDW environments, VWs, DB Catalog, DataViz
    ├── 05-governance-and-operating-model.md ← Ownership, naming, change process
    └── 06-checklists.md               ← Pre-deploy checklists, troubleshooting, FAQ
```

## Key Facts Covered

- Hierarchical resource pools rooted at the cluster default pool
- Quota dimensions: CPU (vCPU/millicores), memory (GiB), GPU (devices)
- Guaranteed (min) vs. maximum quotas — reserved vs. elastic behavior
- Insufficient quota behavior: creation failure, autoscaling stall, queuing, eviction
- **Critical rule:** Do not edit CDE- or CDW-created resource pools in the Management Console UI
- CAI quota: user/group/team oriented; resource profiles define CPU+memory+GPU choices
- CDE quota: service pool + virtual cluster guaranteed/max; GPU VC allocation guidance
- CDW quota: environment → DB Catalog → VW → DataViz namespace hierarchy; autoscaling bounds

## Writing Conventions

- Enterprise English, neutral professional tone, no marketing language
- Short paragraphs, tables for comparisons, bullets for lists
- `**[RECOMMENDATION]**` — advisor best practice, not documented product behavior
- `**[ASSUMPTION]**` — behavior inferred or not explicitly documented; verify in your release
- `**[IMPORTANT]**` — documented Cloudera constraint or warning
- Each file ends with a "References and Notes" section listing assumptions made
- Do not invent unsupported product features

## Content Boundaries

**In scope:**
- Resource pool configuration and sizing guidance
- Quota mechanics for CAI, CDE, CDW on CDP Private Cloud Data Services
- Governance, naming, change management, monitoring recommendations
- Troubleshooting for resource/quota-related failures

**Out of scope:**
- CDP Public Cloud quota management (different control plane)
- CDW internal workload management / query admission control (separate from K8s quotas)
- Cloudera Data Flow (NiFi) resource management
- Network policies, storage quotas, or Kubernetes RBAC

## Maintenance Notes

- This documentation is written against CDP Private Cloud Data Services.
  Verify against the specific release version deployed in the target environment.
- When the documentation is updated, check all `[ASSUMPTION]` and `[RECOMMENDATION]`
  markers against the latest Cloudera release notes to confirm or correct them.
- Sample quota values (vCPU counts, GiB values) are illustrative. Replace with
  actual cluster specifications when used in customer-facing deliverables.
