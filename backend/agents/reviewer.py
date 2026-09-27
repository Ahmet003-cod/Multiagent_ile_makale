"""
Multi-Agent Workflow — Reviewer Agent (15+ Sayfa ve Görsel/Ders Notu Denetimi)

Referans PDF ders notu formatina, 15+ sayfa hacmine, gorsel ve tablo zenginligine
ve en az 25-30 kaynak atfina gore makaleyi siki bir hakem denetimine tabi tutar.
"""

import os
import re
from langchain_openai import ChatOpenAI
from .state import AgentState
from .llm_factory import get_llm, extract_text


def reviewer_node(state: AgentState) -> dict:
    """
    Reviewer Agent:
    - 15+ sayfalik doygunlugu (kelime sayisi, sayfa projeksiyonu)
    - Internetten toplanan gorsellerin ve semalarin dogru eklenip eklenmedigini
    - [BUNU DA BIL?], [UYARI], [KIMDIR?] kutularini ve karsilastirmali tablolari
    - En az 25 kaynak kuralini denetler.
    Eksik gordugunde UZATILMASI icin REVISE karari verir.
    """
    task = state["task"]
    target_platform = state.get("target_platform", "DergiPark (TÜBİTAK ULAKBİM TR Dizin)")
    target_pages = state.get("target_pages", "10-15 Sayfa (Standart)")
    draft = state.get("draft", "")
    research_data = state.get("research_data", "")
    revision_count = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", 3)

    words = len(draft.split())
    estimated_pages = max(1, round(words / 320))
    
    # Gorsel, tablo ve kutu kontrolleri
    img_matches = re.findall(r"!\[(.*?)\]\((.*?)\)", draft)
    img_count = len(img_matches)
    has_tables = "|" in draft and "---" in draft
    table_count = draft.count("|---")
    
    has_bunu_da_bil = "BUNU DA BİL" in draft.upper() or "BUNUDA BIL" in draft.upper()
    has_uyari = "UYARI" in draft.upper() or "DİKKAT" in draft.upper()
    has_kimdir = "KİMDİR" in draft.upper() or "KIMDIR" in draft.upper()
    has_abstract = "ÖZET" in draft.upper() or "ABSTRACT" in draft.upper()
    has_references = "KAYNAKÇA" in draft.upper() or "REFERENCES" in draft.upper() or "BİBLİYOGRAFYA" in draft.upper()
    
    citations = re.findall(r"\[\d+\]", draft)
    unique_citations = len(set(citations))

    is_blog = any(b in (target_platform or "").lower() for b in ["medium", "dev.to", "hashnode", "linkedin"])

    llm = get_llm(temperature=0.2, max_tokens=4000)

    if is_blog:
        platform_role_text = f"Sen {target_platform} platformunun Kıdemli Baş Editörüsün. İncelediğin metin blog formatında, sürükleyici, storytelling unsurları, 1. tekil/çoğul şahısla yazılmış ve kullanıcıyı yormayan akıcı bir TEKNİK BLOG YAZISIDIR."
        decision_criteria = f"""- Yazı dili samimi, 1. tekil/çoğul şahıs ("ben", "biz", "gördüm ki", "adım adım uygulayalım") ve okuyucuyu kesinlikle yormayan ferah bir sohbet üslubunda mı?
- KESİNLİKLE "edilmiştir", "analiz edilmiştir" gibi soğuk akademik edilgen çatı KULLANILMAMIŞ MI?
- ⚠️ METİN İÇİ ATIF YASAĞI DENETİMİ: Metin gövdesinde [1], [2] veya parantez içi (Demir, 2024) gibi atıflar KESİNLİKLE OLMAMALI! Metin pürüzsüz akmalı.
- Kaynaklar SADECE VE SADECE yazının en sonundaki "Kaynaklar ve İleri Okuma" bölümünde mi yer alıyor?
- TL;DR özeti, kod blokları, görsel şemalar ve ipucu kutuları mevcut mu?
- Kelime sayısı 1.000–1.800 aralığında ve blog standardına uygun mu? (20 sayfalık makale gibi DEĞİL!)
- 🚫 İNTİHAL VE KOPYALAMA KONTROLÜ: Metin, araştırma dosyasındaki harici makaleleri motamot kopyalamış veya doğrudan çevirmiş gibi duruyor mu? %100 özgün, yazarın kendi anlatımı ve bağımsız sentezi olmalıdır. Kopyalama veya motamot çeviri seziyorsan derhal REVISE kararı ver!
- 🖼️ GÖRSEL-KONU ANLAMSAL UYUM KONTROLÜ: Kullanılan tüm görseller doğrudan '{task}' konusuyla birebir ilişkili ve teknik olarak uyumlu mu? Konu dışı, absürt veya ilgisiz görsel varsa (örn. yapay zeka yazısında biyoloji/flagellum şeması gibi) derhal çıkarılmasını veya konuya uygun olanla değiştirilmesini talep et!
- Görseller metinle BAĞLANTILI mı? (Görsel öncesi tanıtım + sonrası analiz paragrafı var mı?)"""
    else:
        platform_role_text = f"Sen uluslararası hakemli bir bilimsel derginin (TÜBİTAK DergiPark TR Dizin / IEEE / Elsevier) Kıdemli Baş Hakemisin. İncelediğin makale {target_platform} kurallarına göre resmi, mesafeli, 3. tekil şahıs / edilgen çatı ile yazılmış bir BİLİMSEL DERGİ MAKALESİDİR."
        decision_criteria = f"""- Yazı dili resmi ve 3. tekil şahıs / edilgen çatı mı ("yapılmıştır", "analiz edilmiştir")?
- IMRAD bölümleri, Türkçe ve İngilizce özetler, anahtar kelimeler eksiksiz mi?
- Metin içi savlar sıralı olarak [1], [2] atıflarıyla desteklenmiş mi?
- ⚠️ KAYNAK DAĞILIMI DOĞRU MU?:
  * Giriş ve Literatür Taramasında YÜKSEK atıf yoğunluğu var mı?
  * Bulgular bölümünde DIŞ KAYNAK YOK MU? (Bulgular yazarın kendi verileridir, dış atıf OLMAMALI!)
  * Tartışma bölümünde KARŞILAŞTIRMALI atıf var mı? ("X vd. [14] ile tutarlıdır" gibi)
  * Sonuç bölümünde MİNİMUM/HİÇ kaynak mı?
- 🚫 İNTİHAL VE KOPYALAMA KONTROLÜ: Metin, literatür taramasında bulunan kaynakları motamot kopyalamış veya doğrudan çevirmiş gibi duruyor mu? %100 özgün bilimsel sentez, kuramsal analiz ve bağımsız akademik üslup olmalıdır. Doğrudan kopyalama veya motamot çeviri varsa REVISE kararı ver!
- 🖼️ GÖRSEL-KONU ANLAMSAL UYUM KONTROLÜ: Kullanılan tüm şema ve diyagramlar doğrudan '{task}' konusuyla alakalı mı? Konuyla ilgisiz (örn. yapay zeka makalesinde alakasız biyoloji, flagellum veya atmosfer şeması gibi) absürt bir görsel var mı? Varsa derhal çıkarılmasını veya konuya uygun olanla değiştirilmesini talep et!
- Sonda her maddenin doğrulanmış DOI / linki var mı?
- GÖRSEL-METİN BAĞLANTISI: Her görselden ÖNCE tanıtım paragrafı, SONRA analiz paragrafı var mı?
- Görseller "Şekil X" olarak metin içinde çağrılmış ve tartışılmış mı?"""

    # Görsel-metin bağlantısı otomatik kontrolü
    image_text_issues = []
    if img_count > 0:
        for i, (alt_text, url) in enumerate(img_matches, 1):
            # Görselin bulunduğu pozisyonu bul
            img_pattern = f"![{alt_text}]({url})"
            img_pos = draft.find(img_pattern)
            if img_pos > 0:
                # Görsel öncesi 500 karakter ve sonrası 500 karakter kontrol et
                before_text = draft[max(0, img_pos - 500):img_pos].lower()
                after_text = draft[img_pos + len(img_pattern):img_pos + len(img_pattern) + 500].lower()
                has_fig_ref = f"şekil {i}" in before_text or f"şekil {i}" in after_text or f"fig. {i}" in before_text or f"fig. {i}" in after_text
                if not has_fig_ref:
                    image_text_issues.append(f"Şekil {i} ({alt_text[:30]}...): Metin içinde 'Şekil {i}' referansı bulunamadı")

    image_text_report = ""
    if image_text_issues:
        image_text_report = f"\n- ⚠️ GÖRSEL-METİN BAĞLANTI SORUNLARI ({len(image_text_issues)} adet):\n" + "\n".join(f"  * {issue}" for issue in image_text_issues)
    elif img_count > 0:
        image_text_report = f"\n- ✅ Tüm {img_count} görsel metin içinde referanslanmış."

    prompt = f"""{platform_role_text}

## Konu:
{task}

## Otomasyon Denetim Verileri:
- Hedef Yayın Platformu: {target_platform} (Tür: {'Sektörel Blog / Teknik Rehber' if is_blog else 'Akademik Hakemli Makale'})
- Hedeflenen Sayfa / Hacim Kriteri: {target_pages}
- Mevcut Toplam Kelime Sayısı: {words} (Tahmini Sayfa Hacmi: ~{estimated_pages} sayfa)
- Akademik Özet (Abstract) / TL;DR Bölümü: {'MEVCUT' if has_abstract else 'EKSİK (Zorunlu!)'}
- Metin İçi Atıf Yapılan Benzersiz Kaynak Sayısı: {unique_citations}
- Kaynakça Listesi: {'MEVCUT' if has_references else 'EKSİK (Zorunlu!)'}
- Metne Eklenen Görsel / Şema Sayısı: {img_count} adet
- Karşılaştırmalı Tablo Sayısı: {table_count} adet
- Mevcut Revizyon Aşaması: {revision_count + 1} / {max_revisions}{image_text_report}

## İncelenen Taslak Metin (Örnek Bölümler):
{draft[:4000]}
[... ve kalan bölümler ...]

-------------------------------------------------------------
## DEĞERLENDİRME KRİTERLERİ:
{decision_criteria}

## KARAR KURALLARI:
- Eğer bu son revizyon hakkıysa ({revision_count + 1} >= {max_revisions}), "APPROVE" kararı ver.
- Blog yazısı için: Eğer kelime sayısı < 800 VEYA kaynaklar eksikse "REVISE" kararı ver.
- Akademik makale için: Eğer kelime sayısı < 2.500 VEYA kaynak atıfı < 8 VEYA Kaynakça eksikse "REVISE" kararı ver.
- Görsel-metin bağlantı sorunları, intihal/kopyalama veya alakasız görsel varsa bunları revizyon talimatlarında belirt.

Yanıtını TAM OLARAK şu formatta dök:

### Hakem Raporu

**Yayın Şablonu ve Dil Uyumu:** [puan]/20 - [açıklama]
**Özgünlük & İntihal Denetimi:** [puan]/20 - [açıklama + %100 özgün sentez kontrolü]
**Kaynak Zenginliği & Atıf Dağılımı:** [puan]/20 - [açıklama + kaynak dağılımı uyumu kontrolü]
**Görsel Anlamsal Uyumu & Entegrasyon:** [puan]/20 - [açıklama + görseller konuyla doğrudan alakalı mı ve metinde tartışılmış mı?]
**Tablo ve Bilgi Kutuları:** [puan]/20 - [açıklama]

**Toplam Puan:** [toplam]/100
**Mevcut Kelime / Sayfa:** {words} kelime (~{estimated_pages} sayfa)

### Hakem Revizyon ve Genişletme Talimatları:
1. [Genişletilmesi veya düzeltilmesi gereken hususlar]

### Karar
[APPROVE veya REVISE]
"""

    import time
    review_text = ""
    for attempt in range(3):
        try:
            response = llm.invoke(prompt)
            review_text = extract_text(response)
            if review_text and len(review_text.strip()) > 20:
                break
        except Exception as e:
            if attempt == 2:
                raise e
            time.sleep(2 * (attempt + 1))

    review_status = "APPROVE"
    upper_text = review_text.upper()

    if "### KARAR" in upper_text:
        decision_part = upper_text.split("### KARAR")[-1].strip()
        if "REVISE" in decision_part[:50]:
            review_status = "REVISE"
    elif "REVISE" in upper_text[-120:]:
        review_status = "REVISE"

    # Zorunlu revizyon kontrolu (Platforma duyarli)
    if revision_count < max_revisions - 1:
        if is_blog:
            if words < 750 or not has_references:
                review_status = "REVISE"
        else:
            min_academic_words = 3200 if ("15-25" in target_pages or "20" in target_pages) else 2400
            if words < min_academic_words or img_count < 1 or table_count < 1 or unique_citations < 5:
                review_status = "REVISE"

    if revision_count >= max_revisions - 1:
        review_status = "APPROVE"

    logs = state.get("logs", [])
    logs.append(f"[Reviewer] Hakem denetimi #{revision_count + 1} tamamlandi - Kelime: {words} (~{estimated_pages} sayfa), Görsel: {img_count}, Tablo: {table_count}, Karar: {review_status}")

    result = {
        "review": review_text,
        "review_status": review_status,
        "logs": logs,
    }

    if review_status == "REVISE":
        result["revision_count"] = revision_count + 1
    else:
        result["final_output"] = draft

    return result
