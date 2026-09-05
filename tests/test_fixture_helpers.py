from pathlib import Path


HEADERS = [
    "\u53d6\u5f97\u5b66\u5e74\u5b66\u671f",
    "\u6821\u533a",
    "\u5e74\u7ea7",
    "\u9662(\u7cfb)/\u90e8",
    "\u4e13\u4e1a",
    "\u73ed\u7ea7",
    "\u5b66\u53f7",
    "\u59d3\u540d",
    "\u627f\u62c5\u5355\u4f4d",
    "\u8bfe\u7a0b\u4ee3\u7801",
    "\u8bfe\u7a0b\u540d\u79f0",
    "\u5b66\u5206",
    "\u4efb\u8bfe\u6559\u5e08",
    "\u8bfe\u7a0b\u7c7b\u522b",
    "\u53d6\u5f97\u65b9\u5f0f",
    "\u6210\u7ee9",
    "\u662f\u5426\u8f85\u4fee\u8bfe\u7a0b",
]


def write_html_fixture(tmp_path: Path) -> Path:
    header_cells = "".join(f"<td>{value}</td>" for value in HEADERS[:-1])
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body><table>
<tr><td>\u5929\u6d25\u5e08\u8303\u5927\u5b66\u5b66\u751f\u6210\u7ee9[\u539f\u59cb]</td></tr>
<tr><td>2025-2026</td></tr>
<tr>{header_cells}<td>\u662f\u5426\u8f85</td></tr>
<tr><td>\u4fee\u8bfe\u7a0b</td></tr>
<tr><td>2025-2026\u5b66\u5e74\u7b2c\u4e00\u5b66\u671f</td><td>\u4e3b\u6821\u533a</td><td>2024</td>
<td>\u8f6f\u4ef6\u5b66\u9662</td><td>\u8f6f\u4ef6\u5de5\u7a0b</td><td>\u8f6f\u4ef62402</td><td>1001</td>
<td>\u6d4b\u8bd5\u5b66\u751f</td><td>\u8f6f\u4ef6\u5b66\u9662</td><td>C-01</td><td>\u6d4b\u8bd5\u8bfe\u7a0b</td>
<td>2</td><td>\u8001\u5e08</td><td>\u4e13\u4e1a\u8bfe/\u5fc5\u4fee\u8bfe</td><td>\u521d\u4fee\u53d6\u5f97</td><td>\u4f18\u79c0</td><td>\u5426</td></tr>
</table></body></html>"""
    path = tmp_path / "fixture.xls"
    path.write_text(html, encoding="utf-8")
    return path
