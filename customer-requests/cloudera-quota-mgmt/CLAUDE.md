# CLAUDE.md — Project Guidance

## Purpose

This project produces a best-practices documentation set for quota and resource management in Cloudera Data Services (on-premises). It targets platform administrators, data architects, SRE/operations teams, and pre-sales engineers.

## Scope

- Cloudera AI (CAI / CML on-premises)
- Cloudera Data Engineering (CDE)
- Cloudera Data Warehouse (CDW)
- Cloudera Management Console (resource pool visibility and management)

## Writing Rules

1. Use only factual, vendor-aligned statements. If a feature is not explicitly documented in Cloudera public documentation, mark the statement as a **[Recommendation]** or **[Assumption]**.
2. Do not invent unsupported product features (e.g., do not claim a GUI option exists unless it does).
3. Use neutral, professional enterprise English. Avoid marketing language.
4. Keep each file focused on its topic. Prefer short paragraphs, bullets, and tables over long prose.
5. End every file with a "References and Notes" section listing assumptions made in that file.

## Accuracy Notes

- Quota management in Cloudera Data Services on-premises is primarily managed **through each data service UI** (CAI, CDE, CDW). The Management Console provides cluster-level resource pool visibility and pool management.
- The **default pool** is the standard node pool and can be subdivided into child pools.
- Quotas control **CPU, memory, and GPU** resources.
- **CDI/CDE-created quotas must not be edited in the Management Console UI** if they were originally created by the Data Engineering service; doing so can cause inconsistent state.
- CDW creates resource pools for namespaces, Virtual Warehouses, Database Catalogs, and Data Visualization instances; it manages autoscaling behavior within those pools.
- Cloudera AI quota management is user/group/team oriented and uses resource pools.

## File Map

| File | Topic |
|------|-------|
| README.md | Root index and navigation |
| docs/01-platform-overview.md | Platform-level resource pools, quota model, insufficient quota behavior |
| docs/02-cloudera-ai.md | CAI user/group/team quotas and resource pools |
| docs/03-cloudera-data-engineering.md | CDE guaranteed/max quotas, GPU allocation, Management Console warning |
| docs/04-cloudera-data-warehouse.md | CDW namespace pools, VW autoscaling, Database Catalog, Data Viz |
| docs/05-governance-and-operating-model.md | Naming conventions, change process, ownership, review cadence |
| docs/06-checklists.md | Pre-deployment, operational, and review checklists |

## Style Preferences

- Headings: Title Case for H2, sentence case for H3 and below.
- Tables: Use for comparisons, do's/don'ts, and quota examples.
- Code/CLI examples: Use fenced code blocks with appropriate language tag.
- Callouts: Use `> **Note:**`, `> **Warning:**`, or `> **Recommendation:**` blockquotes.
