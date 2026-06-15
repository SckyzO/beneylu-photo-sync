# tests/test_exif.py
from datetime import datetime
from io import BytesIO

from PIL import Image

from ent_exporter.exif import capture_date


def _jpeg_with_date(value: str) -> bytes:
    img = Image.new("RGB", (2, 2))
    exif = Image.Exif()
    exif.get_ifd(0x8769)[36867] = value  # DateTimeOriginal in the Exif sub-IFD
    buf = BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def _jpeg_without_exif() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (2, 2)).save(buf, format="JPEG")
    return buf.getvalue()


def test_capture_date_reads_datetimeoriginal():
    data = _jpeg_with_date("2026:03:04 11:22:33")
    assert capture_date(data) == datetime(2026, 3, 4, 11, 22, 33)


def test_capture_date_returns_none_without_exif():
    assert capture_date(_jpeg_without_exif()) is None


def test_capture_date_returns_none_on_garbage():
    assert capture_date(b"not an image at all") is None


def test_capture_date_returns_none_on_unparseable_value():
    data = _jpeg_with_date("garbage-date")
    assert capture_date(data) is None
