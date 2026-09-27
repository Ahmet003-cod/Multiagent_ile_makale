"""
Multi-Agent Workflow — FastAPI Backend Server (Enhanced)

SSE (Server-Sent Events) ile gercek zamanli agent durumu
guncellemesi saglayan REST API sunucusu.
Word (.docx) dosyasi indirme destegi ile.
"""

import os
import json
import asyncio
import uuid
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# .env dosyasini yukle
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from agents.graph import build_graph
from agents.docx_generator import create_word_document, extract_sources_from_text
from agents.llm_factory import get_active_provider_name

# FastAPI uygulamasi
app = FastAPI(
    title="Multi-Agent Workflow API",
    description="LangChain + LangGraph ile Researcher, Writer & Reviewer Multi-Agent Sistemi",
    version="2.5.0",
)

def validate_llm_keys():
    gemini = os.getenv("GEMINI_API_KEY", "").strip()
    groq = os.getenv("GROQ_API_KEY", "").strip()
    openai = os.getenv("OPENAI_API_KEY", "").strip()
    has_any = (
        (gemini and gemini != "your_gemini_api_key_here") or
        (groq and groq != "your_groq_api_key_here") or
        (openai and openai != "your_openai_api_key_here")
    )
    if not has_any:
        raise HTTPException(
            status_code=500,
            detail="LLM API Anahtarı bulunamadı! Lütfen .env dosyasında GEMINI_API_KEY (Ücretsiz: aistudio.google.com), GROQ_API_KEY (Ücretsiz: console.groq.com) veya OPENAI_API_KEY tanımlayın."
        )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cikti dizini
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Gecici sonuc deposu (basit in-memory store)
results_store = {}


class TaskRequest(BaseModel):
    task: str
    paper_title: str = ""
    focus_area: str = ""
    paper_type: str = "Hakemli Bilimsel Dergi Makalesi"
    target_platform: str = "DergiPark (TÜBİTAK ULAKBİM TR Dizin)"
    target_pages: str = "10-15 Sayfa (Standart Hakemli Makale)"
    target_images: int = 4
    scope_details: str = ""


class ChatScopeRequest(BaseModel):
    message: str
    history: list = []
    current_scope: dict = {}


class TaskResponse(BaseModel):
    task: str
    research_data: str
    draft: str
    review: str
    review_status: str
    revision_count: int
    final_output: str
    logs: list
    doc_id: str = ""


@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Multi-Agent Workflow API calisiyor",
        "version": "2.6.0",
        "provider": get_active_provider_name(),
    }


