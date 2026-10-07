"""Tests for Bon Permintaan parser and endpoint."""

from __future__ import annotations

import io
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from timbang.shared.parsers.excel import parse_excel_document as parse_bon_excel
from timbang.modules.procurement.models import ProcurementDocument
from timbang.shared.schemas.document import ExtractedItem as BonItem, ParsedDocument as ParsedBon


async def _read_sample_bon() -> bytes:
    with open("sample-docs/13-Pengajuan-Rabu-30-Sept-2026.xlsx", "rb") as f:
        return f.read()


def _read_sample_bon_sync() -> bytes:
    with open("sample-docs/13-Pengajuan-Rabu-30-Sept-2026.xlsx", "rb") as f:
        return f.read()


class TestBonParser:
    """Tests for the bon_parser module."""

    def test_parse_bon_single_section(self):
        """Test parsing a single BON section."""
        content = _read_sample_bon_sync()
        bons = parse_bon_excel(content)

        # Should find multiple BONs across sheets
        assert len(bons) >= 5

        # Check first BON from first sheet
        bon1 = next((b for b in bons if b.bon_number == "1"), None)
        assert bon1 is not None
        assert bon1.date == "30 SEPTEMBER 2026"
        assert bon1.division == "PPIC"
        assert bon1.sheet_name == "Kain dan Aksesoris"
        assert len(bon1.items) >= 3

        # Check first item
        item1 = bon1.items[0]
        assert isinstance(item1, BonItem)
        assert item1.no == "1"
        assert "WUNDER" in item1.nama_barang
        assert item1.qty is not None
        assert item1.satuan == "YARD"

    def test_parse_bon_multi_section(self):
        """Test parsing multiple BON sections from the actual sample file."""
        content = _read_sample_bon_sync()
        bons = parse_bon_excel(content)

        # Should find BONs: 1 from sheet 1, and 2,3,4,5,6 from sheet 2
        bon_numbers = [b.bon_number for b in bons]
        assert "1" in bon_numbers
        assert "2" in bon_numbers
        assert "3" in bon_numbers
        assert "4" in bon_numbers
        assert "5" in bon_numbers
        assert "6" in bon_numbers

        # Check BON 4 has multiple items (sample has 6 items for thread)
        bon4 = next((b for b in bons if b.bon_number == "4"), None)
        assert bon4 is not None
        assert len(bon4.items) == 6
        assert bon4.division == "SAMPLE"

    def test_handle_typo_supplier(self):
        """Test that 'SUPLIER' typo in header is handled."""
        content = _read_sample_bon_sync()
        bons = parse_bon_excel(content)

        # BON 2 has "SUPLIER" in header
        bon2 = next((b for b in bons if b.bon_number == "2"), None)
        assert bon2 is not None

    def test_handle_formula_literal(self):
        """Test that formula literals like '=C11-E11' are handled as None."""
        content = _read_sample_bon_sync()
        bons = parse_bon_excel(content)

        # Check that formula cells don't crash the parser
        for bon in bons:
            for item in bon.items:
                if item.qty is not None:
                    assert isinstance(item.qty, float)


