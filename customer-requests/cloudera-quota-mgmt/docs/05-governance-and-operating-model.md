# 05 — Governance and Operating Model

## Overview

Effective quota management requires more than correct technical configuration. It requires clear ownership, consistent naming conventions, a defined change process, and a regular review cadence. This document establishes the governance framework for operating the Cloudera Data Services quota and resource pool model in an enterprise environment.

---

## 1. Ownership Model

### 1.1 Role Definitions

| Role | Responsibilities |
|------|----------------|
| **Platform Administrator** | Create and manage top-level resource pools in the Management Console; enforce cluster-level capacity policies; own the control-plane reserve pool |
| **Data Platform Architect** | Design the pool hierarchy; define naming conventions and sizing standards; approve major quota changes |
| **SRE / Operations Team** | Monitor pool utilization; respond to quota exhaustion incidents; execute approved quota changes outside business hours |
| **Data Service Owner (CAI / CDE / CDW)** | Manage service-level quotas within their assigned pool; submit requests for pool quota increases; maintain virtual cluster and workspace documentation |
| **Security / Compliance** | Audit group and user quota assignments; verify isolation between tenants; review changes that affect multi-tenant environments |

### 1.2 Ownership Assignment

Each resource pool must have a documented owner. The pool name should encode the service and tier (see Section 2), and a supplementary registry (spreadsheet, CMDB entry, or infrastructure-as-code comment) must record:

- Pool name
- Owning team
- Assigned service and environment tier
- Current quota values (CPU, memory, GPU)
- Justification for the current allocation
- Date last reviewed

---

## 2. Naming Conventions

### 2.1 Resource Pool Naming

Use a consistent naming scheme to make ownership, service, and tier unambiguous at a glance.

**Pattern:** `<service>-<tier>[-<region-or-cluster>]`

| Token | Values | Notes |
|-------|--------|-------|
| `<service>` | `cai`, `cde`, `cdw`, `shared`, `ctrl` | Use `ctrl` for the control-plane reserve; `shared` for pools not tied to a specific service |
| `<tier>` | `prod`, `dev`, `staging`, `sandbox` | Always include tier; never leave ambiguous |
| `<region-or-cluster>` | Optional: `us-east`, `cluster01` | Include when multiple clusters or regions are managed |

**Examples:**

| Pool Name | Meaning |
|-----------|---------|
| `ctrl-reserve` | Control-plane reserve pool, all clusters |
| `cai-prod` | Cloudera AI production pool |
| `cde-dev` | Cloudera Data Engineering development pool |
| `cdw-prod` | Cloudera Data Warehouse production pool |
| `cai-prod-us-east` | Cloudera AI production pool in the US-East cluster |

### 2.2 Virtual Cluster and Workspace Naming (Service Level)

Apply similar conventions within data service UIs:

**CDE Virtual Clusters:** `<team-or-domain>-<tier>` (e.g., `analytics-prod`, `etl-dev`)

**CAI Workspaces:** `<team-or-domain>-<tier>` (e.g., `datascience-prod`, `ml-sandbox`)

**CDW Virtual Warehouses:** `<team-or-domain>-<engine>-<tier>` (e.g., `reporting-hive-prod`, `adhoc-impala-dev`)

> **Recommendation:** Enforce naming conventions at the infrastructure-as-code or deployment automation layer, not only through documentation. Inconsistent names in production environments make incident response significantly harder.

---

## 3. Change Management Process

### 3.1 Change Categories

| Category | Examples | Process |
|----------|---------|---------|
| **Routine** | Increasing a VW max node count within an existing pool; adjusting a default user quota in CAI | Data Service Owner approves; SRE executes; log the change |
| **Standard** | Creating a new resource pool; adding a new virtual cluster; increasing a pool quota | Data Platform Architect approves; Platform Admin executes; update the pool registry |
| **Major** | Restructuring the pool hierarchy; reducing production pool quotas; adding a new service tier | Data Platform Architect and Platform Admin jointly review; change control board approval required; off-hours execution with rollback plan |
| **Emergency** | Responding to quota exhaustion incident blocking production | On-call SRE executes with verbal approval from Data Service Owner; retrospective within 24 hours |

### 3.2 Standard Change Workflow

```
1. Requestor submits quota change request (ticket/ITSM)
   └── Includes: current quota, requested quota, justification, affected pool/VC

2. Data Platform Architect reviews
   └── Verifies parent pool has headroom
   └── Checks impact on other pools/services sharing the parent

3. Approval granted (or request returned with alternatives)

4. Platform Admin or Data Service Owner executes change
   └── Uses the appropriate UI (Management Console or data service UI)
   └── Does NOT use kubectl or direct Kubernetes edits

5. Verification
   └── Confirm new quota is reflected in the service UI
   └── Confirm Management Console pool utilization is consistent

6. Update pool registry with new quota values and change date
```