@app.post("/api/chat-scope")
async def chat_scope(request: ChatScopeRequest):
    """
    Akademik Danışman & Baş Editör Ajanı:
    Geniş konuları tespit eder, alt alanlara böler, kullanıcının yayınlayacağı
    platformu (DergiPark, IEEE, arXiv, Medium, LinkedIn vb.) ve şablonunu belirler.
    """
    validate_llm_keys()
    from agents.llm_factory import get_llm, extract_text
    import re

    llm = get_llm(temperature=0.7)

    user_msg = request.message.strip()
    history_text = ""
    for h in request.history[-6:]:
        role = "Kullanıcı" if h.get("role") == "user" else "Akademik Danışman"
        history_text += f"{role}: {h.get('content')}\n"

    scope = request.current_scope or {}

    prompt = f"""Sen saygın bir uluslararası akademik derginin Baş Editörü ve Kıdemli Tez Danışmanısın.
Kullanıcı seninle yeni bir bilimsel makale, ön basım veya teknik monografi yazımı için planlama yapıyor.

Kullanıcının son iletisi: "{user_msg}"
Mevcut Belirlenen Kapsam: {json.dumps(scope, ensure_ascii=False)}
Sohbet Geçmişi:
{history_text}

GÖREVİN VE DİYALOG KURALLARI:
1. Kullanıcı genel veya geniş bir konu yazdıysa (örn: "Yapay zeka", "Biyoteknoloji", "Siber Güvenlik", "Blokzincir"):
   - Doğrudan şöyle hitap et: "Harika bir çalışma konusu! Ancak bu alan oldukça geniş ve çok boyutlu bir disiplini kapsıyor. Makalenizin literatürde gerçek bir bilimsel özgünlük ve derinlik kazanabilmesi için şu alt alanlardan hangisine odaklanmak istersiniz?"
   - Konuya özel 4-5 tane net ve spesifik **Alt Odak Alanı** öner.
2. Yayınlanacak Platformu ve Sayfa Hacmini Sor (ZORUNLU):
   - Kullanıcıya: "Ayrıca bu çalışmanızı hangi platformda yayınlamayı planlıyorsunuz (DergiPark TR Dizin, IEEE/Elsevier, arXiv, Medium vb.) ve hedeflenen sayfa sayısı (örn: 5-8 sayfa kısa bildiri, 10-15 sayfa standart hakemli makale, 18-25 sayfa kapsamlı monografi) nedir? Makalenin editoryal yapısını, kaynakça stilini ve derinliğini bu kurallara göre kurgulayacağız." şeklinde açıkça sor.
3. Akademik Başlığı Birlikte Belirle (ZORUNLU):
   - Konuya ve seçilen alana uygun 3 adet prestijli, saygın ve yayınlanmaya hazır **Akademik Makale Başlığı** (title_options) türet.
   - Danışman yanıtında: "Makalenizin başlığı için de şu seçenekleri belirledim, dilediğinizi seçebilir veya yenisini belirtebilirsiniz:" diyerek bu başlıkları sun.
4. Eğer kullanıcı bir platform, sayfa sayısı, başlık veya alt alan belirttiyse, bunu teyit et ve kapsamı güncelle.
5. Eğer kullanıcı "başla", "tamamdır", "yaz", "oluştur" dediyse veya gerekli tercihler netleştiyse `ready_to_start: true` yap.

YANITINI SADECE VE SADECE GEÇERLİ BİR JSON OBJESİ OLARAK DÖNDÜR (JSON bloğu dışında hiçbir metin veya markdown etiketi ekleme):
{{
  "reply": "Kullanıcıya hitaben samimi, teşvik edici, uzman danışman mesajı (Markdown formatında, başlık alternatifleri, platform ve sayfa sayısı vurgusuyla)",
  "is_broad_topic": true,
  "title_options": ["1. Akademik Başlık Önerisi", "2. Akademik Başlık Önerisi", "3. Akademik Başlık Önerisi"],
  "focus_options": ["1. Odak Alanı", "2. Odak Alanı", "3. Odak Alanı", "4. Odak Alanı", "5. Odak Alanı"],
  "platform_categories": [
    {{
      "category": "Akademik Hakemli Yayınlar",
      "options": ["DergiPark (TÜBİTAK ULAKBİM TR Dizin)", "Uluslararası Hakemli (IEEE / Elsevier / Springer)"]
    }},
    {{
      "category": "Ön Basım Sunucuları (Preprint)",
      "options": ["arXiv (Bilgisayar & Yapay Zeka)", "SSRN (İşletme, Ekonomi & Hukuk)", "Zenodo (CERN Açık Veri & DOI)"]
    }},
    {{
      "category": "Akademik Sosyal Ağlar",
      "options": ["ResearchGate & Academia.edu", "Google Akademik (Scholar Profil)"]
    }},
    {{
      "category": "Teknik & Geliştirici Blogu",
      "options": ["Medium (Towards Data Science)", "Dev.to & Hashnode", "LinkedIn Articles (Sektörel Liderlik)"]
    }}
  ],
  "platform_options": [
    "DergiPark (TÜBİTAK ULAKBİM TR Dizin)",
    "Uluslararası Hakemli (IEEE / Elsevier / Springer)",
    "arXiv (Bilgisayar & Yapay Zeka)",
    "SSRN (İşletme, Ekonomi & Hukuk)",
    "Zenodo (CERN Açık Veri & DOI)",
    "ResearchGate & Academia.edu",
    "Medium (Towards Data Science)",
    "Dev.to & Hashnode",
    "LinkedIn Articles (Sektörel Liderlik)"
  ],
  "page_options": [
    "5-8 Sayfa (Kısa Bildiri / Konferans)",
    "10-15 Sayfa (Standart Hakemli Makale)",
    "18-25 Sayfa (Kapsamlı Monografi / Tez)",
    "30+ Sayfa (Büyük Rapor & Kitap Bölümü)"
  ],
  "image_options": ["3-4 Mimari Şema & Akış Diyagramı", "5-6 Zengin Teknik Görsel", "Yalnızca Tablolar (Görselsiz)"],
  "ready_to_start": false,
  "updated_scope": {{
    "task": "{scope.get('task') or user_msg}",
    "paper_title": "{scope.get('paper_title', '')}",
    "focus_area": "{scope.get('focus_area', '')}",
    "paper_type": "{scope.get('paper_type', 'Hakemli Bilimsel Dergi Makalesi')}",
    "target_platform": "{scope.get('target_platform', 'DergiPark (TÜBİTAK ULAKBİM TR Dizin)')}",
    "target_pages": "{scope.get('target_pages', '10-15 Sayfa (Standart Hakemli Makale)')}",
    "target_images": {scope.get('target_images', 4)},
    "scope_details": "{scope.get('scope_details', '')}"
  }}
}}
"""
    try:
        res = llm.invoke(prompt)
        text = extract_text(res).strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text.strip())
        return data
    except Exception as e:
        return {
            "reply": f"Harika bir konu! '{user_msg}' üzerine derinlikli bir makale için alt odakları, platformu ve başlık alternatiflerini belirleyelim.",
            "is_broad_topic": True,
            "title_options": [
                f"{user_msg}: Teori, Metodoloji ve Güncel Gelişmeler",
                f"{user_msg} Alanında Yeni Yaklaşımlar ve Sistematik İnceleme",
                f"Modern Sistemlerde {user_msg}: Ampirik Bulgular ve Gelecek Vizyonu"
            ],
            "focus_options": [f"{user_msg} Teknik Mimarisi", f"{user_msg} Etik ve Hukuki Boyutları", f"{user_msg} Sektörel Uygulamaları", f"{user_msg} Performans ve Güvenlik"],
            "platform_options": [
                "DergiPark (TÜBİTAK ULAKBİM TR Dizin)",
                "Uluslararası Hakemli (IEEE / Elsevier / Springer)",
                "arXiv (Bilgisayar & Yapay Zeka)",
                "SSRN (İşletme, Ekonomi & Hukuk)",
                "Zenodo (CERN Açık Veri & DOI)",
                "ResearchGate & Academia.edu",
                "Medium (Towards Data Science)",
                "Dev.to & Hashnode",
                "LinkedIn Articles (Sektörel Liderlik)"
            ],
            "page_options": [
                "5-8 Sayfa (Kısa Bildiri / Konferans)",
                "10-15 Sayfa (Standart Hakemli Makale)",
                "18-25 Sayfa (Kapsamlı Monografi / Tez)",
                "30+ Sayfa (Büyük Rapor & Kitap Bölümü)"
            ],
            "image_options": ["3-4 Mimari Şema & Akış Diyagramı", "5-6 Zengin Teknik Görsel", "Yalnızca Tablolar (Görselsiz)"],
            "ready_to_start": False,
            "updated_scope": {
                "task": scope.get("task") or user_msg,
                "paper_title": scope.get("paper_title") or f"{user_msg}: Teori, Metodoloji ve Güncel Gelişmeler",
                "focus_area": scope.get("focus_area", ""),
                "paper_type": "Hakemli Bilimsel Dergi Makalesi",
                "target_platform": scope.get("target_platform", "DergiPark (TÜBİTAK ULAKBİM TR Dizin)"),
                "target_pages": scope.get("target_pages", "10-15 Sayfa (Standart Hakemli Makale)"),
                "target_images": 4,
                "scope_details": ""
            }
        }