class TestBonEndpoint:
    """Tests for the /api/v1/procurement/bons/parse endpoint."""

    @pytest.mark.asyncio
    async def test_endpoint_bon_parse(self, client: AsyncClient):
        """Test POST /api/v1/procurement/bons/parse with Excel file."""
        content = await _read_sample_bon()
        files = {"file": ("test_bon.xlsx", io.BytesIO(content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

        response = await client.post("/api/v1/procurement/bons/parse", files=files)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 5

        # Verify structure of first BON
        bon1 = next((b for b in data if b["bon_number"] == "1"), None)
        assert bon1 is not None
        assert bon1["date"] == "30 SEPTEMBER 2026"
        assert bon1["division"] == "PPIC"
        assert len(bon1["items"]) >= 3
        assert "no" in bon1["items"][0]
        assert "nama_barang" in bon1["items"][0]
        assert "qty" in bon1["items"][0]

    @pytest.mark.asyncio
    async def test_endpoint_bon_parse_invalid_extension(self, client: AsyncClient):
        """Test that non-Excel files are rejected."""
        content = b"not an excel file"
        files = {"file": ("test.txt", io.BytesIO(content), "text/plain")}

        response = await client.post("/api/v1/procurement/bons/parse", files=files)

        assert response.status_code == 400
        assert "tidak didukung" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_endpoint_bon_parse_oversized(self, client: AsyncClient):
        """Test that oversized files are rejected."""
        # Create a large file (> 10 MB)
        large_content = b"x" * (11 * 1024 * 1024)
        files = {"file": ("large.xlsx", io.BytesIO(large_content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

        response = await client.post("/api/v1/procurement/bons/parse", files=files)

        assert response.status_code == 400
        assert "terlalu besar" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_endpoint_bon_parse_empty_file(self, client: AsyncClient):
        """Test that empty files are rejected."""
        files = {"file": ("empty.xlsx", io.BytesIO(b""), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

        response = await client.post("/api/v1/procurement/bons/parse", files=files)

        assert response.status_code == 400
        assert "kosong" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_parse_bon_saves_to_database(self, client: AsyncClient, session):
        """Test that parsing BON auto-saves to procurement_documents table."""
        content = await _read_sample_bon()
        files = {"file": ("test_bon.xlsx", io.BytesIO(content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

        response = await client.post("/api/v1/procurement/bons/parse", files=files)

        assert response.status_code == 200

        # Verify records were saved to database
        result = await session.execute(select(ProcurementDocument))
        docs = list(result.scalars().all())

        # Should have 6 BONs from the sample file
        assert len(docs) == 6

        # Verify each document has correct fields
        for doc in docs:
            assert doc.doc_type == "BON"
            assert doc.doc_number in {"1", "2", "3", "4", "5", "6"}
            assert doc.division in {"PPIC", "PURCHASING", "PACKING", "SAMPLE", "OFFICE"}
            assert doc.doc_date == "30 SEPTEMBER 2026"
            assert doc.currency == "IDR"
            assert doc.amount is None
            assert doc.vendor_reference == ""
            assert doc.source_file == "test_bon.xlsx"
            assert "items" in doc.items_json
            assert len(doc.items_json["items"]) > 0

        # Verify specific BONs
        bon1 = next((d for d in docs if d.doc_number == "1"), None)
        assert bon1 is not None
        assert bon1.division == "PPIC"

        bon4 = next((d for d in docs if d.doc_number == "4"), None)
        assert bon4 is not None
        assert bon4.division == "SAMPLE"
        assert len(bon4.items_json["items"]) == 6

    @pytest.mark.asyncio
    async def test_list_documents_after_upload(self, client: AsyncClient, session):
        """Test that listing documents works after BON upload."""
        content = await _read_sample_bon()
        files = {"file": ("test_bon.xlsx", io.BytesIO(content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

        # Upload first
        response = await client.post("/api/v1/procurement/bons/parse", files=files)
        assert response.status_code == 200

        # List all documents
        response = await client.get("/api/v1/procurement/documents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 6

        # Verify list item structure
        doc1 = data[0]
        assert "id" in doc1
        assert doc1["doc_type"] == "BON"
        assert "doc_number" in doc1
        assert "doc_date" in doc1
        assert "division" in doc1
        assert "item_count" in doc1
        assert "source_file" in doc1
        assert "created_at" in doc1

    @pytest.mark.asyncio
    async def test_list_documents_filter_by_division(self, client: AsyncClient, session):
        """Test filtering documents by division."""
        content = await _read_sample_bon()
        files = {"file": ("test_bon.xlsx", io.BytesIO(content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

        await client.post("/api/v1/procurement/bons/parse", files=files)

        # Filter by SAMPLE division (should have BON 4 and 5)
        response = await client.get("/api/v1/procurement/documents", params={"division": "SAMPLE"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(d["division"] == "SAMPLE" for d in data)
        bon_numbers = {d["doc_number"] for d in data}
        assert bon_numbers == {"4", "5"}

        # Filter by PPIC division (should have BON 1)
        response = await client.get("/api/v1/procurement/documents", params={"division": "PPIC"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["division"] == "PPIC"
        assert data[0]["doc_number"] == "1"

    @pytest.mark.asyncio
    async def test_get_document_detail(self, client: AsyncClient, session):
        """Test getting document detail by ID."""
        content = await _read_sample_bon()
        files = {"file": ("test_bon.xlsx", io.BytesIO(content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

        await client.post("/api/v1/procurement/bons/parse", files=files)

        # Get first document ID
        response = await client.get("/api/v1/procurement/documents")
        assert response.status_code == 200
        docs = response.json()
        doc_id = docs[0]["id"]

        # Get detail
        response = await client.get(f"/api/v1/procurement/documents/{doc_id}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["id"] == doc_id
        assert detail["doc_type"] == "BON"
        assert "items" in detail
        assert isinstance(detail["items"], list)
        assert len(detail["items"]) > 0
        assert "raw_metadata" in detail
        assert "created_at" in detail

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, client: AsyncClient):
        """Test getting non-existent document returns 404."""
        import uuid as uuid_module
        random_id = uuid_module.uuid4()
        response = await client.get(f"/api/v1/procurement/documents/{random_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()