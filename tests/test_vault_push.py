import json
import re

import pytest

from src.review import Chapter
from src.vault_checks import DOCUMENT_MAP, NOTE_JSON, _split_frontmatter, check_parsed
from src.vault_commit import CommitError, push_chapter, render_chapter, staging_dir
from tests.helpers import make_work_dir
from tests.test_vault_commit import CHART, FLAGS, PARA, SECTIONS, TITLE, TITLE2


class FakeClient:
    """In-memory vault: PUT/GET bytes, plus Obsidian's note+json and document-map views."""

    base = "http://fake:27123"

    def __init__(self, corrupt=()):
        self.store: dict[str, bytes] = {}
        self.corrupt = set(corrupt)

    def ping(self):
        return {"authenticated": True}

    def put(self, path, data, content_type):
        self.store[path] = data + (b"x" if path.split("/")[-1] in self.corrupt else b"")
        return 204

    def _resolved(self, text):
        targets = set(re.findall(r"\[\[([^\]|#]+)", text))
        return sorted(
            k for k in self.store if k.rsplit("/", 1)[-1] in targets | {t + ".md" for t in targets}
        )

    def get(self, path, accept=None):
        data = self.store.get(path)

        class R:
            status_code = 200 if data is not None else 404
            content = data or b""
            text = (data or b"").decode(errors="replace")

        r = R()
        if data is not None and accept == NOTE_JSON:
            fm, _body = _split_frontmatter(r.text)
            r.json = lambda: {
                "frontmatter": fm or {},
                "content": r.text,
                "links": self._resolved(r.text),
                "tags": [],
            }
        elif data is not None and accept == DOCUMENT_MAP:
            # Obsidian lists unique `::`-joined heading paths (two sibling headings with the same
            # text collapse to one entry — bma ch05 note 03, gate 4)
            paths, stack = [], []
            for m in re.finditer(r"(?m)^(#{1,6}) (.+)$", r.text):
                level, title = len(m.group(1)), m.group(2).strip()
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, title))
                path = "::".join(x for _lvl, x in stack)
                if path not in paths:
                    paths.append(path)
            r.json = lambda: {"headings": paths, "blocks": []}
        return r


@pytest.fixture
def certified(tmp_path, monkeypatch):
    import src.vault_commit

    monkeypatch.setattr(src.vault_commit, "VAULT", tmp_path / "vault")
    make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[[TITLE, PARA, CHART], [TITLE2, PARA]],
        flagged=FLAGS,
        sections=SECTIONS,
        pdf_lines=["body one", "body one"],
    )
    ch = Chapter("bma", 5)
    ch.review["blocks"][0]["verdict"] = "verified"
    ch.save()
    return render_chapter(Chapter("bma", 5), certified=True)


def test_push_refuses_uncertified(tmp_path, monkeypatch):
    import src.vault_commit

    monkeypatch.setattr(src.vault_commit, "VAULT", tmp_path / "vault")
    make_work_dir(
        tmp_path, monkeypatch, pages=[[TITLE, PARA]], sections=SECTIONS[:1], pdf_lines=["body one"]
    )
    render_chapter(Chapter("bma", 5), certified=False)
    with pytest.raises(CommitError, match="not certified"):
        push_chapter(Chapter("bma", 5), "raw/textbooks/", client=FakeClient())


def test_push_puts_every_file_under_root_and_records_verification(certified):
    client = FakeClient()
    assert push_chapter(Chapter("bma", 5), "raw/textbooks/", client=client) == 0
    assert all(k.startswith("raw/textbooks/bma/ch05/") for k in client.store)
    assert "raw/textbooks/bma/ch05/assets/bma-ch05-p000-b002.jpg" in client.store
    m = json.loads((certified / "manifest.json").read_text())
    assert m["push"]["root"] == "raw/textbooks/" and m["push"]["host"] == "http://fake:27123"
    assert all(v == {"status": 204, "verified": True} for v in m["push"]["files"].values())


def test_push_section_only_and_failed_readback(certified):
    client = FakeClient(corrupt={"bma-ch05-01-first.md"})
    failed = push_chapter(Chapter("bma", 5), "", section="1", client=client)
    assert failed == 1
    assert set(client.store) == {
        "bma/ch05/bma-ch05-01-first.md",
        "bma/ch05/assets/bma-ch05-p000-b002.jpg",
    }
    m = json.loads((certified / "manifest.json").read_text())
    assert m["push"]["files"]["bma-ch05-01-first.md"]["verified"] is False


def test_check_parsed_is_clean_after_a_full_push(certified):
    client = FakeClient()
    ch = Chapter("bma", 5)
    assert push_chapter(ch, "raw/textbooks/", client=client) == 0
    assert check_parsed(staging_dir(ch), ch, client, "raw/textbooks/") == []


def test_check_parsed_reports_unresolved_embeds_and_content_drift(certified):
    client = FakeClient()
    ch = Chapter("bma", 5)
    push_chapter(ch, "raw/textbooks/", client=client)
    del client.store["raw/textbooks/bma/ch05/assets/bma-ch05-p000-b002.jpg"]
    hub = "raw/textbooks/bma/ch05/bma-ch05-00-net-present-value-and-other-investment-criteria.md"
    client.store[hub] += b"\n## extra heading\n"
    msgs = [p.msg for p in check_parsed(staging_dir(ch), ch, client, "raw/textbooks/")]
    assert any("unresolved" in m and "bma-ch05-p000-b002.jpg" in m for m in msgs), msgs
    assert any("content" in m for m in msgs) and any("headings" in m for m in msgs), msgs


def test_check_parsed_needs_a_pushed_chapter(certified):
    ch = Chapter("bma", 5)
    problems = check_parsed(staging_dir(ch), ch, FakeClient(), "raw/textbooks/")
    assert len(problems) == 1 and "not pushed" in problems[0].msg


def test_check_parsed_accepts_duplicate_sibling_headings(certified):
    client = FakeClient()
    ch = Chapter("bma", 5)
    push_chapter(ch, "raw/textbooks/", client=client)
    hub = "raw/textbooks/bma/ch05/bma-ch05-00-net-present-value-and-other-investment-criteria.md"
    tree = staging_dir(ch)
    text = (
        client.store[hub].decode()
        + "\n### BEYOND THE PAGE\n\ntext\n\n### BEYOND THE PAGE\n\nmore\n"
    )
    client.store[hub] = text.encode()
    (tree / hub.rsplit("/", 1)[-1]).write_text(text)  # same text in the staging tree
    msgs = [p.msg for p in check_parsed(tree, ch, client, "raw/textbooks/")]
    assert not any("heading" in m for m in msgs), msgs
