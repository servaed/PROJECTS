# 06 — Checklists

## Overview

This document provides actionable checklists for three scenarios: initial deployment of Cloudera Data Services with quota management, ongoing operational monitoring, and periodic quota reviews. Use these checklists in conjunction with the service-specific guidance in documents 01–05.

---

## 1. Pre-Deployment Checklist

Use this checklist before provisioning any Cloudera Data Service in a new environment.

### 1.1 Cluster Capacity Baseline

- [ ] Total cluster CPU, memory, and GPU capacity has been inventoried and documented.
- [ ] Kubernetes node pool composition is documented (node types, CPU, memory, GPU per node).
- [ ] Expected Kubernetes system component overhead has been estimated and reserved (typically 10–20% of total capacity).
- [ ] Cluster autoscaler settings are documented: minimum and maximum node counts per node pool.

### 1.2 Resource Pool Hierarchy Design

- [ ] Pool hierarchy design has been approved by the Data Platform Architect.
- [ ] A dedicated control-plane reserve pool has been defined (minimum 10% of total CPU and memory).
- [ ] Production and non-production pools are separated at the top level.
- [ ] Service-level pools (CAI-Prod, CDE-Prod, CDW-Prod, etc.) are defined with documented CPU, memory, and GPU allocations.
- [ ] Sum of all child pool allocations does not exceed the parent pool quota.
- [ ] Pool naming follows the organization's naming convention (see [docs/05-governance-and-operating-model.md](05-governance-and-operating-model.md)).
- [ ] Each pool has a documented owner and is entered in the pool registry.

### 1.3 GPU Readiness (if applicable)

- [ ] GPU node pool is configured with appropriate node labels and taints.
- [ ] GPU device plugin (e.g., NVIDIA device plugin) is installed and verified on GPU nodes.
- [ ] GPU resource pools are defined and assigned to GPU node pools.
- [ ] GPU quota is not allocated to non-GPU pools.

### 1.4 Cloudera AI Pre-Deployment

- [ ] CAI workspace resource pool is identified and has sufficient CPU, memory, and GPU quota.
- [ ] Default user quota values have been defined (not left unlimited).
- [ ] Resource profiles (Small, Medium, Large, GPU) have been defined.
- [ ] GPU resource profiles are restricted to users who require GPU access.
- [ ] Session auto-timeout policy has been configured for GPU sessions.
- [ ] LDAP/AD group synchronization is configured if group quotas will be used.

### 1.5 Cloudera Data Engineering Pre-Deployment

- [ ] CDE service pool is identified and sized to accommodate virtual cluster guaranteed quotas plus overhead.
- [ ] At least one virtual cluster for production and one for development/testing are planned.
- [ ] Virtual cluster guaranteed and maximum quotas are defined.
- [ ] GPU virtual cluster is planned separately from CPU virtual clusters (if GPU workloads are expected).
- [ ] CDE service quota includes 5–10% overhead for CDE control-plane components.
- [ ] Team has confirmed: quota changes will be made through the CDE UI only, never via Management Console or kubectl.

### 1.6 Cloudera Data Warehouse Pre-Deployment

- [ ] CDW environment pool is sized for the aggregate peak of all planned Virtual Warehouses.
- [ ] Each Virtual Warehouse type (Hive, Impala) and its minimum/maximum node counts are documented.
- [ ] Database Catalog sizing has been assessed against expected partition count and VW count.
- [ ] Data Visualization instance quota is allocated in a dedicated sub-pool.
- [ ] Autoscaler node pool limits are aligned with the sum of all VW maximum node counts.
- [ ] Team has confirmed: quota changes will be made through the CDW UI only.

### 1.7 Governance Readiness

- [ ] Quota change management process is documented and communicated to all Data Service Owners.
- [ ] Pool registry document/template is created and populated with initial values.
- [ ] Runbooks for quota exhaustion response have been drafted for each data service.
- [ ] Monitoring and alerting for pool utilization thresholds (≥ 80%) has been configured.
- [ ] First monthly utilization review date is scheduled.

---

## 2. Operational Checklist

Use this checklist for ongoing operational monitoring of quota and resource pools. Run monthly or after any significant workload change.