### 3.3 Change Freeze Windows

- Production quota changes should not be made within 48 hours of a scheduled major release or data service upgrade.
- Define a change freeze period before quarter-end or other high-utilization business periods.
- Emergency changes during freeze windows require explicit approval from the Data Platform Architect or SRE lead.

---

## 4. Review Cadence

### 4.1 Scheduled Reviews

| Review | Frequency | Owner | Purpose |
|--------|-----------|-------|---------|
| Pool utilization review | Monthly | SRE / Operations | Identify pools approaching 80% utilization; flag for upcoming increases |
| Quota sizing review | Quarterly | Data Platform Architect + Data Service Owners | Validate quota allocations against actual workload growth; adjust forecasts |
| Ownership audit | Quarterly | Platform Administrator | Confirm all pools have documented owners; remove or reassign orphaned pools |
| Incident retrospective | After each quota exhaustion incident | Data Platform Architect + affected Data Service Owner | Root cause analysis; identify preventive quota or process changes |
| Annual capacity review | Annually | Data Platform Architect | Full capacity planning exercise; re-baseline quotas against hardware refresh and workload projections |

### 4.2 Review Checklist

For each monthly pool utilization review:

- [ ] List all pools with current and maximum quota values.
- [ ] Flag any pool at ≥ 80% of its quota (CPU, memory, or GPU) for the past 30 days.
- [ ] Review the trend: is utilization growing, stable, or declining?
- [ ] For pools approaching 80%: initiate a Standard change request to increase quota or identify workloads to rebalance.
- [ ] Confirm no orphaned pools (pools with no documented owner or active workloads).

---

## 5. Multi-Tenancy and Isolation

### 5.1 Tenant Isolation Principles

In environments where multiple business units or external customers share CDP infrastructure:

- **Allocate dedicated pools per tenant** at the top level of the pool hierarchy. Do not co-locate tenants within a shared pool without sub-pool isolation.
- **Do not share Kubernetes namespaces** across tenants. Each data service component for each tenant should run in its own namespace.
- **Network policies** should be applied to prevent cross-tenant namespace traffic. [Assumption — verify with your network configuration]
- **Quota enforcement** is mandatory for multi-tenant environments. An unlimited quota for one tenant can exhaust the shared pool and starve others.

### 5.2 Tenant Onboarding

When onboarding a new tenant to the platform:

1. Create a dedicated resource pool for the tenant (following naming conventions).
2. Set an initial quota based on the tenant's stated workload requirements.
3. Assign the tenant's data service components (workspaces, virtual clusters, VWs) to the tenant pool.
4. Document the tenant pool in the pool registry with the tenant's designated Data Service Owner.
5. Inform the tenant of their quota limits and the process for requesting increases.

---

## 6. Documentation Standards

### 6.1 Pool Registry

Maintain a pool registry document or infrastructure-as-code record with at minimum:

| Field | Description |
|-------|-------------|
| Pool Name | The exact name as it appears in the Management Console |
| Parent Pool | The parent in the hierarchy |
| Service | Which data service(s) use this pool |
| Environment Tier | prod / dev / staging / sandbox |
| CPU Quota | In cores |
| Memory Quota | In GiB |
| GPU Quota | Count (0 if none) |
| Owner Team | Team responsible for the pool |
| Owner Contact | Primary contact (name or alias) |
| Justification | Why this quota was set; linked change ticket(s) |
| Last Reviewed | Date of last review |

### 6.2 Runbook Requirements

Every data service (CAI, CDE, CDW) must have a quota management runbook covering:

- How to view current quota utilization (data service UI + Management Console steps).
- How to identify quota exhaustion (symptoms, logs, kubectl commands).
- How to submit a quota increase request (who to contact, what information to include).
- How to execute an emergency quota increase (on-call SRE procedure).

---

## 7. Compliance and Audit

- Quota change logs must be retained for a minimum of 12 months for audit purposes.
- Access to the Management Console resource pool management functions should be restricted to Platform Administrators. Data Service Owners should have quota management access within their own service UIs only.
- Quarterly group and user quota audits in CAI should be performed by the Security / Compliance team to verify no unauthorized quota escalations have occurred.

---

## References and Notes

- **[Recommendation]** All naming conventions, review cadences, and change process steps are operational best practices. Adapt to the specific ITSM and change management tooling in use at your organization.
- **[Assumption]** Network policy enforcement for cross-tenant isolation is a Kubernetes-level concern. Verify that the CDP cluster network configuration supports and enforces network policies.
- **[Recommendation]** The pool registry format is a suggestion. Infrastructure-as-code (e.g., Terraform, Ansible) with embedded comments and version history is preferable to a standalone spreadsheet where feasible.
