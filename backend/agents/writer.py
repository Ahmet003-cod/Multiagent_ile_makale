"""
Multi-Agent Workflow — Writer Agent (Platform-Aware Academic & Blog Content Generator)

Platform tipine göre tamamen farklı yazım mimarileri kullanır:
- Akademik (DergiPark, IEEE, arXiv): IMRaD, edilgen çatı, bölüme göre kaynak dağılımı
- Blog (Medium, Dev.to, LinkedIn): Storytelling, kod blokları, metin içi hyperlink

Görsel-Metin Entegrasyonu:
- Her görsel metinde tartışılır ve analiz edilir
- Görseller bağlamsız yerleştirilmez, öncesinde/sonrasında açıklama ve yorumlama yapılır

Kaynak Dağılımı Kuralları (Akademik):
- Özet: 0 kaynak
- Giriş + Literatür: EN YÜKSEK yoğunluk
- Metodoloji: Seçici (bilinen araç/veri seti referansları)
- Bulgular: SIFIR kaynak (yazarın kendi verileri!)
- Tartışma: Karşılaştırmalı kaynak
- Sonuç: Minimum/hiç kaynak
"""

import os
import re
from langchain_openai import ChatOpenAI
from .state import AgentState
from .llm_factory import get_llm, extract_text


# ==============================================================================
# KAYNAK DAĞILIMI REHBERİ (Akademik Platformlar İçin)
# ==============================================================================
CITATION_DISTRIBUTION_GUIDE = """
## ⚠️ BÖLÜMLERE GÖRE KAYNAK (ATIF) DAĞILIMI KURALLARI (KESİN UYULACAK):

Kaynaklar metnin HER YERİNE rastgele serpilmez! Her bölümün kaynak yoğunluğu farklıdır:

| Bölüm | Kaynak Yoğunluğu | Açıklama |
|---|---|---|
| **ÖZET (Abstract)** | ❌ SIFIR kaynak | Özet tamamen bağımsızdır, hiçbir atıf içermez |
| **1. GİRİŞ** | 🟢 YÜKSEK yoğunluk | Problem arka planı, araştırma motivasyonu ve mevcut durumu kaynaklı anlatılır |
| **2. LİTERATÜR TARAMASI** | 🟢🟢 EN YÜKSEK yoğunluk | Önceki çalışmaların detaylı analizi — her paragrafta birden fazla [1], [2] atfı |
| **3. METODOLOJİ** | 🟡 SEÇİCİ | Sadece bilinen araçlar, veri setleri ve algoritmalara atıf (Adam optimizer [14], ImageNet [15] gibi). Yazarın kendi yeni yöntemi atıfsızdır! |
| **4. BULGULAR** | ❌ SIFIR veya MİNİMUM | Bu bölüm TAMAMEN yazarın kendi ampirik verilerini sunar. Dış kaynak buraya KONULMAZ! |
| **5. TARTIŞMA** | 🟡 KARŞILAŞTIRMALI | Yazarın bulgularını önceki çalışmalarla kıyaslar: "Zhao vd. [14] benzer sonuçlara ulaşmıştır" veya "Martinez [15]'in aksine..." |
| **6. SONUÇ** | ❌ MİNİMUM / HİÇ | Sentez bölümüdür, yeni atıf eklenmez. Sadece çalışmanın katkıları özetlenir |
| **KAYNAKÇA** | — | Metin içindeki tüm [1]...[N] atıfları burada tam künyeli ve DOI/linkli listelenir |

BU TABLOYA UYMA! Bulgu bölümüne kaynak serpiştirme, giriş/literatürde yoğunlaştır!
"""

