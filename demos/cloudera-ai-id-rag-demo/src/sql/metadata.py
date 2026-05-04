"""Database schema discovery — builds schema context for LLM SQL generation.

Only exposes approved tables to prevent the LLM from accessing sensitive tables.
Column descriptions are included alongside types so the SQL model understands
the semantic meaning of each field without needing to inspect sample data.
"""

from __future__ import annotations

from src.config.settings import settings
from src.config.logging import get_logger
from src.connectors.db_adapter import get_table_names, get_table_schema

logger = get_logger(__name__)

_COLUMN_DESCRIPTIONS: dict[str, str] = {
    # ── Banking: msme_credit ──────────────────────────────────────────────
    "msme_credit.customer_id":    "foreign key -> customer.id",
    "msme_credit.region":         "city name (27 cities: Jakarta, Surabaya, Bandung, Denpasar, Jayapura, etc.)",
    "msme_credit.province":       "province name (DKI Jakarta, Jawa Barat, Bali, Papua, etc.)",
    "msme_credit.segment":        "MSME segment: Micro | Small | Medium",
    "msme_credit.outstanding":    "outstanding loan balance in IDR",
    "msme_credit.credit_quality": "OJK tier: Lancar (current) | DPK (special mention) | Kurang Lancar (substandard) | Macet (loss) — Kurang Lancar+Macet = NPL",
    "msme_credit.month":          "reporting month YYYY-MM (2025-04 to 2026-03)",

    # ── Banking: customer ─────────────────────────────────────────────────
    "customer.id":                "primary key",
    "customer.name":              "company name",
    "customer.segment":           "Corporate | MSME",
    "customer.region":            "home city",
    "customer.industry":          "industry sector (Manufacturing | Retail & Trade | Agriculture | Construction | etc.)",
    "customer.total_exposure":    "total credit exposure in IDR across all products",
    "customer.annual_revenue":    "estimated annual revenue in IDR",
    "customer.debt_service_ratio":"debt service ratio 0-1 (proportion of revenue used for debt payments; >0.5 = stressed)",
    "customer.internal_rating":   "internal credit rating: AA | A | A- | B+ | B | B-",
    "customer.onboard_date":      "customer onboarding date YYYY-MM-DD",

    # ── Banking: branch ───────────────────────────────────────────────────
    "branch.id":                  "primary key",
    "branch.name":                "branch office name",
    "branch.region":              "province",
    "branch.city":                "city",
    "branch.is_active":           "1 = active, 0 = inactive",
    "branch.customer_count":      "number of active customers",
    "branch.credit_target":       "annual credit disbursement target in IDR",
    "branch.credit_realization":  "actual credit disbursed in IDR",
    "branch.npl_amount":          "non-performing loan amount in IDR (credit_quality Kurang Lancar + Macet)",
    "branch.deposit_balance":     "total customer deposits held at this branch in IDR",
    "branch.roi_pct":             "return on investment % (higher NPL erodes ROI)",
    "branch.lat":                 "latitude of branch location",
    "branch.lon":                 "longitude of branch location",

    # ── Banking: loan_application ─────────────────────────────────────────
    "loan_application.id":                "primary key",
    "loan_application.branch_id":         "foreign key -> branch.id",
    "loan_application.city":              "city of the branch processing the application",
    "loan_application.loan_type":         "KUR Mikro | KUR Kecil | KUR Menengah (government-subsidised SME loans)",
    "loan_application.application_count": "total loan applications received this month",
    "loan_application.approved_count":    "applications approved",
    "loan_application.rejected_count":    "applications rejected",
    "loan_application.approval_rate_pct": "approval rate as percentage (approved/total * 100)",
    "loan_application.avg_processing_days":"average days to process an application",
    "loan_application.avg_loan_amount":   "average approved loan amount in IDR",
    "loan_application.month":             "reporting month YYYY-MM",

    # ── Telco: subscriber ─────────────────────────────────────────────────
    "subscriber.id":                "primary key",
    "subscriber.name":              "subscriber name",
    "subscriber.subscription_type": "Prepaid | Postpaid | Corporate",
    "subscriber.plan":              "Starter | Basic | Standard | Premium | Unlimited | Business | Enterprise",
    "subscriber.region":            "subscriber city",
    "subscriber.status":            "Active | Inactive",
    "subscriber.activation_date":   "YYYY-MM-DD",
    "subscriber.churn_risk_score":  "predicted churn risk 0-100 (>= 70 = high risk)",
    "subscriber.arpu_monthly":      "average revenue per user per month in IDR",
    "subscriber.tenure_months":     "months since activation (short tenure correlates with high churn)",
    "subscriber.monthly_complaints":"number of complaints filed in the last month",

    # ── Telco: network ────────────────────────────────────────────────────
    "network.id":              "primary key",
    "network.region":          "province",
    "network.city":            "city",
    "network.network_type":    "4G LTE | 4.5G | 5G",
    "network.bts_count":       "number of base transceiver stations",
    "network.capacity_mbps":   "total capacity in Mbps",
    "network.utilization_pct": "utilization % of capacity (>85% = Critical, 70-85% = High, <70% = Optimal)",
    "network.status":          "Optimal | High | Critical",
    "network.avg_latency_ms":  "average network latency in milliseconds (rises sharply above 70% utilization)",
    "network.packet_loss_pct": "packet loss percentage (0-3%; higher = worse quality)",
    "network.lat":             "latitude",
    "network.lon":             "longitude",

    # ── Telco: network_incident ───────────────────────────────────────────
    "network_incident.id":                "primary key",
    "network_incident.city":              "city where incidents occurred",
    "network_incident.month":             "reporting month YYYY-MM",
    "network_incident.incident_count":    "total network incidents (outages, degradation events)",
    "network_incident.resolved_count":    "incidents resolved within SLA",
    "network_incident.avg_downtime_hrs":  "average downtime per incident in hours",
    "network_incident.avg_resolution_hrs":"average time to resolve an incident in hours",
    "network_incident.mttr_hrs":          "mean time to resolve (MTTR) in hours",
    "network_incident.sla_breach_count":  "incidents that breached SLA resolution time (>4 hours)",

    # ── Telco: data_usage ─────────────────────────────────────────────────
    "data_usage.id":             "primary key",
    "data_usage.subscriber_id":  "foreign key -> subscriber.id",
    "data_usage.month":          "billing month YYYY-MM",
    "data_usage.quota_gb":       "data quota in GB",
    "data_usage.usage_gb":       "actual usage in GB",
    "data_usage.speed_mbps":     "average experienced speed",
    "data_usage.overage_charge": "overage charges in IDR",

    # ── Government: regional_budget ───────────────────────────────────────
    "regional_budget.id":             "primary key",
    "regional_budget.work_unit":      "government agency (SKPD)",
    "regional_budget.program":        "budget program name",
    "regional_budget.budget_ceiling": "approved budget in IDR",
    "regional_budget.realization":    "actual spending in IDR",
    "regional_budget.quarter":        "Q1 | Q2 | Q3 | Q4",
    "regional_budget.year":           "fiscal year",

    # ── Government: public_service ────────────────────────────────────────
    "public_service.id":                  "primary key",
    "public_service.service_type":        "service name (KTP Elektronik | IMB/PBG | Paspor | etc.)",
    "public_service.agency":              "responsible agency",
    "public_service.application_count":   "total applications received",
    "public_service.on_time_count":       "completed on time",
    "public_service.pending_count":       "applications still pending / backlogged",
    "public_service.satisfaction_pct":    "citizen satisfaction score 0-100 (IKM target >= 82)",
    "public_service.complaint_count":     "complaints filed about this service",
    "public_service.avg_processing_days": "average processing days",
    "public_service.month":               "reporting month YYYY-MM",

    # ── Government: resident ──────────────────────────────────────────────
    "resident.id":       "primary key",
    "resident.district": "kecamatan name",
    "resident.city":     "city / kabupaten",
    "resident.province": "province",
    "resident.total":    "total registered residents",
    "resident.male":     "male count",
    "resident.female":   "female count",
    "resident.year":     "census year",
}


def get_approved_tables() -> list[str]:
    """Return the intersection of approved tables and tables that actually exist."""
    existing = get_table_names()
    approved = settings.approved_tables
    if not approved:
        return existing
    visible = [t for t in approved if t in existing]
    hidden  = [t for t in approved if t not in existing]
    if hidden:
        logger.warning("Approved tables not found in database: %s", hidden)
    return visible


def build_schema_context(tables: list[str] | None = None) -> str:
    """Build an enriched schema description for SQL generation."""
    if tables is None:
        tables = get_approved_tables()
    if not tables:
        return "No tables available."

    header = "IMPORTANT: Use ONLY the exact table names listed below. Do not substitute with any other names.\n"
    lines = [header]
    for table in tables:
        try:
            columns = get_table_schema(table)
            col_lines = []
            for c in columns:
                desc = _COLUMN_DESCRIPTIONS.get(f"{table}.{c['name']}", "")
                desc_str = f"  -- {desc}" if desc else ""
                col_lines.append(f"  {c['name']} ({c['type']}){desc_str}")
            lines.append(f"Table: {table}\nColumns:\n" + "\n".join(col_lines))
        except Exception as exc:
            logger.error("Failed to get schema for table '%s': %s", table, exc)
    return "\n\n".join(lines)
