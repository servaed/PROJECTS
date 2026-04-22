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

# ── Column-level descriptions ──────────────────────────────────────────────
# Maps "table.column" → human-readable description injected into the schema
# context so the LLM generates semantically correct queries.

_COLUMN_DESCRIPTIONS: dict[str, str] = {
    # ── Banking: msme_credit ──────────────────────────────────────────────
    "msme_credit.id":             "primary key",
    "msme_credit.customer_id":    "foreign key -> customer.id",
    "msme_credit.region":         "city or region (e.g. Jakarta, Bandung, Bali)",
    "msme_credit.segment":        "MSME segment: Micro | Small | Medium",
    "msme_credit.outstanding":    "outstanding loan balance in IDR (rupiah)",
    "msme_credit.credit_quality": "OJK credit quality: Lancar | DPK | Kurang Lancar | Macet",
    "msme_credit.month":          "reporting month (YYYY-MM, e.g. 2026-03)",

    # ── Banking: customer ─────────────────────────────────────────────────
    "customer.id":              "primary key",
    "customer.name":            "customer full name",
    "customer.segment":         "customer segment: Corporate | MSME",
    "customer.region":          "home region/city",
    "customer.total_exposure":  "total credit exposure across all products in IDR",
    "customer.internal_rating": "internal credit rating: AA | A | B | etc.",
    "customer.onboard_date":    "date the customer was onboarded (YYYY-MM-DD)",

    # ── Banking: branch ───────────────────────────────────────────────────
    "branch.id":                 "primary key",
    "branch.name":               "branch office name",
    "branch.region":             "region/province",
    "branch.city":               "city",
    "branch.is_active":          "branch status: 1 = active, 0 = inactive",
    "branch.customer_count":     "number of active customers at this branch",
    "branch.credit_target":      "annual credit disbursement target in IDR",
    "branch.credit_realization": "actual credit disbursed to date in IDR",

    # ── Telco: subscriber ─────────────────────────────────────────────────
    "subscriber.id":                "primary key",
    "subscriber.name":              "subscriber name",
    "subscriber.subscription_type": "subscription type: Prepaid | Postpaid | Corporate",
    "subscriber.plan":              "active plan name (Starter | Basic | Standard | Premium | Unlimited | Business | Enterprise)",
    "subscriber.region":            "subscriber region/city",
    "subscriber.status":            "account status: Active | Inactive",
    "subscriber.activation_date":   "activation date (YYYY-MM-DD)",
    "subscriber.churn_risk_score":  "predicted churn risk 0-100; >= 70 = high risk",
    "subscriber.arpu_monthly":      "average revenue per user per month in IDR",

    # ── Telco: network ────────────────────────────────────────────────────
    "network.id":              "primary key",
    "network.region":          "region/province",
    "network.city":            "city",
    "network.network_type":    "network generation: 4G LTE | 4.5G | 5G",
    "network.bts_count":       "number of base transceiver stations",
    "network.capacity_mbps":   "total network capacity in Mbps",
    "network.utilization_pct": "current utilization as percentage of capacity (0-100)",
    "network.status":          "operational status: Optimal | High | Critical",

    # ── Telco: data_usage ─────────────────────────────────────────────────
    "data_usage.id":             "primary key",
    "data_usage.subscriber_id":  "foreign key -> subscriber.id",
    "data_usage.month":          "billing month (YYYY-MM)",
    "data_usage.quota_gb":       "subscribed data quota in GB",
    "data_usage.usage_gb":       "actual data usage in GB",
    "data_usage.speed_mbps":     "average experienced speed in Mbps",
    "data_usage.overage_charge": "overage charges in IDR",

    # ── Government: regional_budget ───────────────────────────────────────
    "regional_budget.id":             "primary key",
    "regional_budget.work_unit":      "government work unit / agency (SKPD) name",
    "regional_budget.program":        "budget program name",
    "regional_budget.budget_ceiling": "approved budget ceiling in IDR",
    "regional_budget.realization":    "actual spending to date in IDR",
    "regional_budget.quarter":        "fiscal quarter: Q1 | Q2 | Q3 | Q4",
    "regional_budget.year":           "fiscal year (e.g. 2025)",

    # ── Government: public_service ────────────────────────────────────────
    "public_service.id":                  "primary key",
    "public_service.service_type":        "service type (e.g. KTP Elektronik, IMB/PBG, Paspor)",
    "public_service.agency":              "responsible government agency",
    "public_service.application_count":   "total applications received",
    "public_service.on_time_count":       "applications completed on time",
    "public_service.satisfaction_pct":    "citizen satisfaction rate 0-100 (%)",
    "public_service.avg_processing_days": "average processing time in working days",
    "public_service.month":               "reporting month (YYYY-MM)",

    # ── Government: resident ──────────────────────────────────────────────
    "resident.id":       "primary key",
    "resident.district": "sub-district name (kecamatan)",
    "resident.city":     "city or kabupaten",
    "resident.province": "province name",
    "resident.total":    "total registered resident count",
    "resident.male":     "male resident count",
    "resident.female":   "female resident count",
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
    """Build an enriched text schema description for SQL generation.

    Includes column types AND semantic descriptions so the LLM generates
    semantically correct queries.
    """
    if tables is None:
        tables = get_approved_tables()

    if not tables:
        return "No tables available."

    # Prepend an explicit reminder so the LLM uses exact table names, not Indonesian equivalents.
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
