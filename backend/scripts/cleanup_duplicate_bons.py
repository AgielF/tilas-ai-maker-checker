#!/usr/bin/env python3
"""
Cleanup script to remove duplicate BON records from procurement_documents table.

Keeps the oldest record (by created_at) for each unique combination of:
- doc_number
- division  
- source_file

Deletes all other duplicates.
"""

import asyncio
import sys
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from timbang.modules.audit.models import AuditFinding
from timbang.shared.core.config import get_settings


async def cleanup_duplicate_bons():
    """Remove duplicate BON records, keeping the oldest one per unique key."""
    settings = get_settings()
    
    engine = create_async_engine(settings.database_url, echo=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    
    async with session_factory() as session:
        # Find all BON records
        stmt = select(AuditFinding).where(
            AuditFinding.evidence_type == "BON"
        ).order_by(AuditFinding.created_at.asc())
        
        result = await session.execute(stmt)
        bons = list(result.scalars().all())
        
        print(f"Total BON records found: {len(bons)}")
        
        # Group by unique key (doc_number, division, source_file)
        groups = {}
        for bon in bons:
            key = (bon.doc_number, bon.division, bon.source_file)
            if key not in groups:
                groups[key] = []
            groups[key].append(bon)
        
        # Find duplicates
        duplicates_to_delete = []
        for key, records in groups.items():
            if len(records) > 1:
                # Keep the first (oldest by created_at), delete the rest
                for record in records[1:]:
                    duplicates_to_delete.append(record.id)
        
        print(f"Duplicate groups found: {len([g for g in groups.values() if len(g) > 1])}")
        print(f"Records to delete: {len(duplicates_to_delete)}")
        
        if duplicates_to_delete:
            # Delete duplicates
            for doc_id in duplicates_to_delete:
                stmt = delete(AuditFinding).where(AuditFinding.id == doc_id)
                await session.execute(stmt)
            
            await session.commit()
            print(f"Successfully deleted {len(duplicates_to_delete)} duplicate records.")
        else:
            print("No duplicates found.")
        
        # Verify remaining count
        remaining_stmt = select(func.count()).select_from(AuditFinding).where(AuditFinding.evidence_type == "BON")
        remaining_result = await session.execute(remaining_stmt)
        print(f"Remaining BON records: {remaining_result.scalar()}")


if __name__ == "__main__":
    asyncio.run(cleanup_duplicate_bons())