import pytest
from app.services.qr_service import generate_qr_image_bytes, build_qr_pdf


def test_generate_qr_image_bytes():
    data = generate_qr_image_bytes("https://menu.menuscan.io/test/table/1")
    assert isinstance(data, bytes)
    assert data[:4] == b'\x89PNG'


def test_build_qr_pdf_small():
    entries = [{"table_number": i, "url": f"https://menu.menuscan.io/cafe/table/{i}"} for i in range(1, 5)]
    pdf = build_qr_pdf(venue_name="Тест Кафе", qr_entries=entries)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b'%PDF'


def test_build_qr_pdf_12_tables():
    entries = [{"table_number": i, "url": f"https://menu.menuscan.io/cafe/table/{i}"} for i in range(1, 13)]
    pdf = build_qr_pdf(venue_name="Большое Кафе", qr_entries=entries)
    assert pdf[:4] == b'%PDF'
