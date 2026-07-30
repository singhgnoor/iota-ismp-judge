"""
Scrapes prompt/response turns from a public Gemini share link
(e.g. https://share.gemini.google/... or https://gemini.google.com/share/...).

Like ChatGPT, Gemini's share pages are client-rendered — the conversation
only exists in the DOM after JS hydrates it. We render with a headless
browser and read the hydrated custom elements directly.
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

# Gemini renders each turn as one of these custom elements, in DOM order.
_TURN_SELECTOR = "user-query, model-response"
_ROLE_BY_TAG = {
    "user-query": "user",
    "model-response": "assistant",
}


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

# Strips screen-reader-only labels ("You said", avatar icons, etc.) before
# reading text, instead of guessing a specific content class to target.
_CLEAN_TEXT_JS = """
el => {
    const clone = el.cloneNode(true);
    clone.querySelectorAll(
        '[class*="visually-hidden"], [aria-hidden="true"], mat-icon, [class*="avatar"]'
    ).forEach(node => node.remove());
    return clone.innerText.trim();
}
"""


def _load_page(page: Page, url: str) -> None:
    """Loads the share page and waits until the conversation is rendered."""

    logger.info(f"Loading Gemini chat {url}...")

    page.goto(url, wait_until="domcontentloaded")

    page.wait_for_load_state("networkidle")

    try:
        page.wait_for_selector(_TURN_SELECTOR, state="attached")
    except PlaywrightTimeoutError:
        logger.warning(
            "Conversation never appeared. "
            "The share link may be invalid or Gemini changed the page."
        )
        return

    _scroll_until_fully_hydrated(page)


def _scroll_until_fully_hydrated(page: Page, max_rounds: int = 30) -> None:
    """
    Gemini virtualizes long conversations: turns outside the viewport
    aren't attached to the DOM until scrolled into view, even though
    `wait_for_selector` already fired on turn #1.

    Blindly scrolling the window (mouse wheel / End key) doesn't help if
    the real scroll container is some inner <div>, which is the norm for
    Angular Material apps. Instead, scroll the *actual last rendered turn*
    into view each round — Playwright resolves whichever ancestor is
    scrollable for us — until the turn count stops growing.
    """

    stable_rounds = 0
    last_count = -1

    for _ in range(max_rounds):
        turns = page.locator(_TURN_SELECTOR)
        count = turns.count()

        if count > 0:
            try:
                turns.nth(count - 1).scroll_into_view_if_needed(timeout=2000)
            except PlaywrightTimeoutError:
                pass

        page.wait_for_timeout(500)

        new_count = page.locator(_TURN_SELECTOR).count()

        if new_count == last_count:
            stable_rounds += 1
            if stable_rounds >= 3:
                break
        else:
            stable_rounds = 0

        last_count = new_count

    logger.debug(f"Hydration settled at {last_count} turns.")


def _walk_dom(page: Page) -> List[ChatTurn]:
    """
    Reads rendered messages directly from the hydrated DOM.

    Gemini wraps every turn in one of two custom elements:

        <user-query>...</user-query>
        <model-response>...</model-response>

    which is more stable than reverse-engineering internal class names.
    """

    messages = page.locator(_TURN_SELECTOR)

    turns: List[ChatTurn] = []

    for i in range(messages.count()):
        message = messages.nth(i)

        tag = message.evaluate("el => el.tagName.toLowerCase()")
        role = _ROLE_BY_TAG.get(tag, tag)
        text = message.evaluate(_CLEAN_TEXT_JS).strip()

        # Belt-and-suspenders: strip a leading a11y label if one slipped through.
        for prefix in ("You said\n", "You\n"):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        if not text:
            continue

        turns.append(
            ChatTurn(
                role=role,
                text=text,
            )
        )

    logger.debug(f"Found {len(turns)} conversation turns.\n Chat turns: {turns}")

    return turns


# Public API

def scrape_gemini_share(url: str) -> List[ChatTurn]:
    """
    Downloads a public Gemini share page and returns the conversation.

    Returns
    -------
    List[ChatTurn]
        Conversation ordered exactly as shown in Gemini.
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

    for turn in scrape_gemini_share(url):
        if turn.role == "user":
            return turn.text

    raise ValueError("Conversation contains no user messages.")


if __name__ == "__main__":
    url = input("Gemini Share URL: ").strip()

    conversation = scrape_gemini_share(url)

    for turn in conversation:
        print(f"\n[{turn.role.upper()}]")
        print(turn.text)