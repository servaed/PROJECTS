# 06 — Checklists, Troubleshooting, and FAQ

## 6.1 Pre-Deployment Checklist

Complete this checklist before activating any new data service environment.

### Platform-level

- [ ] Cluster total capacity (vCPU, RAM, GPU devices) is documented.
- [ ] A named `shared-services` pool is carved out for control-plane components
      (minimum 10% of cluster capacity).
- [ ] Production and non-production pools are defined at the cluster level before
      any service pools are created.
- [ ] GPU nodes are labeled/tainted to prevent non-GPU workloads from landing on them.
- [ ] Resource pool naming convention is agreed and documented.
- [ ] Platform pool ownership is documented (who owns the default pool, shared-services pool).
- [ ] Monitoring alerts for 80% / 95% pool utilisation are configured.

### Cloudera AI

- [ ] CAI workspace pool is sized with Kubernetes overhead factored in.
- [ ] Standard resource profiles (Small / Medium / Large / GPU) are defined before
      users are onboarded.
- [ ] GPU profiles are only created if the workspace pool includes GPU quota.
- [ ] Idle session timeout is configured for all session types.
- [ ] Per-user or per-group quota limits are set to prevent monopolisation.
- [ ] Workspace ownership is documented and an admin contact is defined.
- [ ] Production and development workspaces are in separate pools.

### Cloudera Data Engineering

- [ ] CDE service pool includes overhead for Airflow, API server, and metadata pods
      (minimum 3–6 vCPU / 12–24 GiB above the sum of VC quotas).
- [ ] Virtual clusters are created with descriptive names following the naming convention.
- [ ] Production VCs have a guaranteed quota set; dev VCs have guaranteed = 0.
- [ ] GPU virtual clusters are only created within services that have GPU quota.
- [ ] Executor idle timeout is configured for each VC.
- [ ] A separate VC exists for each major workload class (ETL, streaming, ML, dev).
- [ ] CDE-created resource pools are not modified in the Management Console UI.

### Cloudera Data Warehouse

- [ ] CDW environment pool is sized as sum of all component maximums + 20% overhead.
- [ ] A dedicated Database Catalog is provisioned per environment (prod vs. dev).
- [ ] Production Virtual Warehouses have minimum clusters ≥ 1.
- [ ] VW maximum cluster count is set based on the VW pool maximum, not the env pool.
- [ ] Separate VWs are provisioned for interactive BI and batch reporting workloads.
- [ ] Data Visualization instances are sized for concurrent user count.
- [ ] CDW-created namespaces are not edited via kubectl or Management Console UI.
- [ ] Autoscaling parameters (min/max, scale-down timeout) are documented per VW.

---

## 6.2 Day-2 Operations Review Checklist

Run this checklist monthly (utilisation) and quarterly (capacity planning).

### Monthly utilisation review

- [ ] Pull average and peak CPU utilisation per pool for the past 30 days.
- [ ] Pull average and peak memory utilisation per pool for the past 30 days.
- [ ] Check GPU utilisation and idle percentage for GPU-enabled pools.
- [ ] Identify pools with average utilisation > 70% → flag for expansion review.
- [ ] Identify pools with average utilisation < 20% → flag for reclamation review.
- [ ] Review CDE virtual cluster queue depth history. Any persistent queuing?
- [ ] Review CDW Virtual Warehouse autoscaling events. Frequent scale-up/down cycling?
- [ ] Review CAI workspace "Waiting for resources" events. Any persistent queuing?
- [ ] Check for any temporary quota increases that should now be reverted.
- [ ] Verify all pools have documented owners and last-reviewed dates.

### Quarterly capacity review

- [ ] Project workload growth for the next 6–12 months (new teams, new workloads).
- [ ] Model required capacity additions (CPU, memory, GPU) based on growth projections.
- [ ] Confirm cluster headroom is ≥ 30% at the cluster level.
- [ ] Verify hardware procurement lead times if expansion is needed.
- [ ] Review and update resource pool documentation for all changes made in the quarter.
- [ ] Circulate showback report to team/BU leads.
- [ ] Review naming conventions; rename any pools that violate the convention.

---

## 6.3 Troubleshooting Guide

### T1: Service creation fails with "insufficient resources" error

**Symptoms:** VW, VC, or workspace creation fails in the service UI with a capacity error.

**Steps:**
1. Open the Management Console resource pool view. Check the parent pool utilisation.
2. Compare the requested resource size against available headroom in the parent pool.
3. If headroom is insufficient: either reduce the requested size, or expand the parent pool.
4. If the parent pool appears to have headroom but creation still fails: check that
   the Kubernetes scheduler is not constrained by node taints, pod disruption budgets,
   or node-level resource fragmentation (too many small gaps).
5. Check the service UI for more detailed error messages; some services surface
   Kubernetes scheduler errors that clarify the specific constraint.

---

### T2: Autoscaling stalls — VW or VC does not scale up under load

**Symptoms:** Query queue grows; executor count stays flat; users report slow queries.

**Steps:**
1. Check the VW/VC resource pool utilisation in the service UI. Is the pool at maximum?
2. If the pool is at maximum: increase the VW/VC pool maximum (CDW: resize VW;
   CDE: edit VC quota) or reduce load by routing queries to another VW/VC.
3. If the pool is below maximum: check whether the parent environment/service pool
   is exhausted. A VC/VW cannot scale beyond its parent pool.
4. Verify that worker nodes have available capacity. Pool headroom does not help
   if all nodes are physically full — check `kubectl describe node` for pressure conditions.
5. Check for pod pending events: `kubectl get pods -n <namespace> | grep Pending`
   and `kubectl describe pod <pending-pod>` for scheduling failure reasons.

---

