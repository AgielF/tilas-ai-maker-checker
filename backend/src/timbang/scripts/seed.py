"""Demo data seed script.

Usage:
    cd backend
    python -m timbang.scripts.seed

Idempotent: running multiple times produces the same state (no duplicates).
Reads DATABASE_URL from environment / .env file via pydantic-settings.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from timbang.modules.audit.public_api import AuditFindingRepository, CheckResultRepository
from timbang.modules.audit.schemas import AuditFindingCreate, CheckResultCreate
from timbang.modules.procurement.public_api import PriceQuoteRepository, VendorRepository
from timbang.modules.procurement.schemas import PriceQuoteCreate, VendorCreate
from timbang.shared.core.config import get_settings
from timbang.shared.db.base import Base  # noqa: F401 — ensures all models are registered

# ── Seed data definitions ─────────────────────────────────────────────────────

_VENDORS = [
    VendorCreate(name="PT Sinar Elektronik"),
    VendorCreate(name="CV Maju Jaya"),
    VendorCreate(name="PT Global Supply"),
]

_LAPTOP_PRICES = [
    ("PT Sinar Elektronik", Decimal("8500000")),
    ("CV Maju Jaya", Decimal("8700000")),
    ("PT Global Supply", Decimal("12500000")),  # intentional outlier
]

_PRINTER_PRICES = [
    ("PT Sinar Elektronik", Decimal("2100000")),
    ("CV Maju Jaya", Decimal("2250000")),
    ("PT Global Supply", Decimal("2300000")),
]

_FINDINGS = [
    AuditFindingCreate(
        transaction_id="TRX-2026-0001",
        po_number="PO-001",
        severity="HIGH",
        amount=Decimal("250000000"),
        currency="IDR",
        description="Nilai PO di atas threshold approval L2",
        sop_reference="SOP_VALIDATION",
    ),
    AuditFindingCreate(
        transaction_id="TRX-2026-0002",
        po_number="PO-002",
        severity="MEDIUM",
        amount=Decimal("45000000"),
        currency="IDR",
        description="Selisih qty GR vs Invoice 5%",
        sop_reference="THREE_WAY_MATCH",
    ),
]

# Mapping: transaction_id → CheckResult status
_CHECK_STATUSES = {
    "TRX-2026-0001": "FAIL",
    "TRX-2026-0002": "WARN",
}


# ── Seed helpers ─────────────────────────────────────────────────────────────


async def _seed_vendors(
    vendor_repo: VendorRepository,
    quote_repo: PriceQuoteRepository,
) -> tuple[int, int]:
    """Insert vendors and price quotes. Skip existing by name / (vendor+item)."""
    vendors_created = 0
    quotes_created = 0

    # Build a name→vendor map, creating missing ones
    vendor_map: dict[str, object] = {}
    for vc in _VENDORS:
        existing = await vendor_repo.get_by_name(vc.name)
        if existing is not None:
            vendor_map[vc.name] = existing
        else:
            vendor = await vendor_repo.create(vc)
            vendor_map[vc.name] = vendor
            vendors_created += 1

    # Insert price quotes — idempotency check: same vendor + item_name
    all_items = [("Laptop i5", _LAPTOP_PRICES), ("Printer Laser", _PRINTER_PRICES)]
    for item_name, price_list in all_items:
        for vendor_name, price in price_list:
            vendor = vendor_map[vendor_name]
            existing_quotes = await quote_repo.list_by_vendor(vendor.id)
            already_exists = any(q.item_name == item_name for q in existing_quotes)
            if not already_exists:
                await quote_repo.create(
                    PriceQuoteCreate(
                        vendor_id=vendor.id,
                        item_name=item_name,
                        price=price,
                        currency="IDR",
                        source_url=None,
                    )
                )
                quotes_created += 1

    return vendors_created, quotes_created


async def _seed_audit(
    finding_repo: AuditFindingRepository,
    check_repo: CheckResultRepository,
) -> tuple[int, int]:
    """Insert audit findings and check results. Skip by transaction_id."""
    findings_created = 0
    checks_created = 0

    for finding_data in _FINDINGS:
        existing = await finding_repo.list_by_transaction(finding_data.transaction_id)
        if existing:
            # Already seeded — also ensure check result exists
            for f in existing:
                existing_checks = await check_repo.list_by_finding(f.id)
                if not existing_checks:
                    status = _CHECK_STATUSES.get(finding_data.transaction_id, "PASS")
                    await check_repo.create(CheckResultCreate(finding_id=f.id, status=status))
                    checks_created += 1
            continue

        finding = await finding_repo.create(finding_data)
        findings_created += 1

        status = _CHECK_STATUSES.get(finding_data.transaction_id, "PASS")
        await check_repo.create(CheckResultCreate(finding_id=finding.id, status=status))
        checks_created += 1

    return findings_created, checks_created


# ── Main ─────────────────────────────────────────────────────────────────────


async def main(db_url: str | None = None) -> None:
    """Run the seed script against the configured database.

    Args:
        db_url: Override database URL (e.g. for tests or local SQLite).
                Falls back to SEED_DATABASE_URL env var, then settings.database_url.
    """
    import os

    settings = get_settings()
    url = db_url or os.environ.get("SEED_DATABASE_URL") or settings.database_url
    engine = create_async_engine(url, echo=False)

    # Create all tables (safe — CREATE TABLE IF NOT EXISTS via checkfirst=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        vendor_repo = VendorRepository(session)
        quote_repo = PriceQuoteRepository(session)
        finding_repo = AuditFindingRepository(session)
        check_repo = CheckResultRepository(session)

        vendors_created, quotes_created = await _seed_vendors(vendor_repo, quote_repo)
        findings_created, checks_created = await _seed_audit(finding_repo, check_repo)

    await engine.dispose()

    # ── Summary ───────────────────────────────────────────────────────────────
    async with session_factory() as session:
        vendor_repo = VendorRepository(session)
        quote_repo = PriceQuoteRepository(session)
        finding_repo = AuditFindingRepository(session)

        total_vendors = len(await vendor_repo.list(limit=1000))
        total_quotes = len(await quote_repo.list(limit=1000))
        total_findings = len(await finding_repo.list(limit=1000))

    await engine.dispose()

    print("=" * 50)
    print("  Tilas — Seed Script")
    print("=" * 50)
    print(f"  Vendors       : {total_vendors:>4}  (+{vendors_created} new)")
    print(f"  Price Quotes  : {total_quotes:>4}  (+{quotes_created} new)")
    print(f"  Audit Findings: {total_findings:>4}  (+{findings_created} new)")
    print(f"  Check Results : {'n/a':>4}  (+{checks_created} new)")
    print("=" * 50)
    print("  Done. Database is ready for demo.")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