# ==============================================================================
# GÖRSEL-METİN ENTEGRASYON REHBERİ
# ==============================================================================
IMAGE_TEXT_INTEGRATION_GUIDE = """
## 🖼️ GÖRSEL-METİN BAĞLANTISI KURALLARI (KESİN UYULACAK):

Her görsel/şema/diyagram metinle BAĞLANTILI olmalıdır. Görseli koyduktan sonra geçme!

### DOĞRU KULLANIM (Zorunlu):
Her görselden ÖNCE tanıtım paragrafı yaz, görselden SONRA analiz/yorum paragrafı yaz:

```
[Tanıtım paragrafı]: "Önerilen sistemin genel mimarisi Şekil 1'de görselleştirilmiştir. Bu mimari üç temel katmandan oluşmaktadır..."

![Şekil Başlığı](URL)
*Şekil 1: Önerilen çok katmanlı transformer mimarisi — Kaynak: Wikimedia Commons*

[Analiz paragrafı]: "Şekil 1'de görüldüğü üzere, birinci katman (giriş kodlayıcısı) ham veriyi 512 boyutlu vektörlere dönüştürmektedir. İkinci katmandaki çok-başlı dikkat mekanizması, ardışık bağımlılıkları %23 daha düşük gecikmeyle yakalamaktadır..."
```

### YANLIŞ KULLANIM (Yapma!):
- Görseli paragraflar arasına bırakıp hiç bahsetmemek
- Sadece "Şekil 1'de gösterilmiştir." yazıp geçmek (analiz yok!)
- Görselin konusuyla ilgisiz bir bölüme yerleştirmek

### IEEE KURALI:
- Şekil altyazıları görselin ALTINDA: `*Şekil X: Açıklama*`
- Tablo başlıkları tablonun ÜSTÜNDE
- Her şekil ve tablo metin içinde ismiyle (`Şekil 1`, `Tablo I`) çağrılmalıdır
"""


# ==============================================================================
# İNTİHAL ÖNLEME VE ÖZGÜN SENTEZ REHBERİ (ZORUNLU KURAL)
# ==============================================================================
ANTI_PLAGIARISM_GUIDE = """
## 🚫 İNTİHAL VE BİREBİR KOPYALAMA YASAĞI (KESİN VE TAVİZSİZ KURAL):
1. **ASLA DIŞ KAYNAKLARI BİREBİR KOPYALAMA VEYA MOTAMOT ÇEVİRME:**
   - Araştırma dosyasında (`research_data`) sunulan literatür özetleri, makale kesitleri veya web içerikleri yalnızca *arka plan bağlamı ve fikir referansı* içindir.
   - Herhangi bir makaleden veya kaynaktan doğrudan cümle, paragraf veya yapıyı kopyalayıp Türkçeye motamot çevirmek KESİNLİKLE YASAKTIR!
   - Metin %100 özgün, yazarın kendi analitik sentezi, kuramsal değerlendirmesi ve bağımsız bilimsel üslubuyla kaleme alınmalıdır.
2. **KENDİ ÖZGÜN PARAFRAZ VE ANALİZİNİ KUR:**
   - Literatürdeki bulguları ve kuramları kendi cümlelerinle sentezle ("X araştırmacısının ortaya koyduğu gibi... ancak bu yaklaşım...", "Literatürde X ve Y arasındaki korelasyon tartışılmakta olup...").
   - Kendi bağımsız karşılaştırma tablolarını, kendi analitik kutularını ve özgün mantık akışını oluştur.
"""


# ==============================================================================
# BİLGİ SEVİYESİ, TARİHÇE VE YARATICI DERİNLİK REHBERİ
# ==============================================================================
KNOWLEDGE_DEPTH_GUIDE = """
## 🧠 YÜKSEK BİLGİ DÜZEYİ, TARİHÇE VE YARATICI DERİNLİK KURALLARI (ZORUNLU):

Metin kesinlikle yüzeysel ("X çok önemlidir", "gelecekte gelişecektir" gibi boş laflarla) GEÇİŞTİRİLMEYECEKTİR!
Okuyucuya gerçek bir başvuru kaynağı, monografi ve ansiklopedik yetkinlikte derin bir bilgi sunulmalıdır:

1. **📜 TARİHSEL EVRİM VE DÖNÜM NOKTALARI:**
   - Konunun kökeni nerede başladı? Hangi matematiksel/teknolojik krizden doğdu?
   - Alanın öncü isimleri (örn: Alan Turing, Richard Feynman, Claude Shannon, John von Neumann, David Deutsch vb.), yaptıkları kritik yayınlar ve yıllarıyla birlikte dönüm noktaları.
   - İlk teorik modellerden günümüz modern mimarilerine uzanan tarihsel paradigma kırılımları.
   - Özel Kutu: `> 📜 **TARİHSEL KİLOMETRE TAŞI:** [Yıl, öncü bilim insanı ve dönüm noktası olan kuramsal buluş]`

2. **🔬 TEKNİK MİMARİ VE ALT MEKANİZMALAR (Yüksek Bilgi Düzeyi):**
   - Yalnızca "ne yaptığını" değil, "nasıl çalıştığını", arka plandaki matematiksel, mantıksal ve algoritmik temelleri anlat.
   - Formüller ($$...$$), denklemler, parametreler, veri akışları ve donanım/yazılım darboğazları.
   - Özel Kutu: `> 💡 **DERİN TEKNİK ANALİZ:** [Mimarinin en kritik matematiksel veya algoritmik çalışma ilkesi]`

3. **📊 KARŞILAŞTIRMALI ANALİZ VE MÜHENDİSLİK TAVİZLERİ (Trade-offs):**
   - Hiçbir sistem kusursuz değildir. Alternatif yaklaşımlarla (geleneksel vs modern) kıyaslayan detaylı Markdown tabloları.
   - Hız vs doğruluk, karmaşıklık vs ölçeklenebilirlik gibi mühendislik tavizlerini somut metriklerle ortaya koy.
   - Özel Kutu: `> ⚠️ **KRİTİK DARBOĞAZ / MÜHENDİSLİK SINIRI:** [Sistemin karşılaştığı donanımsal, algoritmik veya etik engeller]`

4. **🎯 EĞİTİCİ VE SÜRÜKLEYİCİ ANLATI AKIŞI:**
   - Bilgiler mantıksal bir pedagojik sırayla inşa edilmelidir: Problem Durumu -> Tarihçe -> Mimari ve Metodoloji -> Bulgular ve Karşılaştırma -> Gelecek Vizyonu.
"""


