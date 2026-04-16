# 05 — Governance and Operating Model

## 5.1 Why Governance Matters for Quota Management

Resource quotas without governance become meaningless over time. Without clear ownership,
naming conventions, and change processes:

- Quotas grow through ad-hoc increases and are never reclaimed.
- No one knows who owns a pool or why it was sized a certain way.
- Incidents caused by resource exhaustion are hard to diagnose because utilisation
  history and ownership are not tracked.
- Chargeback and capacity planning are impossible.

A governance model defines **who can change what, how they request it, and how it is
reviewed**. It converts quota management from an ad-hoc operational task into a
repeatable, auditable process.

---

## 5.2 Ownership Model

Every resource pool should have a documented owner. Ownership implies:

| Responsibility | Detail |
|---|---|
| Requesting quota changes | The owner initiates change requests; no other party can request on their behalf |
| Monitoring utilisation | The owner reviews utilisation reports and initiates right-sizing |
| Approving sub-pool allocation | The owner approves how their pool is subdivided to child teams |
| Incident response | The owner is the first contact for resource-related incidents within their pool |

**Recommended ownership tiers:**

| Pool level | Owner role |
|---|---|
| Cluster default pool | Platform engineering / infra team |
| Service-level pool (CDW env, CDE service, CAI workspace) | Service owner (e.g., data platform team) |
| Virtual cluster / virtual warehouse | Team lead or application owner |
| Individual user / team quota (CAI) | Workspace administrator |

---

## 5.3 Naming Conventions

Consistent naming makes pools discoverable, searchable, and unambiguous in monitoring.

**Recommended pattern:** `<service>-<environment>-<team-or-workload>`

| Component | Examples |
|---|---|
| CDE service | `cde-prod`, `cde-dev`, `cde-finops` |
| CDE virtual cluster | `vc-etl-daily`, `vc-streaming-ops`, `vc-ml-featureeng` |
| CDW environment | `cdw-prod`, `cdw-staging` |
| CDW Virtual Warehouse | `vw-hive-bi`, `vw-impala-reporting`, `vw-impala-adhoc` |
| CAI workspace | `cai-ws-datascience-prod`, `cai-ws-research-dev` |
| Resource pool | `pool-cai-prod`, `pool-cde-finance-prod` |

**Naming rules:**
- Use lowercase and hyphens only (no spaces, underscores, or mixed case).
- Include environment (`prod`, `dev`, `staging`) in every name.
- Avoid generic names like `default2`, `test`, `new-pool`.
- Prefix team names consistently (e.g., `fin-`, `ops-`, `ds-`) if multiple teams
  share a service.

---

## 5.4 Change Process

All quota changes should go through a lightweight but auditable change process.

**Recommended change workflow:**

```
1. Request
   → Pool owner submits a quota change request (ticket/JIRA/email) with:
     - Target pool name
     - Current quota values
     - Requested quota values
     - Business justification
     - Expected duration (permanent or temporary)

2. Review
   → Platform admin reviews:
     - Available headroom in the parent pool
     - Impact on sibling pools
     - Whether the change requires resizing the parent pool

3. Approval
   → Approved by: platform admin (routine) or infra/capacity committee (large changes)

4. Implementation
   → Platform admin makes the change in the service UI
   → Change is logged (ticket updated, runbook entry, or CMDB record)

5. Validation
   → Requestor validates that the change resolves their need
   → Admin confirms no other pool was adversely affected

6. Review date
   → Temporary increases: auto-expire after 30/60/90 days
   → Permanent increases: reviewed at next quarterly capacity review
```

**[RECOMMENDATION]** Require a written justification for any quota increase above 20%
of the current value. Track all changes in a ticketing system (ServiceNow, Jira, etc.)
for audit purposes.

---

## 5.5 Capacity Planning

Capacity planning connects observed utilisation to future hardware investment.

**Quarterly capacity review process:**

1. **Pull utilisation reports** for each service pool (CDW, CDE, CAI) for the previous quarter.
2. **Identify pools above 70% average utilisation** — these are candidates for expansion.
3. **Identify pools below 20% average utilisation** — these are candidates for reclamation.
4. **Project growth** based on business plans (new teams onboarding, new workloads, growth in data volume).
5. **Model headroom** — target 30% free headroom at the cluster level at all times.
6. **Raise hardware acquisition requests** with a 6–12 month lead time if expansion is needed.

**Key metrics to track per pool:**

