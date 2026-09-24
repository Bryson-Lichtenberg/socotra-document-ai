import base64
import json
import os
from pathlib import Path
from typing import Protocol

from openai import OpenAI

from ai.prompts import FORM_ANALYZER_SYSTEM
from models.document import DocumentModel


class LLMProvider(Protocol):
    """What the pipeline needs from a model vendor. Core logic depends on this, not on OpenAI."""

    def analyze_form(self, *, text_blocks: list[dict], page_image: Path, review_notes: list[str] | None = None) -> DocumentModel: ...
    def map_fields(self, *, requirements: list, catalog: list, candidates: dict) -> list: ...
    def extract_rules(self, *, source_text: str, field_catalog: list, document_catalog: list) -> object: ...
    def compare_semantics(self, *, source: str, candidate: str, accepted_differences: list[str]) -> object: ...
    def inspect_visuals(self, *, pdf_path: Path, source_page: Path, candidate_pages: list[Path]) -> object: ...


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def image_part(path: Path) -> dict:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}", "detail": "high"}}


class OpenAIJson:
    """Minimal JSON-mode chat wrapper. The model name comes from LLM_MODEL."""

    def __init__(self, model: str | None = None):
        load_env(Path(__file__).resolve().parents[2] / ".env")
        self.model = model or os.environ.get("LLM_MODEL") or "gpt-4.1"
        self.client = OpenAI()

    def complete(self, system: str, content: list[dict]) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return json.loads(response.choices[0].message.content)


class OpenAIFormAnalyzer:
    def __init__(self, model: str | None = None):
        load_env(Path(__file__).resolve().parents[2] / ".env")
        self.model = model or os.environ.get("LLM_MODEL") or "gpt-4.1"
        self.client = OpenAI()

    def analyze_form(
        self,
        *,
        text_blocks: list[dict],
        page_image: Path,
        review_notes: list[str] | None = None,
    ) -> DocumentModel:
        image_b64 = base64.b64encode(page_image.read_bytes()).decode("ascii")
        user_text = (
            "Write a reusable template specification for this declarations form. "
            "Text blocks are provided so you can quote them. Use the image for layout.\n\n"
            f"TEXT_BLOCKS:\n{json.dumps(text_blocks, indent=2)}"
        )
        if review_notes:
            user_text += "\n\nThe previous specification failed these checks. Fix them:\n- " + "\n- ".join(review_notes)
        last_error = None
        for _attempt in range(2):
            messages = [
                {"role": "system", "content": FORM_ANALYZER_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                    ],
                },
            ]
            if last_error:
                messages.append(
                    {
                        "role": "user",
                        "content": f"The previous JSON failed validation: {last_error}. Return corrected JSON only.",
                    }
                )
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
            )
            payload = _coerce_payload(json.loads(response.choices[0].message.content))
            try:
                return DocumentModel.model_validate(payload)
            except Exception as exc:
                last_error = str(exc)
        raise ValueError(last_error)


class OpenAIProvider:
    """LLMProvider backed by OpenAI chat completions in JSON mode. Each method delegates to the module that owns the task."""

    def __init__(self, model: str | None = None):
        self.json = OpenAIJson(model)
        self.forms = OpenAIFormAnalyzer(model)

    def analyze_form(self, *, text_blocks, page_image, review_notes=None):
        return self.forms.analyze_form(text_blocks=text_blocks, page_image=page_image, review_notes=review_notes)

    def map_fields(self, *, requirements, catalog, candidates):
        from mapping.ai_mapper import adjudicate
        return adjudicate(requirements, catalog, candidates, self.json)

    def extract_rules(self, *, source_text, field_catalog, document_catalog):
        from rules.extractor import extract_rules
        return extract_rules(source_text, field_catalog, document_catalog, self.json)

    def compare_semantics(self, *, source, candidate, accepted_differences):
        from validation.semantic import review_semantics
        return review_semantics(reference_text=source, candidate_text=candidate, accepted_differences=accepted_differences, client=self.json)

    def inspect_visuals(self, *, pdf_path, source_page, candidate_pages):
        from validation.visual import review_visuals
        return review_visuals(pdf_path=pdf_path, reference_image=source_page, candidate_images=candidate_pages, client=self.json)


def _coerce_payload(payload: dict) -> dict:
    if "nodes" not in payload and "document_model" in payload:
        payload = payload["document_model"]
    pages = payload.get("pages")
    if isinstance(pages, list):
        nodes = []
        for page in pages:
            if isinstance(page, dict):
                nodes.extend(page.get("nodes") or [])
        payload = {**payload, "pages": len(pages), "nodes": payload.get("nodes") or nodes}
    return payload
