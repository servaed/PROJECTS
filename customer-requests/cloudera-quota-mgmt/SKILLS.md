# SKILLS.md — Domain Expertise Reference

This file documents the domain knowledge required to author, review, and maintain this documentation set. Use it to onboard new contributors and calibrate the expected level of technical depth.

---

## Required Knowledge Areas

### 1. Cloudera Data Platform (CDP) — On-Premises

| Skill | Level | Notes |
|-------|-------|-------|
| CDP Private Cloud Base architecture | Intermediate | Yarn, HDFS, Ozone as underlying services |
| CDP Private Cloud Experiences architecture | Intermediate | Data Services run on Kubernetes above the base layer |
| Cloudera Management Console | Intermediate | Resource pool creation, pool hierarchy, cluster registration |
| Kubernetes fundamentals | Intermediate | Namespaces, ResourceQuota objects, LimitRange, node pools |
| Helm and operator patterns | Basic | Cloudera services deploy via operators |

### 2. Cloudera Data Services

| Service | Skill Level | Key Concepts |
|---------|-------------|--------------|
| Cloudera AI (CAI / CML) | Intermediate | Workspaces, resource profiles, user/group quota, GPU sessions |
| Cloudera Data Engineering (CDE) | Intermediate | Services, virtual clusters, guaranteed/max quota, Spark workloads |
| Cloudera Data Warehouse (CDW) | Intermediate | Environments, Database Catalogs, Virtual Warehouses, autoscaling |

### 3. Resource Management Concepts

- **Hierarchical resource pools**: Parent/child pool relationships, quota subdivision.
- **Kubernetes ResourceQuota**: CPU requests/limits, memory requests/limits, GPU limits per namespace.
- **Guaranteed vs. burstable allocations**: Reserved capacity versus burst ceiling.
- **Autoscaling**: Cluster Autoscaler behavior, scale-out triggers, scale-in delays, quota interaction.
- **GPU resource management**: Device plugin model, exclusive GPU allocation per pod.

### 4. Capacity Planning

- Node sizing for CPU, memory, and GPU workloads.
- Headroom planning for control-plane and shared services (10–20% of total cluster capacity).
- Separation of production and non-production workloads at the pool level.
- Utilization monitoring and alerting via Prometheus/Grafana.

---

## Subject-Matter Expert Roles

| Role | Responsibilities |
|------|-----------------|
| Platform Administrator | Create and manage resource pools; enforce quota policies |
| Data Platform Architect | Design pool hierarchy, capacity plan, define naming conventions |
| SRE / Operations | Monitor utilization, respond to quota exhaustion alerts |
| Pre-Sales / Solution Engineer | Translate workload requirements into quota sizing recommendations |
| Data Service Owner (CAI / CDE / CDW) | Manage service-level quotas; coordinate with platform admin |

---

## Key Terminology

| Term | Definition |
|------|------------|
| Resource Pool | Named allocation of CPU, memory, and/or GPU within the cluster, managed hierarchically |
| Default Pool | The root node pool available when a cluster is registered; can be subdivided |
| Guaranteed Quota | Minimum resources reserved for a service; cannot be preempted by other tenants |
| Maximum Quota | Upper bound on resources a service may consume, including burst |
| Namespace Quota | A Kubernetes ResourceQuota applied to a namespace |
| Virtual Warehouse | A CDW compute unit; each has its own namespace and resource pool |
| Workspace (CAI) | A Cloudera AI deployment scoped to a namespace |
| Virtual Cluster (CDE) | A CDE compute unit carrying its own guaranteed and maximum quota |

---

## Assumptions and Limitations

- This documentation applies to CDP Private Cloud Data Services only. CDP Public Cloud has different quota mechanisms.
- GPU support in CDE and CAI requires specific CDP release versions; verify before advising customers.
- Cloudera public documentation is the authoritative source; this file is a supplement.
