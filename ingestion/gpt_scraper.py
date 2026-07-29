"""
Scrapes prompt/response turns from a public ChatGPT share link.

Modern ChatGPT share pages are React Server Components (RSC) applications.
The conversation is reconstructed client-side, so we render the page with a
headless browser and extract the hydrated conversation from the DOM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)
from config import REQUEST_TIMEOUT
from core.log import get_logger


logger = get_logger(__name__)


@dataclass(slots=True)
class ChatTurn:
    """One message in chronological order."""
    role: str
    text: str


# Browser

class _BrowserSession:
    """Small wrapper around Playwright lifecycle."""

    def __enter__(self) -> Page:
        self._playwright = sync_playwright().start()

        self._browser: Browser = self._playwright.chromium.launch(
            headless=True,
        )

        self._context: BrowserContext = self._browser.new_context()

        self._page = self._context.new_page()

        self._page.set_default_timeout(REQUEST_TIMEOUT * 1000)

        return self._page

    def __exit__(self, exc_type, exc, tb):
        self._context.close()
        self._browser.close()
        self._playwright.stop()


# DOM extraction

def _load_page(page: Page, url: str) -> None:
    """Loads the share page and waits until the conversation is rendered."""

    logger.info("Loading ChatGPT share page...")

    page.goto(url, wait_until="domcontentloaded")

    page.wait_for_load_state("networkidle")

    print(page.content())


    try:
        page.wait_for_selector(
            '[data-message-author-role]',
            state="attached",
        )
    except PlaywrightTimeoutError:
        logger.warning(
            "Conversation never appeared. "
            "The share link may be invalid or ChatGPT changed the page."
        )


def _walk_dom(page: Page) -> List[ChatTurn]:
    """
    Reads rendered messages directly from the hydrated DOM.

    ChatGPT annotates every message with:

        data-message-author-role="user"
        data-message-author-role="assistant"

    which is much more stable than reverse-engineering the internal payload.
    """

    messages = page.locator("[data-message-author-role]")

    turns: List[ChatTurn] = []

    for i in range(messages.count()):
        message = messages.nth(i)

        role = message.get_attribute("data-message-author-role")
        text = message.inner_text().strip()

        if not text:
            continue

        turns.append(
            ChatTurn(
                role=role,
                text=text,
            )
        )

    return turns


# Public API

def scrape_chatgpt_share(url: str) -> List[ChatTurn]:
    """
    Downloads a public ChatGPT share page and returns the conversation.

    Returns
    -------
    List[ChatTurn]
        Conversation ordered exactly as shown in ChatGPT.
    """

    with _BrowserSession() as page:
        _load_page(page, url)
        turns = _walk_dom(page)

    if not turns:
        logger.warning(f"Conversation loaded but zero messages were found:\n{url}")

    logger.info("Scraped %d conversation turns.", len(turns))

    return turns


def get_first_user_prompt(url: str) -> str:
    """Returns the very first user prompt."""

    for turn in scrape_chatgpt_share(url):
        if turn.role == "user":
            return turn.text

    raise ValueError("Conversation contains no user messages.")


if __name__ == "__main__":
    url = input("ChatGPT Share URL: ").strip()

    conversation = scrape_chatgpt_share(url)

    for turn in conversation:
        print(f"\n[{turn.role.upper()}]")
        print(turn.text)