def writer_node(state: AgentState) -> dict:
    """
    Writer Agent — Platform-Aware & High-Knowledge Depth:
    - Akademik: IMRaD yapısı, tarihsel derinlik, bölüme göre kaynak dağılımı, görsel-metin entegrasyonu
    - Blog: Storytelling, 1. şahıs, sıfır metin içi atıf, TL;DR, kod blokları
    """
    task = state["task"]
    focus_area = state.get("focus_area", "")
    paper_type = state.get("paper_type", "Hakemli Bilimsel Dergi Makalesi")
    target_platform = state.get("target_platform", "DergiPark (TÜBİTAK ULAKBİM)")
    target_pages = state.get("target_pages", "10-15 Sayfa (Standart Hakemli Makale)")
    target_images = state.get("target_images", 4)
    scope_details = state.get("scope_details", "")
    research_data = state.get("research_data", "")
    images = state.get("images", [])
    revision_count = state.get("revision_count", 0)
    previous_draft = state.get("draft", "")
    review = state.get("review", "")

    from .tools import target_platform_guidelines_tool
    platform_rules = target_platform_guidelines_tool.invoke({"platform": target_platform})

    llm = get_llm(temperature=0.6, max_tokens=16000)

    # Görsel listesini yazara bağlamsal entegrasyon talimatıyla hazırla
    images_prompt_text = ""
    if images:
        images_prompt_text = "### 🖼️ METİNDE KULLANILACAK 4 FARKLI DİYAGRAM VE ŞEMA (HEPSİ METNE YERLEŞTİRİLECEK VE ANALİZ EDİLECEK):\n"
        for idx, img in enumerate(images[:target_images], 1):
            images_prompt_text += f"- Şekil {idx}: {img['title']}\n  URL: {img['url']}\n  (Kaynak: {img['source']})\n"
        images_prompt_text += f"""
{IMAGE_TEXT_INTEGRATION_GUIDE}

⚠️ ÇOK ÖNEMLİ GÖRSEL KURALI:
- Yukarıda verilen {len(images[:target_images])} görselin HEPSİ birbirinden FARKLI ve özeldir!
- Her şekil numarası (Şekil 1, Şekil 2, Şekil 3, Şekil 4) için YALNIZCA KENDİ ÖZEL URL'SİNİ KULLAN!
- Asla aynı görseli veya aynı URL'yi tekrarlama!
- Metnin ilgili bölümlerine şu formatta yerleştir:
![Şekil Başlığı](URL)
*Şekil X: Açıklama — Görsel Kaynağı: Kaynak*
"""

    scope_prompt_text = f"\n- **Hedef Yayın Platformu:** {target_platform}\n- **Hedef Sayfa Hacmi:** {target_pages}"
    if focus_area:
        scope_prompt_text += f"\n- **Özel Odak Alanı:** {focus_area}"
    if paper_type:
        scope_prompt_text += f"\n- **Yayın Türü:** {paper_type}"
    if scope_details:
        scope_prompt_text += f"\n- **Kullanıcı Özel Direktifleri:** {scope_details}"

    is_blog = any(b in (target_platform or "").lower() for b in ["medium", "dev.to", "hashnode", "linkedin"])

    # Sayfa ve kelime hacmi kurgusu
    if is_blog:
        if "dev.to" in target_platform.lower() or "hashnode" in target_platform.lower():
            target_words_instruction = "HEDEF HACİM: 1.000 – 2.200 KELİME (Geliştirici odaklı, step-by-step tutorial, çalışan kod blokları). FAZLA UZATMA!"
        elif "linkedin" in target_platform.lower():
            target_words_instruction = "HEDEF HACİM: 1.000 – 1.500 KELİME (C-Level ve sektörel liderlik, kısa paragraflar, bullet points). FAZLA UZATMA!"
        else:  # Medium / Towards Data Science
            target_words_instruction = "HEDEF HACİM: 1.000 – 1.800 KELİME (~5-8 dakika okuma süresi). Sürükleyici storytelling + teknik derinlik. FAZLA UZATMA!"
    else:
        if "15-25" in target_pages or "20" in target_pages:
            target_words_instruction = "HEDEF HACİM: 15–25 SAYFALIK KAPSAMLI MONOGRAFİ (EN AZ 5.000 – 7.500 KELİME). Her ana bölüm altında en az 2-3 derin alt başlık ve her alt başlıkta 3-4 paragraf."
        elif "10-15" in target_pages:
            target_words_instruction = "HEDEF HACİM: 10–15 SAYFALIK STANDART HAKEMLİ MAKALE (EN AZ 3.500 – 5.000 KELİME). Detaylı ampirik analizler ve kuramsal tartışmalar."
        else:
            target_words_instruction = "HEDEF HACİM: 5–8 SAYFALIK BİLDİRİ / KONFERANS MAKALESİ (2.000 – 2.800 KELİME)."

    # Başlık Bloku
    paper_title = state.get("paper_title", "")
    if paper_title:
        title_block = f"""# {paper_title}"""
    else:
        title_block = f"""# [{task}: Alana Özgü, Saygın ve Kapsamlı Başlık]"""

    # =========================================================================
    # 1. KATEGORİ: SEKTÖREL, TEKNİK BLOG VE TOPLULUK PLATFORMLARI
    # =========================================================================
    if is_blog:
        # Platform-specific blog tone
        if "dev.to" in target_platform.lower() or "hashnode" in target_platform.lower():
            blog_tone_guide = """
**DEV.TO / HASHNODE YAZI TONU (KESİN UYULACAK):**
- Geliştiriciden geliştiriciye samimi, doğrudan, pratik ("straight to the point")
- Adım adım tutorial veya problem-çözüm dili
- "We've all been there when...", "Install the package...", "Run the migration..."
- KESİNLİKLE akademik dilden uzak dur! "edilmiştir", "saptanmıştır" gibi ifadeler YASAK!
- Emoji kullanabilirsin: 🚀, 💡, ⚠️
- Frontend/Backend/DevOps terminolojisi doğal kullan
"""
            blog_structure = """
## YAZI YAPISI:
1. **BAŞLIK + Frontmatter Tags** (ai, python, machinelearning, tutorial)
2. **Problem & Ne Yapıyoruz?** — 2-3 kısa paragraf + preview screenshot/GIF
3. **Gereksinimler (Prerequisites)** — Bullet list: Node 20+, Python 3.11, Docker vb.
4. **Adım Adım Uygulama** — H2/H3 ile bölünmüş, her adımda çalışan kod bloğu
5. **Dikkat! Yaygın Hatalar** — Gotchas, edge cases, troubleshooting
6. **Sonuç + GitHub Repo + İleri Okuma** — Working repo link, tartışma sorusu
"""
        elif "linkedin" in target_platform.lower():
            blog_tone_guide = """
**LINKEDIN ARTICLE TONU (KESİN UYULACAK):**
- İş dünyasına yönelik, kurumsal, ilham verici, stratejik içgörü sunan C-Level dili
- 1. tekil şahıs profesyonel: "CTO'lara danışmanlık sürecimde...", "Geçen çeyrekte gözlemlediğimiz..."
- 1-2 cümlelik KISA paragraflar (mobil uyumlu)
- ROI, verimlilik, maliyet analizi gibi iş metrikleri kullan
- Sonda sektörel tartışma sorusu: "Siz şirketinizde bu dönüşümü nasıl yönetiyorsunuz?"
- KESİNLİKLE akademik dilden uzak dur!
"""
            blog_structure = """
## YAZI YAPISI:
1. **Çarpıcı Başlık** (problem/trend odaklı: "Kurumsal YZ Projelerinin %70'i Neden Başarısız Oluyor?")
2. **Banner Görseli** — 1920x1080 profesyonel görsel
3. **Hook (3 Saniye Kuralı)** — Kontrast veri, çarpıcı istatistik veya kısa anekdot
4. **Değer Vaadi** — "Bu yazıda X, Y, Z öğreneceksiniz"
5. **3-5 Ana Sütun** — Kısa paragraflar, bol bullet point, bold lead-in
6. **Yönetici Özeti (Key Takeaway)** — Eyleme dönüştürülebilir tavsiyeler
7. **CTA (Call to Action)** — Etkileşim sorusu + bağlantı teklifi
"""
        else:  # Medium / TDS
            blog_tone_guide = """
**MEDIUM / TOWARDS DATA SCIENCE YAZI TONU (KESİN VE TAVİZSİZ UYULACAK KURALLAR):**
1. **BİRİNCİ AĞIZDAN ANLATIM (1. Tekil/Çoğul Şahıs):**
   - "Ben bu mimariyi kurgularken şunu fark ettim...", "Birlikte adım adım inşa edelim...", "Benim sahada en sık karşılaştığım sorun..."
   - Kesinlikle "edilmiştir", "gözlemlenmiştir", "analiz edilmiştir" gibi mesafeli/soğuk akademik dil KULLANMA!
2. **KULLANICIYI ASLA YORMAYAN AKICI BİR DİL:**
   - 2-3 cümlelik ferah paragraflar. Okuyucuyu boğan devasa blok paragraflar YASAK!
   - Samimi, öğretici, heyecan verici ve sohbet havasında bir üslup (Storytelling).
   - "Kahvenizi alın, başlayalım", "Peki işler nerede tıkanıyor?", "Gelin somut bir örnekle görelim" gibi akıcı geçişler.
3. **METİN İÇİNDE ASLA KAYNAK/ATIF BELİRTME (ÇOK ÖNEMLİ):**
   - Metin içinde KESİNLİKLE `[1]`, `[2]`, `[3]` gibi köşeli parantezli atıflar KULLANILMAYACAK!
   - Metin içinde `(Demir, 2024)` veya `(Yılmaz vd., 2023)` gibi parantezli akademik kaynaklar KULLANILMAYACAK!
   - Okuyucunun dikkatini dağıtacak hiçbir kaynak işareti metne konulmayacak.
4. **KAYNAKLAR SADECE VE SADECE EN SONDA YER ALACAK:**
   - Yazının en sonunda `## Kaynaklar ve İleri Okuma (References & Further Reading)` başlığı altında toplanacak.
   - Burada araştırmadaki gerçek kaynaklar tam linkleriyle listelenecek.
"""
            blog_structure = """
## YAZI PLANI VE AKIŞI:
1. **Başlık + Merak Uyandıran Alt Başlık (Subtitle)**: Okuyucuyu hemen yakalayan başlık.
2. **Hero Görseli**: Hemen başta konuyu özetleyen görsel şema.
3. **TL;DR (30 Saniyede Özet)**:
   > ⏱️ **TL;DR:** [3-4 vurucu maddede bu yazıdan ne öğreneceksiniz?]
4. **Kişisel Giriş & Sorunun Özü**: Neden eski yaklaşımlar can sıkıcı? Birinci ağızdan deneyim.
5. **Teknik Mimari & Diyagramlar**:
   - Mutlaka `![Şekil 1: Başlık](URL)` formatıyla görselleri ekle.
   - Görselden önce tanıt, görselden sonra "Şekil 1'de gördüğünüz gibi..." diyerek analiz et.
6. **Adım Adım Çözüm & Çalışan Kod Blokları**: Python/Bash kodları (` ```python ... ``` `).
7. **Pro Tips & Common Pitfalls**:
   > 💡 **Pro Tip:** [Uygulamada hayat kurtaran ipucu]
   > ⚠️ **Common Pitfall:** [Sık yapılan kritik hata ve çözümü]
8. **Karşılaştırma Tablosu**: Markdown tablosu.
9. **Kapanış ve Düşünceler**: Gelecek vizyonu ve okuyucuya soru ("Sizce de öyle değil mi? Yorumlarda buluşalım").
10. **## Kaynaklar ve İleri Okuma (References & Further Reading)**:
    - Metin içinde kaynak numarası YAZILMAYACAK, tüm kaynaklar SADECE burada listelenecek:
    - `1. Yazar Adı (Yıl). "Makale Başlığı" — URL/DOI`
"""

        # Blog kaynak kullanım kuralı
        blog_citation_guide = """
## ⚠️ KRİTİK KURAL — METİN İÇİ ATIF YASAKTIR:
- Metin gövdesinde ASLA `[1]`, `[2]`, `(Smith, 2023)` gibi atıflar KULLANILMAZ!
- Metin akıcı ve pürüzsüz bir hikaye şeklinde okunmalıdır.
- Tüm kaynaklar YALNIZCA yazının en sonundaki `## Kaynaklar ve İleri Okuma` bölümünde listelenecektir!
"""

        if revision_count > 0 and previous_draft and review:
            prompt = f"""Sen {target_platform} platformunda on binlerce okuyucuya sahip Kıdemli Teknik İçerik Yazarısın.
Editör taslağını inceledi ve şu revizyon taleplerini iletti:
{review}

{blog_tone_guide}

{KNOWLEDGE_DEPTH_GUIDE}

{ANTI_PLAGIARISM_GUIDE}

## REVİZYON TALİMATLARI:
1. Mevcut taslağı editör direktifleri doğrultusunda genişlet ve zenginleştir.
2. {target_words_instruction}
3. Görsel-metin bağlantısını güçlendir: her görselden önce tanıtım, sonra analiz paragrafı yaz.
{blog_citation_guide}

## Konu: {task}
{scope_prompt_text}

## Kullanılacak Gerçek Diyagramlar:
{images_prompt_text}

## Araştırma Dosyası ve Kaynaklar:
{research_data}

## Önceki Taslak:
{previous_draft}

Lütfen güncellenmiş blog yazısını tam Markdown formatında yaz:
"""
        else:
            prompt = f"""Sen {target_platform} platformunda on binlerce mühendis ve lider tarafından takip edilen Kıdemli Teknoloji Başyazarısın.
Sana verilen araştırma verileri ve mimari şemaları kullanarak, platformun ruhuna birebir uyan profesyonel bir TEKNİK BLOG YAZISI yazacaksın.

{blog_tone_guide}

{KNOWLEDGE_DEPTH_GUIDE}

{ANTI_PLAGIARISM_GUIDE}

## HEDEF PLATFORM KURALLARI (ZORUNLU):
{platform_rules}

- {target_words_instruction}
- KESİNLİKLE AĞIR IMRAD AKADEMİK MAKALESİ YAZMA! Blog formatı kullan.

{blog_structure}

{blog_citation_guide}

## GÖRSELLER VE ENTEGRASYON:
{images_prompt_text}

## BAŞLIK:
{title_block}

## Araştırma Dosyası ve Kaynaklar:
{research_data}

Lütfen şimdi bu birinci sınıf blog yazısını Markdown formatında yaz:
"""

    # =========================================================================
    # 2. KATEGORİ: AKADEMİK VE HAKEMLİ YAYIN PLATFORMLARI
    # =========================================================================
    else:
        if revision_count > 0 and previous_draft and review:
            prev_words = len(previous_draft.split())
            prompt = f"""Sen uluslararası saygın indeksli (TR Dizin, Scopus, WoS) akademik dergiler için {paper_type} kaleme alan Profesör ve Baş Yazarsın.
Hakem Heyeti taslağı inceledi ve REVİZYON kararı verdi:
{review}

{CITATION_DISTRIBUTION_GUIDE}

{KNOWLEDGE_DEPTH_GUIDE}

{ANTI_PLAGIARISM_GUIDE}

## TEMEL REVİZYON TALİMATLARI:
1. Taslağı ASLA KISALTMA VEYA ÖZETLEME.
2. {target_words_instruction}
3. DİL TONU: Kesinlikle resmi, mesafeli, 3. tekil şahıs veya edilgen çatı ("yapılmıştır", "analiz edilmiştir").
4. ATIFLAR: Yukarıdaki kaynak dağılımı tablosuna KESİN UY! Bulgular bölümüne kaynak serpiştirme!
5. GÖRSELLER: Her görsel öncesinde tanıtım, sonrasında analiz paragrafı yaz.
6. TARİHSEL DERİNLİK VE TEORİSYENLER: Konunun tarihsel evrimini (öncüler, yıllar, dönüm noktaları) detaylı aktar!

## Konu: {task} {scope_prompt_text}

## Gerçek Şemalar:
{images_prompt_text}

## Doğrulanmış Kaynakça Havuzu:
{research_data}

## Önceki Taslak ({prev_words} kelime):
{previous_draft}

Lütfen şimdi makaleyi hakem talepleri doğrultusunda UZATARAK ve kaynak dağılımını düzelterek tam metin olarak yaz:
"""
        else:
            prompt = f"""Sen uluslararası saygın hakemli bilimsel dergiler (TÜBİTAK DergiPark TR Dizin, IEEE, Elsevier, Springer) standardında {paper_type} kaleme alan Profesör ve Baş Yazarsın.
Sana verilen araştırma verilerini, doğrulanmış kaynakça havuzunu ve şemaları kullanarak, seçilen platformun ({target_platform}) editoryal kriterlerine birebir uyan, tam teşekküllü bir BİLİMSEL DERGİ MAKALESİ yazacaksın.

## HEDEF YAYIN PLATFORMU VE ŞABLON KURALLARI (KESİN UYULACAK):
{platform_rules}

- {target_words_instruction}

## YAZI DİLİ VE ANLATIM TONU (ZORUNLU KURAL):
- Kesinlikle resmi, mesafeli, 3. tekil şahıs veya edilgen çatı ("veriler toplanmıştır", "yöntem modellenmiştir", "bulgular tartışılmıştır").
- Asla 1. tekil ("yaptım", "inceledim") veya samimi konuşma dili KULLANILMAYACAKTIR!

{CITATION_DISTRIBUTION_GUIDE}

{KNOWLEDGE_DEPTH_GUIDE}

{ANTI_PLAGIARISM_GUIDE}

## ATIF SİSTEMİ (ZORUNLU KURAL):
- Metin içi atıflar `[1]`, `[2]`, `[3]` formatında.
- KAYNAK DAĞILIMI TABLOSUNA KESİN UY:
  * Giriş ve Literatür bölümlerinde YOĞUN atıf
  * Bulgular bölümünde SIFIR dış kaynak (sadece kendi verileriniz!)
  * Tartışmada KARŞILAŞTIRMALI atıf
  * Sonuçta MİNİMUM atıf
- Sondaki KAYNAKÇA'daki her madde gerçek DOI veya DergiPark/arXiv linki içerecektir.

-------------------------------------------------------------
### KESİN AKADEMİK MAKALE BÖLÜM PLANI:

1. **BAŞLIK VE KÜNYE**:
   {title_block}
   - `*[Academic English Translation of the Title]*`
   - **Yazar(lar):** Prof. Dr. Akademik Heyet | **Kurum:** Bağımsız Akademik Araştırmalar Konsorsiyumu | **Kabul:** 2026

2. **ÖZETLER** (Kaynak: ❌ SIFIR):
   - **ÖZET (Türkçe)**: 250-300 kelime, yapılandırılmış + 5-7 Anahtar Kelime + JEL Kodları.
   - **ABSTRACT (English)**: 250-300 words + Keywords.

3. **## 1. GİRİŞ VE PROBLEM DURUMU** (Kaynak: 🟢 YÜKSEK):
   - 1.1 Kuramsal Zemin ve Kavramsal Çerçeve.
   - 1.2 Literatürdeki Boşluk ve Araştırmanın Özgün Değeri.
   - 1.3 Amaç, Kapsam ve Araştırma Soruları.
   - ÖNEMLİ: Tüm savlar `[1]`, `[2]` ile atıflı!

4. **## 2. KAVRAMSAL ÇERÇEVE, TARİHÇE VE LİTERATÜR TARAMASI** (Kaynak: 🟢🟢 EN YÜKSEK):
   - 2.1 Tarihsel Evrim, Kurucu Bilim İnsanları ve Kilometre Taşları (Yıllar, buluşlar ve teorik kırılmalar).
   - Özel Kutu: `> 📜 **TARİHSEL KİLOMETRE TAŞI:** [Yıl, öncü kuramcı ve paradigma değişimi]`
   - 2.2 Uluslararası Literatür Analizi ve Öncü Modeller.
   - 2.3 Güncel Tartışmalar ve Teorik Açmazlar.
   - Her paragrafta birden fazla kaynak atfı!

5. **## 3. METODOLOJİ VE TEKNİK MİMARİ** (Kaynak: 🟡 SEÇİCİ):
   - 3.1 Araştırma Deseni ve Analitik Model.
   - 3.2 Veri Seti, Örneklem ve Değişkenler.
   - 3.3 Algoritmik Süreçler ve Sistem Mimarisi.
   - Sadece bilinen araç/algoritma/veri setine atıf, kendi yönteminize ATIF YAPMA!
   {images_prompt_text}

6. **## 4. BULGULAR VE KARŞILAŞTIRMALI ANALİZ** (Kaynak: ❌ SIFIR dış kaynak!):
   - 4.1 Ampirik Bulgular ve İstatistiksel Analiz.
   - 4.2 Model Başarımı ve Kıyaslamalı Değerlendirme.
   - EN AZ 3 DETAYLI KARŞILAŞTIRMA TABLOSU.
   - ⚠️ BU BÖLÜMDE DIŞ KAYNAK KULLANMA! Sadece kendi bulgularını sun!

7. **## 5. TARTIŞMA VE ETİK BOYUTLAR** (Kaynak: 🟡 KARŞILAŞTIRMALI):
   - 5.1 Bulguların Önceki Çalışmalarla Karşılaştırması — "[14] ile tutarlıdır" veya "[15]'in aksine..."
   - 5.2 Etik İkilemler (AI Act, KVKK/GDPR).
   - 5.3 Sınırlılıklar.

8. **## 6. SONUÇ VE ÖNERİLER** (Kaynak: ❌ MİNİMUM):
   - 6.1 Genel Değerlendirme ve Sentez.
   - 6.2 Stratejik Eylem Planı.
   - 6.3 Gelecek Araştırma Ufukları.
   - Yeni atıf ekleme, sadece çalışmanın katkılarını özetle!

9. **## KAYNAKÇA VE BİBLİYOGRAFYA** (ZORUNLU DOĞRULANMIŞ DOI VE ARXIV/DERGİPARK LİNKLERİ):
   - Her bir kaynak için KESİN VE TEK FORMAT:
     `[1] Soyadı, A. (Yıl). "Başlık". Dergi/Yayıncı Adı, Cilt(Sayı), Sayfa. DOI: https://doi.org/...`
     veya
     `[2] Soyadı, A. (Yıl). "Başlık". arXiv Preprint. Erişim: https://arxiv.org/abs/...`
   - ⚠️ KESİN KURAL: ASLA `[. Erişim: [url](url)]` şeklinde iç içe, köşeli parantezli veya bozuk markdown linki YAZMA!
   - Linki doğrudan temiz ve saf bir HTTPS URL'si olarak yaz: `DOI: https://...` veya `Erişim: https://...`
   - Her kaynağın linki mutlaka çalışır durumda olmalıdır!

## Doğrulanmış Kaynakça Havuzu ve Literatür Verisi:
{research_data}

Lütfen bu akademik makaleyi eksiksiz, kaynak dağılımı kurallarına uygun, her görselde metin bağlantısı kurulu, tam metin Markdown formatında yaz:
"""

    import time
    draft = ""
    for attempt in range(3):
        try:
            response = llm.invoke(prompt)
            draft = extract_text(response)
            if draft and len(draft.strip()) > 50:
                break
        except Exception as e:
            if attempt == 2:
                raise e
            time.sleep(2 * (attempt + 1))

    words = len(draft.split())
    img_count = len(re.findall(r"!\[.*?\]\(.*?\)", draft))
    table_count = draft.count("|---")

    logs = state.get("logs", [])
    if revision_count > 0:
        logs.append(f"[Writer] Revizyon #{revision_count} tamamlandı: Metin zenginleştirildi ({words} kelime, {img_count} görsel, {table_count} tablo).")
    else:
        mode_label = f"Teknik Blog ({target_platform})" if is_blog else f"Akademik Makale ({target_platform}, {target_pages})"
        logs.append(f"[Writer] {mode_label} taslağı üretildi ({words} kelime, {img_count} görsel, {table_count} tablo). Kaynak dağılımı: Giriş/Literatür=YÜKSEK, Bulgular=SIFIR")

    return {
        "draft": draft,
        "logs": logs,
    }
