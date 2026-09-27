"""
Multi-Agent Workflow — Unified LLM Factory

Ucretsiz ve Premium LLM saglayicilarini tek bir merkezden yonetir:
1. Google Gemini (100% Ucretsiz - aistudio.google.com) -> gemini-1.5-flash / gemini-2.0-flash
2. Groq Cloud (100% Ucretsiz - console.groq.com) -> llama-3.3-70b-versatile
3. OpenAI -> gpt-4o / gpt-4o-mini
"""

import os
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel


def get_llm(temperature: float = 0.6, max_tokens: Optional[int] = None) -> BaseChatModel:
    """
    Ortam degiskenlerine gore en uygun (oncelikli olarak ucretsiz) LLM'i dondurur.
    
    Oncelik Sirasi:
    1. LLM_PROVIDER acikca belirtilmisse (gemini, groq, openai)
    2. GEMINI_API_KEY varsa -> Google Gemini (UCRETSIZ)
    3. GROQ_API_KEY varsa -> Groq Llama 3.3 (UCRETSIZ)
    4. OPENAI_API_KEY varsa -> OpenAI GPT-4o
    """
    provider = os.getenv("LLM_PROVIDER", "").lower().strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    # Eger secilen saglayicinin anahtari placeholder ise, dolu olan diger anahtara otomatik gec
    if provider == "gemini" and (not gemini_key or gemini_key == "your_gemini_api_key_here"):
        if openai_key and openai_key != "your_openai_api_key_here":
            provider = "openai"
        elif groq_key and groq_key != "your_groq_api_key_here":
            provider = "groq"
    elif provider == "groq" and (not groq_key or groq_key == "your_groq_api_key_here"):
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            provider = "gemini"
        elif openai_key and openai_key != "your_openai_api_key_here":
            provider = "openai"
    elif not provider:
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            provider = "gemini"
        elif groq_key and groq_key != "your_groq_api_key_here":
            provider = "groq"
        elif openai_key and openai_key != "your_openai_api_key_here":
            provider = "openai"
        else:
            provider = "openai"

    # 1. GOOGLE GEMINI (YUKSEK HIZ + KESINTISIZ FALLBACK ZINCIRI)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        primary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        primary_llm = ChatGoogleGenerativeAI(
            model=primary_model,
            google_api_key=gemini_key or os.getenv("GOOGLE_API_KEY", ""),
            temperature=temperature,
            max_output_tokens=max_tokens or 8192,
            max_retries=3,
        )

        fallbacks = []
        if primary_model != "gemini-flash-latest":
            fallbacks.append(ChatGoogleGenerativeAI(
                model="gemini-flash-latest",
                google_api_key=gemini_key or os.getenv("GOOGLE_API_KEY", ""),
                temperature=temperature,
                max_output_tokens=max_tokens or 8192,
                max_retries=2,
            ))

        # Eger Google sunuculari yogunluktan (503) yanit vermezse OpenAI GPT-4o'ya devret
        if openai_key and openai_key != "your_openai_api_key_here":
            from langchain_openai import ChatOpenAI
            fallbacks.append(ChatOpenAI(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                api_key=openai_key,
                temperature=temperature,
                max_tokens=max_tokens or 14000,
            ))

        if fallbacks:
            return primary_llm.with_fallbacks(fallbacks)
        return primary_llm

    # 2. GROQ CLOUD (100% UCRETSIZ TIER - 8000 TPM limitine uygun cap)
    elif provider == "groq":
        from langchain_groq import ChatGroq
        model_name = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        groq_max_tokens = min(max_tokens or 3500, 3500)
        return ChatGroq(
            model=model_name,
            api_key=groq_key,
            temperature=temperature,
            max_tokens=groq_max_tokens,
        )

    # 3. OPENAI (GPT-4o)
    else:
        from langchain_openai import ChatOpenAI
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
        return ChatOpenAI(
            model=model_name,
            api_key=openai_key,
            temperature=temperature,
            max_tokens=max_tokens or 14000,
        )



def extract_text(response) -> str:
    """LLM yanitindan temiz metni guvenle cikarir (str, list, dict uyumlu)."""
    if hasattr(response, "content"):
        content = response.content
    else:
        content = response
    
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif hasattr(item, "text"):
                parts.append(item.text)
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def get_active_provider_name() -> str:
    """Aktif calisan LLM saglayicisinin okunabilir adini dondurur."""
    provider = os.getenv("LLM_PROVIDER", "").lower().strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    if provider == "gemini" or (not provider and gemini_key and gemini_key != "your_gemini_api_key_here"):
        return f"Google Gemini ({os.getenv('GEMINI_MODEL', 'gemini-3.6-flash')} - Yüksek Hız & Kalite)"
    elif provider == "groq" or (not provider and groq_key and groq_key != "your_groq_api_key_here"):
        return f"Groq Cloud ({os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')} - Ücretsiz)"
    else:
        return f"OpenAI ({os.getenv('OPENAI_MODEL', 'gpt-4o')})"

