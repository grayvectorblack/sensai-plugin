from __future__ import annotations

from dataclasses import dataclass

import anyio
import pytest

from sensai_plugin import release_verifier
from sensai_plugin.release_verifier import ReleaseVerificationError


@dataclass(frozen=True)
class Page:
    tools: list[str]
    nextCursor: str | None


class PageOperation:
    def __init__(self, pages: dict[str | None, Page]) -> None:
        self.pages = pages
        self.cursors: list[str | None] = []

    async def __call__(self, cursor: str | None) -> Page:
        self.cursors.append(cursor)
        return self.pages[cursor]


def test_collect_live_pages_returns_all_pages_in_protocol_order() -> None:
    operation = PageOperation(
        {
            None: Page(tools=["first", "second"], nextCursor="page-2"),
            "page-2": Page(tools=["third"], nextCursor=None),
        }
    )

    result = anyio.run(release_verifier._collect_live_pages, operation, "tools")

    assert result == ["first", "second", "third"]
    assert operation.cursors == [None, "page-2"]


def test_collect_live_pages_rejects_repeated_cursor() -> None:
    operation = PageOperation(
        {
            None: Page(tools=["first"], nextCursor="repeat"),
            "repeat": Page(tools=["second"], nextCursor="repeat"),
        }
    )

    with pytest.raises(ReleaseVerificationError, match="pagination cursor repeated"):
        anyio.run(release_verifier._collect_live_pages, operation, "tools")


def test_collect_live_pages_rejects_page_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release_verifier, "_MAX_LIVE_PAGES", 2)

    class EndlessOperation:
        async def __call__(self, cursor: str | None) -> Page:
            page = 0 if cursor is None else int(cursor)
            return Page(tools=[f"item-{page}"], nextCursor=str(page + 1))

    with pytest.raises(ReleaseVerificationError, match="exceeds page limit"):
        anyio.run(release_verifier._collect_live_pages, EndlessOperation(), "tools")


def test_collect_live_pages_rejects_item_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release_verifier, "_MAX_LIVE_ITEMS", 2)
    operation = PageOperation({None: Page(tools=["first", "second", "third"], nextCursor=None)})

    with pytest.raises(ReleaseVerificationError, match="exceeds item limit"):
        anyio.run(release_verifier._collect_live_pages, operation, "tools")