| Metric | Target | Action if exceeded |
|---|---|---|
| Average CPU utilisation | < 70% of pool maximum | Investigate, may indicate need for pool expansion |
| Peak CPU utilisation | < 90% of pool maximum | Immediate review; may need more headroom |
| Average memory utilisation | < 70% of pool maximum | Same as CPU |
| GPU utilisation (idle %) | < 20% idle during business hours | Review session policies; reclaim underused GPUs |
| Queue depth (CDE/CDW) | 0 for >95% of time | Persistent queuing = capacity expansion signal |

---

## 5.6 Separation of Production and Non-Production

This is the single most important isolation decision. It should be made at the start of
the platform lifecycle, not retroactively.

**Why separate pools are required:**

- Development workloads are unpredictable — a developer running a full-dataset scan
  can consume an entire shared pool and block production jobs.
- Production pools need guaranteed quotas; dev pools should use max-only.
- Security and data access policies differ between environments.
- Autoscaling triggers and idle timeouts are different for prod vs. dev.

**Implementation pattern:**

| Layer | Production | Non-production |
|---|---|---|
| Cluster pool | `production` (70% guaranteed) | `non-production` (10% guaranteed, 30% max) |
| CDW | `cdw-prod` environment | `cdw-dev` environment |
| CDE | `cde-prod` service | `cde-dev` service |
| CAI | `cai-ws-prod` workspace | `cai-ws-dev` workspace |

---

## 5.7 Least-Privilege Resource Allocation

Least-privilege applies to resources as well as access:

- **Allocate the minimum quota needed** to meet the workload's SLA. Do not pre-allocate
  capacity "just in case" — use elastic (max > guaranteed) pools for workloads that
  can tolerate variability.
- **Review and reclaim** unused guaranteed quota quarterly. A pool with 100 vCPU
  guaranteed but 15% average utilisation is wasting 85 vCPU that could serve other teams.
- **Do not set default workspace profiles to "Large"** in CAI. Users will use whatever
  default they are given. Start with "Small" as the default and let users escalate.

---

## 5.8 Monitoring and Alerting

Quota management without monitoring is reactive. The following monitoring practices
are recommended.

**Management Console:**
- Use the resource utilisation views to track pool usage at the cluster level.
- Set up alerts for pools exceeding 80% utilisation (warn) and 95% (critical).

**Service-level monitoring:**
- CAI: workspace dashboard shows session count and resource consumption per user.
- CDE: CDE UI shows VC utilisation, job queue depth, and executor count over time.
- CDW: CDW UI shows VW scaling events, query queue depth, and cluster utilisation.

**[RECOMMENDATION]** Export Kubernetes resource quota metrics to a centralised
monitoring system (Prometheus + Grafana, or equivalent). Create dashboards per
service and per pool level. Alert on:
- `kube_resourcequota_used / kube_resourcequota_hard > 0.8` (CPU or memory)
- Persistent non-zero executor queue depth in CDE
- Persistent non-zero query queue in CDW admission control

---

## 5.9 Chargeback and Showback

Even without formal chargeback, a showback model (showing teams what they consume)
improves accountability.

**[RECOMMENDATION]** Implement a monthly showback report that includes, per team or
business unit:

- Average CPU and memory consumption (guaranteed + burst)
- GPU hours consumed (if applicable)
- Peak resource usage and when it occurred
- Ratio of consumed to allocated quota

This information supports quota right-sizing, budget justification, and architectural
discussions with business stakeholders.

---

## 5.10 Documentation Requirements

Every resource pool should have a corresponding entry in a platform asset registry
(CMDB, Confluence, wiki) with:

| Field | Description |
|---|---|
| Pool name | Exact name as shown in Management Console / service UI |
| Service | CAI / CDE / CDW |
| Environment | prod / dev / staging |
| Owner team | Name + contact |
| CPU guaranteed / max | Current values |
| Memory guaranteed / max | Current values |
| GPU quota | Current value (0 if none) |
| Last reviewed | Date of last capacity review |
| Change ticket | Link to last change request |
| Notes | Any special conditions or temporary increases |

---

## References and Notes

- Governance recommendations in this section are operational best practices, not
  product features. **[RECOMMENDATION]** labels indicate advisor guidance.
- The change workflow described is a suggested pattern. Adapt it to your organization's
  existing ITSM processes.
- Kubernetes resource quota metrics (`kube_resourcequota_*`) are available via the
  `kube-state-metrics` exporter, which is typically deployed in CDP Private Cloud
  Kubernetes environments.
- **[ASSUMPTION]** Prometheus and Grafana availability in your CDP environment depends
  on your observability stack deployment. CDP Private Cloud includes some built-in
  monitoring; verify what is available before planning external integrations.
