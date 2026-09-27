"""
Multi-Agent Workflow — LangGraph Workflow Definition (Iterative Expansion Loop)

Researcher → Writer → Reviewer akisini tanimlar.
Reviewer "REVISE" karari verdiginde dogrudan Writer'a doner,
Writer metni elestiriler dogrultusunda UZATARAK ve DERINLESTIREREK yeniden yazar.
Bu dongu makale istenen doygunluga ulasana kadar devam eder.
"""

from langgraph.graph import StateGraph, END
from .state import AgentState
from .researcher import researcher_node
from .writer import writer_node
from .reviewer import reviewer_node


def should_continue(state: AgentState) -> str:
    """
    Reviewer kararina gore akisi yonlendir.
    
    - "REVISE"  → Writer'a don ve taslagi UZAT/GENISLET.
    - "APPROVE" → END (Akis biter, monografi onaylandi).
    """
    review_status = state.get("review_status", "APPROVE")
    revision_count = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", 3)

    if review_status == "REVISE" and revision_count < max_revisions:
        return "writer"
    else:
        return "end"


def build_graph() -> StateGraph:
    """Multi-Agent Workflow grafigini olusturur ve derler."""
    workflow = StateGraph(AgentState)

    # Node'lar
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("reviewer", reviewer_node)

    # Giris noktasi: Derin arastirma
    workflow.set_entry_point("researcher")

    # Researcher -> Writer
    workflow.add_edge("researcher", "writer")

    # Writer -> Reviewer
    workflow.add_edge("writer", "reviewer")

    # Reviewer Kosullu Yonlendirme (Iterative Expansion Loop)
    workflow.add_conditional_edges(
        "reviewer",
        should_continue,
        {
            "writer": "writer",  # REVISE -> Writer'a don, metni UZAT ve derinlestir!
            "end": END,          # APPROVE -> Tamamla
        },
    )

    app = workflow.compile()
    return app