@app.post("/api/run")
async def run_workflow(request: TaskRequest):
    """Workflow'u senkron olarak calistirir ve sonucu doner."""
    if not request.task.strip():
        raise HTTPException(status_code=400, detail="Gorev bos olamaz")

    validate_llm_keys()

    try:
        graph = build_graph()

        initial_state = {
            "task": request.task,
            "paper_title": request.paper_title,
            "focus_area": request.focus_area,
            "paper_type": request.paper_type,
            "target_platform": request.target_platform,
            "target_pages": request.target_pages,
            "target_images": request.target_images,
            "scope_details": request.scope_details,
            "research_data": "",
            "images": [],
            "draft": "",
            "review": "",
            "review_status": "",
            "revision_count": 0,
            "max_revisions": 3,
            "final_output": "",
            "logs": [],
        }

        result = graph.invoke(initial_state)

        final_output = result.get("final_output", result.get("draft", ""))

        # Word dosyasi olustur
        doc_id = str(uuid.uuid4())[:8]
        doc_filename = f"makale_{doc_id}.docx"
        doc_path = os.path.join(OUTPUT_DIR, doc_filename)

        doc_title = request.paper_title.strip() if request.paper_title else request.task
        verified_sources = result.get("sources", [])
        extracted_sources = extract_sources_from_text(final_output)
        combined_sources = verified_sources if verified_sources else extracted_sources

        gathered_images = result.get("images", [])
        create_word_document(
            title=doc_title,
            content=final_output,
            sources=combined_sources if combined_sources else None,
            images=gathered_images,
            output_path=doc_path,
            target_platform=request.target_platform,
        )

        # Sonucu depola
        results_store[doc_id] = {
            "task": request.task,
            "paper_title": doc_title,
            "final_output": final_output,
            "doc_path": doc_path,
            "doc_filename": doc_filename,
        }

        return TaskResponse(
            task=result.get("task", request.task),
            research_data=result.get("research_data", ""),
            draft=result.get("draft", ""),
            review=result.get("review", ""),
            review_status=result.get("review_status", ""),
            revision_count=result.get("revision_count", 0),
            final_output=final_output,
            logs=result.get("logs", []),
            doc_id=doc_id,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow hatasi: {str(e)}")


async def event_generator(
    task: str,
    paper_title: str = "",
    focus_area: str = "",
    paper_type: str = "Hakemli Bilimsel Dergi Makalesi",
    target_platform: str = "DergiPark (TÜBİTAK ULAKBİM TR Dizin)",
    target_pages: str = "10-15 Sayfa (Standart Hakemli Makale)",
    target_images: int = 4,
    scope_details: str = ""
) -> AsyncGenerator[str, None]:
    """SSE stream generator."""
    doc_id = str(uuid.uuid4())[:8]

    try:
        graph = build_graph()

        initial_state = {
            "task": task,
            "paper_title": paper_title,
            "focus_area": focus_area,
            "paper_type": paper_type,
            "target_platform": target_platform,
            "target_pages": target_pages,
            "target_images": target_images,
            "scope_details": scope_details,
            "research_data": "",
            "images": [],
            "draft": "",
            "review": "",
            "review_status": "",
            "revision_count": 0,
            "max_revisions": 3,
            "final_output": "",
            "logs": [],
        }

        final_output = ""
        latest_draft = ""
        verified_sources = []
        gathered_images = []

        for step_output in graph.stream(initial_state):
            for node_name, node_state in step_output.items():
                event_data = {
                    "agent": node_name,
                    "status": "completed",
                    "logs": node_state.get("logs", []),
                    "data": {},
                }

                if node_name == "researcher":
                    event_data["data"]["research_data"] = node_state.get("research_data", "")
                    if node_state.get("sources"):
                        verified_sources = node_state["sources"]
                    if node_state.get("images"):
                        gathered_images = node_state["images"]

                elif node_name == "writer":
                    latest_draft = node_state.get("draft", "")
                    event_data["data"]["draft"] = latest_draft

                elif node_name == "reviewer":
                    event_data["data"]["review"] = node_state.get("review", "")
                    event_data["data"]["review_status"] = node_state.get("review_status", "")
                    event_data["data"]["revision_count"] = node_state.get("revision_count", 0)
                    if node_state.get("final_output"):
                        final_output = node_state["final_output"]
                        event_data["data"]["final_output"] = final_output

                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)

        if not final_output and latest_draft:
            final_output = latest_draft

        # Word dosyasi olustur
        if final_output:
            doc_filename = f"makale_{doc_id}.docx"
            doc_path = os.path.join(OUTPUT_DIR, doc_filename)

            doc_title = paper_title.strip() if paper_title else task
            extracted_sources = extract_sources_from_text(final_output)
            combined_sources = verified_sources if verified_sources else extracted_sources
            create_word_document(
                title=doc_title,
                content=final_output,
                sources=combined_sources if combined_sources else None,
                images=gathered_images,
                output_path=doc_path,
                target_platform=target_platform,
            )

            results_store[doc_id] = {
                "task": task,
                "paper_title": doc_title,
                "final_output": final_output,
                "doc_path": doc_path,
                "doc_filename": doc_filename,
            }

        # Tamamlandi sinyali
        yield f"data: {json.dumps({'agent': 'system', 'status': 'completed', 'message': 'Workflow tamamlandi', 'doc_id': doc_id}, ensure_ascii=False)}\n\n"

    except Exception as e:
        error_data = {
            "agent": "system",
            "status": "error",
            "message": str(e),
        }
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"


