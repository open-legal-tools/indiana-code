import zipfile

from indiana_law import companion, web
from indiana_law.mcp_server import build_server


def test_landing_and_terms_copy():
    landing = web.landing_html()
    terms = web.terms_html()
    assert "Unofficial" in landing and "https://mcp.openindianalaw.org/mcp" in landing
    assert "406" in landing and "Not Acceptable" in landing
    assert "background: #f4efe6" in landing
    assert "1852" in landing and "1807" in landing
    assert "not a complete set" in landing
    assert "1,218" not in landing
    assert "not legal advice" in terms.lower()
    assert "2018" in terms
    assert "court rules" in terms.lower()


def test_custom_http_routes_registered(mini):
    mcp = build_server(conn=mini)
    paths = {route.path for route in mcp._custom_starlette_routes}
    assert paths == {"/", "/terms", "/health"}


def test_extract_archive_titles(tmp_path):
    zpath = tmp_path / "2016-Indiana-Code.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("2016/Title_1.pdf", b"%PDF-1.4 archive")
        zf.writestr("__MACOSX/._Title_1.pdf", b"skip")
    dest = tmp_path / "out"
    written = companion.extract_archive_titles_from_zip(str(zpath), str(dest))
    assert written == [str(dest / "Title_1.pdf")]
    assert (dest / "Title_1.pdf").read_bytes() == b"%PDF-1.4 archive"
