"""
Multi-Agent Workflow — Researcher Agent (Scholar & DergiPark Harvester)

Google Scholar, DergiPark ve arXiv veri tabanlarindan hakemli makaleleri arar,
teknik semalari toplar ve yazici ajana tam referansli bir akademik dosya hazirlar.
"""

import os
import re
from .state import AgentState
from .tools import (
    google_scholar_and_dergipark_tool,
    arxiv_paper_search_tool,
    image_search_tool,
    get_verified_academic_images,
    fetch_webpage_content_tool,
    web_search_tool,
)


def researcher_node(state: AgentState) -> dict:
    """
    Researcher Agent: Google Scholar, DergiPark ve arXiv araclarini kullanarak
    hakemli makale ozetlerini, yazarlari, DOI ve gorselleri derler.
    """
    task = state["task"]
    focus_area = state.get("focus_area", "")
    paper_type = state.get("paper_type", "Hakemli Bilimsel Dergi Makalesi")
    target_platform = state.get("target_platform", "DergiPark (TÜBİTAK ULAKBİM)")
    target_pages = state.get("target_pages", "10-15 Sayfa (Standart)")
    target_images = state.get("target_images", 4) or 4
    scope_details = state.get("scope_details", "")
    revision_count = state.get("revision_count", 0)
    review = state.get("review", "")

    search_query = f"{task} {focus_area}".strip() if focus_area else task

    logs = state.get("logs", [])
    logs.append(f"[Researcher] Akademik veri tabanları taranıyor (Platform: '{target_platform}', Hacim: '{target_pages}', Odak: '{search_query}')...")

    # 1. Hedef Platform Yayın Rehberi ve Şablon Kuralları
    from .tools import (
        target_platform_guidelines_tool, 
        zenodo_and_crossref_tool,
        get_verified_academic_sources
    )
    platform_guidelines = target_platform_guidelines_tool.invoke({"platform": target_platform})
    logs.append(f"[Researcher -> Tool] '{target_platform}' yayın kuralları ve şablon kriterleri yüklendi.")

    # 2. CrossRef, arXiv ve DergiPark Doğrulanmış Numaralı Kaynakça Havuzu
    logs.append(f"[Researcher -> Tool] 'get_verified_academic_sources' çağrılıyor: Gerçek DOI ve kalıcı bağlantılar toplanıyor...")
    verified_sources = get_verified_academic_sources(search_query, max_count=25)

    verified_sources_text = "### DOĞRULANMIŞ VE NUMARALANDIRILMIŞ KAYNAKÇA HAVUZU (YAZAR İÇİN KESİN SIRA REHBERİ):\n"
    for idx, s in enumerate(verified_sources, 1):
        verified_sources_text += f"[{idx}] {s['title']} — DOI/URL: {s['url']}\n"

    # 3. DergiPark ve Google Scholar Arama Aracı
    logs.append(f"[Researcher -> Tool] 'google_scholar_and_dergipark_tool' çağrılıyor: Hakemli üniversite dergileri ve TR Dizin...")
    scholar_res = google_scholar_and_dergipark_tool.invoke({"query": search_query})

    # 4. arXiv Bilimsel Yayın Arama Aracı
    logs.append(f"[Researcher -> Tool] 'arxiv_paper_search_tool' çağrılıyor: Global bilimsel yayınlar ve özetler...")
    arxiv_res = arxiv_paper_search_tool.invoke({"query": search_query})

    # 5. CrossRef & Zenodo Resmi DOI ve Açık Bilim Kaynakları
    logs.append(f"[Researcher -> Tool] 'zenodo_and_crossref_tool' çağrılıyor: Kalıcı DOI kayıtları ve açık erişim künyeleri...")
    crossref_res = zenodo_and_crossref_tool.invoke({"query": search_query})

    # 6. Görsel ve Mimari Şema Aracı (Doğrulanmış liste)
    logs.append(f"[Researcher -> Tool] 'image_search_tool' çağrılıyor: Teknik diyagramlar ve şemalar...")
    img_res = image_search_tool.invoke({"query": search_query})
    images_list = get_verified_academic_images(search_query, max_count=target_images)

    # 7. Güncel Web ve Literatür Verisi
    web_res = web_search_tool.invoke({"query": f"{search_query} akademik analiz istatistikleri ve kuramsal yaklaşımlar"})

    # 8. Kritik bir makalenin tam metnini oku
    top_article_extract = ""
    first_url_match = re.search(r"https?://[^\s\)]+", scholar_res)
    if first_url_match:
        target_url = first_url_match.group(0)
        logs.append(f"[Researcher -> Tool] 'fetch_webpage_content_tool' çağrılıyor: {target_url[:50]}...")
        top_article_extract = fetch_webpage_content_tool.invoke({"url": target_url})

    article_notice = ""
    if top_article_extract:
        article_notice = f"""
=============================================================
## 7. ÖRNEK LİTERATÜR İNCELEMESİ (YALNIZCA ARKA PLAN REFERANSI - KOPYALAMAK YASAKTIR):
⚠️ KESİN İNTİHAL UYARISI: Aşağıdaki metin harici bir makaleye aittir. Buradaki hiçbir cümleyi veya yapıyı AYNEN ALMAYINIZ!
Kendi özgün akademik argümanlarınızı ve modellerinizi bağımsız olarak geliştiriniz.

{top_article_extract[:3500]}
"""

    # Kapsamli ve tam arastirma dosyasi
    research_dossier = f"""# HEDEF YAYIN PLATFORMU VE AKADEMİK LİTERATÜR DOSYASI
Ana Konu: {task}
Hedef Yayın Platformu: {target_platform}
Hedef Sayfa Hacmi: {target_pages}
Odak Alanı: {focus_area if focus_area else 'Genel Kapsam'}
Hedef Yayın Formatı: {paper_type}
Ek Kapsam Notları: {scope_details}
Revizyon Döngüsü: #{revision_count + 1}
{"Hakem Revizyon Talebi: " + review if revision_count > 0 else ""}

=============================================================
## 0. HEDEF PLATFORMA ÖZEL DİZAYN VE FORMAT REHBERİ (ZORUNLU KURAL):
{platform_guidelines}

=============================================================
## 1. KESİN VE DOĞRULANMIŞ SIRALI KAYNAKLAR (METİN İÇİ [1], [2] ATIFLARINDA KULLANILACAK HAVUZ):
{verified_sources_text}

=============================================================
## 2. TEKNİK ŞEMALAR VE GÖRSELLER KATALOĞU (Yazara Sunulan):
{img_res}

=============================================================
## 3. DERGİPARK VE GOOGLE SCHOLAR HAKEMLİ MAKALELERİ (Tam Künye):
{scholar_res}

=============================================================
## 4. GLOBAL BİLİMSEL YAYINLAR (arXiv API):
{arxiv_res}

=============================================================
## 5. CROSSREF VE ZENODO RESMİ DOI KAYITLARI:
{crossref_res}

=============================================================
## 6. GÜNCEL VERİLER, VAKA ANALİZLERİ VE METODOLOJİ:
{web_res}
{article_notice}
"""

    logs.append(f"[Researcher] Akademik tarama tamamlandı — {len(images_list)} görsel şeması ve {len(verified_sources)} doğrulanmış DOI kaynakçası derlendi.")

    return {
        "research_data": research_dossier,
        "images": images_list,
        "sources": verified_sources,
        "max_revisions": 3,
        "logs": logs,
    }

