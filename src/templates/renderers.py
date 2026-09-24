"""Interchangeable HTML-to-PDF backends.

Every backend is a local approximation. Final compatibility belongs to Socotra's ad-hoc render endpoint,
which SocotraRenderAdapter documents but does not call: this prototype has no tenant credentials.
"""

from pathlib import Path
from typing import Protocol

from templates.html_pdf import html_to_pdf


class Renderer(Protocol):
    name: str

    def render(self, html: str, destination: Path) -> Path: ...


class PyMuPDFRenderer:
    """Default. No browser dependency; the golden layout was tuned against it."""

    name = "pymupdf"

    def render(self, html: str, destination: Path) -> Path:
        html_to_pdf(html, destination)
        return destination


class PlaywrightRenderer:
    """Headless Chromium, the renderer the plan recommends. Closer to a browser engine than PyMuPDF Story."""

    name = "playwright"

    def __init__(self, margin_mm: int = 10):
        self.margin = f"{margin_mm}mm"

    def render(self, html: str, destination: Path) -> Path:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright is not installed. Run: pip install playwright && playwright install chromium") from exc
        destination.parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.pdf(
                path=str(destination),
                format="Letter",
                print_background=True,
                margin={side: self.margin for side in ("top", "bottom", "left", "right")},
            )
            browser.close()
        return destination


class SocotraRenderAdapter:
    """Placeholder for tenant rendering. Not implemented: no sandbox credentials.

    With a sandbox tenant this would:
    1. POST /resource/{tenantLocator}/templates/liquid with name, staticName, jurisdiction[] to upload the template.
    2. POST /document/{tenantLocator}/documents/render with referenceType, referenceLocator, and optional
       productName, templateFormat, documentConfig, staticName, templateName.
    Sources: https://docs.socotra.com/api/resources/document-resources and https://docs.socotra.com/api/documents
    """

    name = "socotra"

    def __init__(self, tenant_locator: str | None = None, reference_locator: str | None = None):
        self.tenant_locator = tenant_locator
        self.reference_locator = reference_locator

    def render(self, html: str, destination: Path) -> Path:
        raise NotImplementedError(
            "SocotraRenderAdapter needs a sandbox tenant, credentials, and a quote or policy locator. "
            "The rest of the pipeline does not change when it is implemented."
        )


RENDERERS = {"pymupdf": PyMuPDFRenderer, "playwright": PlaywrightRenderer, "socotra": SocotraRenderAdapter}


def get_renderer(name: str = "pymupdf") -> Renderer:
    if name not in RENDERERS:
        raise ValueError(f"Unknown renderer {name}. Choose from {sorted(RENDERERS)}.")
    return RENDERERS[name]()
