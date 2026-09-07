import os

import pytest

from src.vault_checks import DOCUMENT_MAP, note_json
from src.vault_commit import VaultClient

pytestmark = pytest.mark.vault
PROBE = "_probe-textbook-pipeline/nested/"


@pytest.fixture
def client():
    if not (os.environ.get("OBSIDIAN_HOST") and os.environ.get("OBSIDIAN_API_KEY")):
        pytest.skip("OBSIDIAN_HOST / OBSIDIAN_API_KEY not set")
    c = VaultClient()
    c.ping()
    return c


def test_round_trip_note_png_and_obsidian_parse(client):
    note = (
        "---\nbook: probe\nsection: '5.10'\ncertified_at: null\n---\n# probe\n\n$$x^2$$\n\n"
        "![[probe.png]]\n\n![[nope.png]] and [[nope-note]]\n"
    )
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c636060f8ff1f0002870180eb47ba920000000049454e44ae426082"
    )
    try:
        assert client.put(PROBE + "probe.md", note.encode(), "text/markdown") == 204
        assert client.put(PROBE + "probe.png", png, "image/png") == 204
        assert client.get(PROBE + "probe.md").content == note.encode()
        assert client.get(PROBE + "probe.png").content == png
        data = note_json(client, PROBE + "probe.md")
        assert data["frontmatter"] == {"book": "probe", "section": "5.10", "certified_at": None}
        assert data["content"] == note
        # Obsidian lists only the targets it resolved: the missing embed and link are absent
        assert [p.rsplit("/", 1)[-1] for p in data["links"]] == ["probe.png"]
        dm = client.get(PROBE + "probe.md", accept=DOCUMENT_MAP).json()
        assert dm["headings"] == ["probe"]
    finally:
        assert client.delete(PROBE + "probe.md") == 204
        assert client.delete(PROBE + "probe.png") == 204
    assert client.get("_probe-textbook-pipeline/").status_code == 404  # emptied folders vanish
