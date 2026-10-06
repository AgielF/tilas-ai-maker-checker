"""Procurement repository — the ONLY layer that uses AsyncSession.

Dependency Rule: repository ← service ← router.
No other module layer may import AsyncSession or call DB directly.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from timbang.modules.procurement.models import PriceQuote, ProcurementDocument, Vendor
from timbang.modules.procurement.schemas import PriceQuoteCreate, VendorCreate


class VendorRepository:
    """Data access layer for Vendor entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: uuid.UUID) -> Vendor | None:
        result = await self._session.execute(select(Vendor).where(Vendor.id == id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Vendor | None:
        result = await self._session.execute(select(Vendor).where(Vendor.name == name))
        return result.scalar_one_or_none()

    async def create(self, data: VendorCreate) -> Vendor:
        vendor = Vendor(**data.model_dump())
        self._session.add(vendor)
        await self._session.commit()
        await self._session.refresh(vendor)
        return vendor

    async def update(self, vendor: Vendor) -> Vendor:
        self._session.add(vendor)
        await self._session.commit()
        await self._session.refresh(vendor)
        return vendor

    async def deactivate(self, id: uuid.UUID) -> Vendor | None:
        vendor = await self.get(id)
        if vendor is None:
            return None
        vendor.is_active = False
        return await self.update(vendor)

    async def list(self, limit: int = 50) -> list[Vendor]:
        result = await self._session.execute(select(Vendor).limit(limit))
        return list(result.scalars().all())

    async def list_active(self, limit: int = 50) -> list[Vendor]:
        result = await self._session.execute(
            select(Vendor).where(Vendor.is_active.is_(True)).limit(limit)
        )
        return list(result.scalars().all())


class PriceQuoteRepository:
    """Data access layer for PriceQuote entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: uuid.UUID) -> PriceQuote | None:
        result = await self._session.execute(select(PriceQuote).where(PriceQuote.id == id))
        return result.scalar_one_or_none()

    async def create(self, data: PriceQuoteCreate) -> PriceQuote:
        quote = PriceQuote(**data.model_dump())
        self._session.add(quote)
        await self._session.commit()
        await self._session.refresh(quote)
        return quote

    async def list(self, limit: int = 50) -> list[PriceQuote]:
        result = await self._session.execute(select(PriceQuote).limit(limit))
        return list(result.scalars().all())

    async def list_by_item(self, item_name: str, limit: int = 100) -> list[PriceQuote]:
        result = await self._session.execute(
            select(PriceQuote).where(PriceQuote.item_name == item_name).limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_vendor(self, vendor_id: uuid.UUID, limit: int = 100) -> list[PriceQuote]:
        result = await self._session.execute(
            select(PriceQuote).where(PriceQuote.vendor_id == vendor_id).limit(limit)
        )
        return list(result.scalars().all())

    async def cheapest_for_item(self, item_name: str) -> PriceQuote | None:
        result = await self._session.execute(
            select(PriceQuote)
            .where(PriceQuote.item_name == item_name)
            .order_by(PriceQuote.price.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def average_price_for_item(self, item_name: str) -> float | None:
        result = await self._session.execute(
            select(func.avg(PriceQuote.price)).where(PriceQuote.item_name == item_name)
        )
        avg = result.scalar_one_or_none()
        return float(avg) if avg is not None else None


class ProcurementDocumentRepository:
    """Data access layer for ProcurementDocument entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        doc_type: str,
        doc_number: str,
        doc_date: str,
        division: str,
        vendor_reference: str = "",
        amount: float | None = None,
        currency: str = "IDR",
        items_json: dict | None = None,
        raw_metadata: dict | None = None,
        source_file: str = "",
    ) -> ProcurementDocument:
        doc = ProcurementDocument(
            doc_type=doc_type,
            doc_number=doc_number,
            doc_date=doc_date,
            division=division,
            vendor_reference=vendor_reference,
            amount=amount,
            currency=currency,
            items_json=items_json or {},
            raw_metadata=raw_metadata or {},
            source_file=source_file,
        )
        self._session.add(doc)
        await self._session.commit()
        await self._session.refresh(doc)
        return doc

    async def list_by_type(self, doc_type: str, limit: int = 50) -> list[ProcurementDocument]:
        result = await self._session.execute(
            select(ProcurementDocument)
            .where(ProcurementDocument.doc_type == doc_type)
            .order_by(ProcurementDocument.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_number(self, doc_number: str) -> ProcurementDocument | None:
        result = await self._session.execute(
            select(ProcurementDocument).where(ProcurementDocument.doc_number == doc_number)
        )
        return result.scalar_one_or_none()

    async def list_by_vendor(self, vendor_ref: str, limit: int = 50) -> list[ProcurementDocument]:
        result = await self._session.execute(
            select(ProcurementDocument)
            .where(ProcurementDocument.vendor_reference == vendor_ref)
            .order_by(ProcurementDocument.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
