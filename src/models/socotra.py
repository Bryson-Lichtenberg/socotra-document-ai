from typing import Literal

from pydantic import BaseModel, Field


class SocotraField(BaseModel):
    path: str
    display_name: str | None = None
    type: str
    base_type: str
    cardinality: Literal["one", "optional", "one_or_more", "zero_or_more"]
    scope: list[str] = Field(default_factory=list)
    entity: str
    element_type: str | None = None
    options: list[str] | None = None
    description: str | None = None


class DocumentConfig(BaseModel):
    format: str = "pdf"
    rendering: str = "dynamic"
    scope: str = "term"
    selectionTimeBasis: str = "termStartTime"
    trigger: str = "issued"
    customFonts: list[str] = Field(default_factory=list)
    templateSnippets: list[str] = Field(default_factory=list)
    displayName: str | None = "Homeowners Declarations"
    pageSize: str = "letter"
    portrait: bool = True
    margin: dict[str, int] = Field(
        default_factory=lambda: {"top": 10, "bottom": 10, "left": 10, "right": 10}
    )


class ResourceManifest(BaseModel):
    resourceType: str = "documentTemplate"
    name: str
    staticName: str
    templateFormat: str = "liquid"
    jurisdictions: list[str]
