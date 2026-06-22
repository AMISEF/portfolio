"""
تولید فایل اکسل (.xlsx) با کتابخانهٔ استاندارد (zipfile) — بدون وابستگی بیرونی.

همهٔ سلول‌ها به‌صورت «رشتهٔ درون‌خطی» (inlineStr) نوشته می‌شوند تا اکسل آن‌ها را
متن در نظر بگیرد؛ بدین‌ترتیب صفرِ ابتدایی شماره تماس (مثل 09123456789) حذف
نمی‌شود و ارقام دست‌نخورده می‌مانند.
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone


def _esc(v: object) -> str:
    s = "" if v is None else str(v)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _col_ref(idx: int) -> str:
    """0 → A، 1 → B، … 26 → AA."""
    s = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def _sheet_xml(headers: list[str], rows: list[list[object]]) -> str:
    out = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    all_rows = [headers] + rows
    for r_i, row in enumerate(all_rows, start=1):
        out.append(f'<row r="{r_i}">')
        for c_i, val in enumerate(row):
            ref = f"{_col_ref(c_i)}{r_i}"
            out.append(
                f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">'
                f"{_esc(val)}</t></is></c>"
            )
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def build_xlsx(headers: list[str], rows: list[list[object]], sheet_name: str = "Users") -> bytes:
    """ساخت بایت‌های یک فایل xlsx معتبر با یک شیت."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{_esc(sheet_name)[:31] or "Sheet1"}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/worksheets/sheet1.xml", _sheet_xml(headers, rows))
    _ = now  # برای آینده (متادیتا)
    return buf.getvalue()