@app.post("/api/stream")
async def stream_workflow(request: TaskRequest):
    """Workflow'u SSE stream olarak calistirir."""
    if not request.task.strip():
        raise HTTPException(status_code=400, detail="Gorev bos olamaz")

    validate_llm_keys()

    return StreamingResponse(
        event_generator(
            task=request.task,
            paper_title=request.paper_title,
            focus_area=request.focus_area,
            paper_type=request.paper_type,
            target_platform=request.target_platform,
            target_pages=request.target_pages,
            target_images=request.target_images,
            scope_details=request.scope_details
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/download/{doc_id}")
async def download_document(doc_id: str):
    """Olusturulan Word belgesini indir."""
    if doc_id not in results_store:
        raise HTTPException(status_code=404, detail="Belge bulunamadi")

    doc_info = results_store[doc_id]
    doc_path = doc_info["doc_path"]

    if not os.path.exists(doc_path):
        raise HTTPException(status_code=404, detail="Dosya bulunamadi")

    return FileResponse(
        path=doc_path,
        filename=doc_info["doc_filename"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))

    print(f"[*] Multi-Agent Workflow API baslatiliyor: http://{host}:{port}")
    print(f"[*] API Docs: http://{host}:{port}/docs")

    uvicorn.run(app, host=host, port=port)
