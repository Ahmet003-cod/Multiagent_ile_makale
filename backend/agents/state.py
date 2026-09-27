"""
Multi-Agent Workflow — Shared State Definition (Enhanced)

Ajanlar arasi paylasilan durum yapisi.
Gorsel katalogu, derin arastirma verileri, bolum taslaklari ve hakem kararlarini barindirir.
"""

from typing import TypedDict, List, Dict, Optional


class AgentState(TypedDict):
    """Ajanlar arasi paylasilan zenginlestirilmis durum."""

    # Arastirma konusu
    task: str

    # Toplanan arastirma verileri ve kaynak katalogu
    research_data: str

    # Internetten toplanan gorseller ve diyagramlar
    images: List[Dict[str, str]]

    # Uretilen kapsamli monografi / makale taslagi
    draft: str

    # Hakem (Reviewer) elestiri ve degerlendirmesi
    review: str

    # Hakem karari: "APPROVE" veya "REVISE"
    review_status: str

    # Revizyon sayaci
    revision_count: int

    # Maksimum revizyon sayisi
    max_revisions: int

    # Onaylanmis final cikti
    final_output: str

    # Canli log akisi
    logs: List[str]

    # Kullanici tarafindan secilen ozellestirilmis kapsam
    paper_title: Optional[str]
    focus_area: Optional[str]
    paper_type: Optional[str]
    target_platform: Optional[str]
    target_pages: Optional[str]
    target_images: Optional[int]
    scope_details: Optional[str]
    sources: Optional[List[Dict[str, str]]]
