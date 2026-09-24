from pathlib import Path

import pymupdf


def extract_pdf(path: Path, image_dir: Path | None = None) -> dict:
    """Extract text blocks and page images from a reference PDF."""
    document = pymupdf.open(path)
    pages = []
    text_blocks = []

    if image_dir is not None:
        image_dir.mkdir(parents=True, exist_ok=True)

    for index, page in enumerate(document):
        page_number = index + 1
        blocks = []
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            lines = []
            for line in block.get("lines", []):
                text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
                if text:
                    lines.append(text)
            if not lines:
                continue
            bbox = tuple(round(value, 2) for value in block["bbox"])
            entry = {
                "page": page_number,
                "bbox": bbox,
                "text": " ".join(lines),
            }
            blocks.append(entry)
            text_blocks.append(entry)

        image_path = None
        if image_dir is not None:
            pixmap = page.get_pixmap(dpi=120)
            image_path = image_dir / f"page-{page_number}.png"
            pixmap.save(image_path)

        pages.append(
            {
                "page": page_number,
                "width": page.rect.width,
                "height": page.rect.height,
                "image": str(image_path) if image_path else None,
                "blocks": blocks,
            }
        )

    return {
        "path": str(path),
        "page_count": document.page_count,
        "pages": pages,
        "text_blocks": text_blocks,
    }
