from pathlib import Path

import pymupdf


def html_to_pdf(html: str, destination: Path) -> None:
    """Render HTML to a letter-size PDF with PyMuPDF Story.

    This is a local layout loop, not proof of Socotra renderer parity.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    story = pymupdf.Story(html)
    writer = pymupdf.DocumentWriter(str(destination))
    mediabox = pymupdf.paper_rect("letter")
    where = mediabox + (28, 28, -28, -28)
    more = 1
    while more:
        device = writer.begin_page(mediabox)
        more, _filled = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