### 2.1 Pool Utilization Monitoring

- [ ] Review Management Console Resource Utilization for all pools.
- [ ] Identify any pool where CPU, memory, or GPU utilization has exceeded 80% in the past 30 days.
- [ ] Identify any pool that has been consistently below 20% utilization (potential over-allocation).
- [ ] Check for pods in `Pending` state in data service namespaces: `kubectl get pods --all-namespaces | grep Pending`.
- [ ] Review Kubernetes events for ResourceQuota admission denials in active namespaces.

### 2.2 Per-Service Checks

**Cloudera AI:**
- [ ] Review workspace-level CPU, memory, and GPU utilization in the CAI admin UI.
- [ ] Check for idle GPU sessions consuming quota (GPU held but session idle).
- [ ] Verify default user quota is still appropriate for current user count and workload mix.
- [ ] Confirm no users have been granted unlimited or inappropriately large quota overrides.

**Cloudera Data Engineering:**
- [ ] Review virtual cluster resource utilization in the CDE UI.
- [ ] Identify any virtual cluster consistently at or near its maximum quota.
- [ ] Identify any virtual cluster consistently well below its guaranteed quota (candidate for rebalancing).
- [ ] Verify CDE service namespace quota has not been manually modified outside the CDE UI.

**Cloudera Data Warehouse:**
- [ ] Review each Virtual Warehouse's min/max node configuration and current scale.
- [ ] Check for VWs that are frequently hitting maximum scale (candidate for max node increase).
- [ ] Check for VWs idling at minimum scale for extended periods (candidate for min node reduction).
- [ ] Review Database Catalog namespace memory usage; flag if approaching quota limit.
- [ ] Review Data Visualization instance CPU/memory; flag if constrained.

### 2.3 Incident Follow-Up

- [ ] All quota exhaustion incidents from the past period have a completed retrospective.
- [ ] Preventive changes identified in retrospectives have been implemented or are tracked in the change backlog.
- [ ] Emergency quota changes made in the past period have been formally reviewed and either made permanent or rolled back.

### 2.4 Pool Registry Maintenance

- [ ] Pool registry is updated with any quota changes made in the past period.
- [ ] All active pools have a current owner documented.
- [ ] Orphaned pools (no active workloads, no documented owner) have been identified and flagged for decommission.

---

## 3. Periodic Review Checklist

Use this checklist quarterly or annually for deeper quota governance reviews.

### 3.1 Quota Right-Sizing Review

- [ ] Compare actual peak utilization (90th percentile over the review period) against current quota maximums for each pool and virtual cluster.
- [ ] Identify pools where peak utilization is consistently below 50% of maximum quota — these are candidates for reduction or reallocation.
- [ ] Identify pools where peak utilization is consistently above 70% of maximum quota — these need quota increase or workload rebalancing.
- [ ] Validate that guaranteed quotas (CDE virtual clusters) match the steady-state workload baseline, not peak demand.

### 3.2 Ownership and Access Audit

- [ ] Confirm each resource pool has a current owner in the pool registry.
- [ ] Verify Management Console administrative access is restricted to authorized Platform Administrators.
- [ ] Review CAI user and group quota assignments — confirm no unauthorized escalations.
- [ ] Confirm Data Service Owners manage quotas only within their designated service UI.
- [ ] Review LDAP/AD group-to-quota-tier mappings in CAI for accuracy.

### 3.3 Capacity Planning

- [ ] Gather 6–12 month workload growth projections from Data Service Owners.
- [ ] Estimate cluster capacity headroom against projected growth.
- [ ] Determine if hardware additions are required in the next planning period.
- [ ] Update the pool hierarchy design if new services or teams are being onboarded.
- [ ] Verify the control-plane reserve pool remains adequate as the number of active namespaces grows.

### 3.4 GPU Pool Review (if applicable)

- [ ] Review GPU utilization per pool and per virtual cluster / workspace.
- [ ] Identify idle or underutilized GPU allocations.
- [ ] Confirm GPU pools are mapped to correct GPU node pools in the Management Console.
- [ ] Review session timeout policies for GPU sessions in CAI.
- [ ] Verify no GPU quota has been inadvertently allocated to non-GPU node pools.

