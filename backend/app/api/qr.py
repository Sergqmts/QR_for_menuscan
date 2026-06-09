import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.table import Table
from app.models.qr_batch import QRBatch
from app.services.venue_service import get_venue_or_404

router = APIRouter(prefix="/venues", tags=["qr"])


@router.post("/{venue_id}/qr/generate", status_code=202)
async def generate_qr(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    venue = await get_venue_or_404(db, venue_id, user.id)
    tables_result = await db.execute(
        select(Table).where(Table.venue_id == venue_id, Table.is_active == True).order_by(Table.number)
    )
    tables = tables_result.scalars().all()

    batch = QRBatch(id=uuid.uuid4(), venue_id=venue_id, table_count=len(tables))
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    batch_id = batch.id
    venue_name = venue.name
    venue_slug = venue.slug
    table_data = [(t.id, t.number) for t in tables]

    from app.core.database import AsyncSessionLocal

    async def _generate():
        from app.services.qr_service import build_qr_pdf, upload_pdf_to_s3
        qr_entries = [
            {"table_number": num, "url": f"https://menu.menuscan.io/{venue_slug}/table/{num}"}
            for _, num in table_data
        ]
        pdf_bytes = build_qr_pdf(venue_name=venue_name, qr_entries=qr_entries)
        key = f"qr/{venue_id}/{batch_id}.pdf"
        pdf_url = upload_pdf_to_s3(pdf_bytes, key)

        async with AsyncSessionLocal() as bg_db:
            result = await bg_db.execute(select(QRBatch).where(QRBatch.id == batch_id))
            b = result.scalar_one()
            b.pdf_url = pdf_url
            for tid, tnum in table_data:
                tr = await bg_db.execute(select(Table).where(Table.id == tid))
                t = tr.scalar_one()
                t.qr_code_url = f"https://menu.menuscan.io/{venue_slug}/table/{tnum}"
            await bg_db.commit()

    asyncio.create_task(_generate())
    return {"batch_id": batch_id, "status": "generating"}


@router.get("/{venue_id}/qr/download")
async def download_qr(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_venue_or_404(db, venue_id, user.id)
    result = await db.execute(
        select(QRBatch)
        .where(QRBatch.venue_id == venue_id, QRBatch.pdf_url.isnot(None))
        .order_by(QRBatch.generated_at.desc())
        .limit(1)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="No QR PDF generated yet")
    return RedirectResponse(url=batch.pdf_url)