### T3: Jobs fail with GPU errors despite a GPU-enabled virtual cluster

**Symptoms:** Spark jobs that request GPUs fail at the executor stage with device errors.

**Steps:**
1. Verify the CDE service has a GPU quota allocated (CDE service settings).
2. Verify the virtual cluster has a GPU quota allocated (VC settings).
3. Verify that GPU worker nodes are available and not fully allocated to other pods:
   `kubectl describe nodes | grep -A5 "gpu"`.
4. Verify that the Spark job's executor configuration requests GPUs correctly
   (e.g., `spark.executor.resource.gpu.amount=1`).
5. If GPU nodes are present but pods are not scheduled there, check node taints
   and pod tolerations — GPU pods must tolerate the GPU node taint.

---

### T4: CAI sessions stuck in "Waiting for resources"

**Symptoms:** Users cannot start sessions; sessions remain in pending state.

**Steps:**
1. Check the CAI workspace resource utilisation dashboard. Is the workspace pool exhausted?
2. Identify which sessions are consuming the most resources. Are any sessions idle?
3. If idle sessions are holding resources: prompt users to stop idle sessions, or
   enable idle session timeout in workspace settings.
4. If the pool is genuinely exhausted: expand the workspace pool in the Management Console.
5. If expansion is not possible: reduce the default resource profile or implement
   per-user resource limits to prevent single users from exhausting the pool.

---

### T5: Unexplained resource consumption — pool is "full" but workloads seem light

**Symptoms:** Pool utilisation shows near-maximum consumption, but service dashboards
show few active workloads.

**Steps:**
1. List all pods in the service namespace:
   `kubectl get pods -n <namespace> -o wide`
2. Check pod resource requests (not just usage):
   `kubectl describe pod <pod> | grep -A5 Requests`
   Resource *requests* reserve capacity from the pool even if the pod is not
   actively using that capacity.
3. Look for zombie pods (Completed, CrashLoopBackOff) that are not cleaned up
   and whose requests still count against the quota.
4. Check for non-workload pods (monitoring agents, log collectors) that may have
   been deployed into the namespace and consume quota.
5. Run: `kubectl describe resourcequota -n <namespace>` to see the exact breakdown
   of used vs. hard quota.

---

### T6: Management Console shows pool at 100% but no service UI shows contention

**Symptoms:** Management Console resource pool shows 100% used, but CDW/CDE/CAI
UIs show no visible contention or errors.

**Likely cause:** Resource requests (Kubernetes `requests`) are fully allocated even
though actual CPU/memory utilisation is lower. This is normal — Kubernetes guarantees
are based on requests, not usage.

**Response:**
- This is not an immediate problem unless workloads are being queued or rejected.
- Review whether pool guaranteed values (requests) are set too high relative to actual usage.
- Consider reducing guaranteed values for low-utilisation pools to free up schedulable
  capacity for other pools.

---

## 6.4 Frequently Asked Questions

**Q: Can I share a resource pool between CDE and CDW?**

No. Each service manages its own pool sub-tree. Sharing a pool at the cluster level
is possible (both services draw from the same parent), but CDE and CDW should each
have their own named service-level pools to prevent one service from consuming the
other's capacity.

---

**Q: What happens if I edit a CDW or CDE pool in the Management Console UI?**

The service UI and the underlying Kubernetes resource quotas may become desynchronised.
This can cause creation failures, autoscaling errors, or unexpected capacity behavior.
Always use the service UI to change quotas for service-created pools.

---

**Q: Can two Virtual Warehouses share a Database Catalog?**

Yes, multiple VWs in the same CDW environment can share a Database Catalog. However,
the Database Catalog must be sized to handle the combined metadata query load from all
connected VWs. For production environments with many VWs, consider a dedicated
Database Catalog per workload domain.

---

**Q: How do I reclaim unused guaranteed quota?**

In the service UI, reduce the guaranteed (minimum) value for the pool or virtual
cluster. For CDE VCs, edit the VC quota. For CDW VWs, resize the VW (reduce minimum
cluster count). For CAI workspaces, reduce the workspace pool allocation in the
Management Console. Always verify the change does not impact running workloads.

---

**Q: How do GPU quotas interact with CPU/memory quotas?**

GPU quotas are an independent dimension. A pod can be blocked by a GPU quota even
if CPU and memory are available, and vice versa. Always specify all three dimensions
when sizing GPU-enabled pools.

---

**Q: What is the difference between a resource pool maximum and a hard limit?**

In the context of CDP Data Services, "maximum" in the service UI maps to Kubernetes
resource quota `hard` limits. A pod that requests more than the remaining `hard` limit
will not be scheduled. "Guaranteed" maps to the aggregate of pod `requests` — capacity
that is reserved regardless of overall cluster load.

---

**Q: Can I temporarily increase a quota for a one-off batch job?**

Yes. Follow the change process in [05-governance-and-operating-model.md](05-governance-and-operating-model.md).
Mark the change as temporary with a defined expiry date. The pool owner is responsible
for reverting it after the job completes.

---

**Q: How do I find out which team owns a resource pool?**

Check the platform asset registry or CMDB. If documentation is absent, check the
pool name (naming conventions encode team and environment), then escalate to the
platform engineering team as the default contact.

---

## References and Notes

- Troubleshooting steps involving `kubectl` commands require cluster-level access.
  Ensure your operations team has appropriate Kubernetes RBAC permissions.
- **[ASSUMPTION]** All troubleshooting steps assume CDP Private Cloud Data Services
  deployed on Kubernetes (OpenShift or ECS). Steps may differ for bare-metal deployments.
- FAQ answers are based on documented CDW, CDE, and CAI behavior. Edge cases may
  behave differently in specific release versions — verify against your release notes.