### 3.5 Documentation and Runbook Currency

- [ ] Pool registry is complete and reflects the current state of all resource pools.
- [ ] Service-specific quota runbooks are current with the deployed CDP version.
- [ ] Any features marked `[verify on upgrade]` in this documentation set have been reviewed following the most recent CDP upgrade.
- [ ] Governance process documentation (naming conventions, change process, review cadence) is still accurate and followed in practice.

### 3.6 Compliance and Audit

- [ ] Quota change log for the past 12 months is retained and accessible.
- [ ] No unauthorized changes to CDE or CDW namespace ResourceQuota objects are present in the audit trail.
- [ ] Multi-tenant environments have been audited to confirm pool isolation is intact.
- [ ] Security / Compliance team has reviewed and signed off on the quarterly quota audit.

---

## 4. Quota Exhaustion Response Checklist

Use this checklist during an active quota exhaustion incident.

### 4.1 Immediate Diagnosis (< 5 minutes)

- [ ] Identify the affected data service and environment (CAI / CDE / CDW, prod / dev).
- [ ] Check the data service UI for quota-exceeded error messages.
- [ ] Check the Management Console Resource Utilization view for the affected pool.
- [ ] Run: `kubectl get pods -n <affected-namespace> | grep Pending` to identify queued pods.
- [ ] Run: `kubectl describe resourcequota -n <affected-namespace>` to see current vs. limit.
- [ ] Run: `kubectl get events -n <affected-namespace> --sort-by='.lastTimestamp' | tail -20` to see admission rejections.

### 4.2 Determine Root Cause (< 15 minutes)

- [ ] Is the exhaustion at the namespace ResourceQuota level, the pool level, or both?
- [ ] What consumed the quota — a spike in normal workload, a runaway job, an accidental large allocation?
- [ ] Is there available headroom in the parent pool to increase the child pool quota?
- [ ] Can workloads be shed or deferred to free capacity without impacting SLAs?

### 4.3 Mitigation Options

| Option | When to Use | Action |
|--------|------------|--------|
| Increase pool quota (if parent has headroom) | Parent pool has available capacity | Management Console: increase child pool quota |
| Increase virtual cluster max quota (CDE) | CDE VW consistently at ceiling | CDE UI: increase virtual cluster maximum |
| Terminate idle GPU sessions (CAI) | GPU starvation due to idle sessions | CAI admin UI: identify and terminate idle sessions |
| Scale down a lower-priority VW (CDW) | CDW pool exhausted; lower-priority VW can be reduced | CDW UI: reduce lower-priority VW max nodes temporarily |
| Add nodes to cluster | No headroom anywhere; hardware is available | Cluster admin: add nodes; update pool quotas after |

- [ ] Selected mitigation action has been approved by the Data Service Owner (or on-call SRE for emergency).
- [ ] Mitigation has been executed using the appropriate UI (not kubectl or Management Console for CDE/CDW objects).
- [ ] Recovery verified: affected workloads are running; no more `Pending` pods.

### 4.4 Post-Incident Actions

- [ ] Document the incident: time, affected service, root cause, mitigation taken.
- [ ] Update the pool registry with any quota changes made during the incident.
- [ ] Schedule a retrospective within 24 hours.
- [ ] Identify preventive measures (alerting threshold, permanent quota increase, runbook update).
- [ ] Submit a Standard change request for any temporary emergency quota changes that should be made permanent.

---

## References and Notes

- **[Recommendation]** All checklist items are operational best practices. Adapt to organizational processes and tooling.
- The `kubectl` commands in Section 4.1 are for diagnosis only; do not use `kubectl` to directly modify ResourceQuota objects for CDE or CDW namespaces.
- Refer to service-specific documents for detailed quota configuration procedures:
  - [docs/02-cloudera-ai.md](02-cloudera-ai.md) — Cloudera AI
  - [docs/03-cloudera-data-engineering.md](03-cloudera-data-engineering.md) — CDE
  - [docs/04-cloudera-data-warehouse.md](04-cloudera-data-warehouse.md) — CDW
  - [docs/05-governance-and-operating-model.md](05-governance-and-operating-model.md) — Governance
