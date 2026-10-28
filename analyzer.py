"""Claude API ile ilan analizi ve CV değerlendirme.

Akış:
1. `kriterleri_cikar`: İlan metninden zorunlu / tercih edilen kriterleri çıkarır (tool use).
2. `cv_degerlendir`: Her CV'yi her kriter için evet/kısmen/hayır olarak değerlendirir ve
   her karar için CV'den birebir kanıt cümlesi ister (tool use).
3. Puanı Claude değil `scoring.puanla` hesaplar; kanıtlar kodla CV'de aranır.
4. `tara`: Birden fazla CV'yi paralel değerlendirip sıralar.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .models import AdayDegerlendirme, Ilan
from .scoring import puanla, sirala
from .text_utils import mask_personal_data

DEFAULT_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")

KRITER_ARACI = {
    "name": "ilan_kriterlerini_kaydet",
    "description": "İş ilanından çıkarılan değerlendirme kriterlerini kaydeder.",
    "input_schema": {
        "type": "object",
        "properties": {
            "pozisyon": {"type": "string"},
            "kriterler": {
                "type": "array",
                "minItems": 3,
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Kısa benzersiz kimlik, ör. k1"},
                        "ad": {"type": "string", "description": "Kısa kriter adı, ör. 'Python (2+ yıl)'"},
                        "tur": {"type": "string", "enum": ["zorunlu", "tercih"]},
                        "aciklama": {"type": "string", "description": "Bu kriter nasıl karşılanmış sayılır?"},
                    },
                    "required": ["id", "ad", "tur", "aciklama"],
                },
            },
        },
        "required": ["pozisyon", "kriterler"],
    },
}

DEGERLENDIRME_ARACI = {
    "name": "aday_degerlendirmesini_kaydet",
    "description": "Bir adayın ilan kriterlerine göre değerlendirmesini kaydeder.",
    "input_schema": {
        "type": "object",
        "properties": {
            "aday_ozeti": {"type": "string", "description": "Adayın 2 cümlelik mesleki özeti."},
            "deneyim_yili": {"type": "number", "description": "İlgili alandaki toplam iş deneyimi (yıl)."},
            "degerlendirmeler": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kriter_id": {"type": "string"},
                        "durum": {"type": "string", "enum": ["evet", "kismen", "hayir"]},
                        "kanit": {
                            "type": "string",
                            "description": "CV'den BİREBİR kopyalanmış kısa alıntı. 'hayir' ise boş bırak.",
                        },
                        "yorum": {"type": "string"},
                    },
                    "required": ["kriter_id", "durum", "kanit", "yorum"],
                },
            },
            "guclu_yonler": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
            "eksikler": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
            "mulakat_sorulari": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 3,
                "description": "Eksikleri ve belirsiz noktaları netleştirecek 3 mülakat sorusu.",
            },
        },
        "required": ["aday_ozeti", "deneyim_yili", "degerlendirmeler", "guclu_yonler", "eksikler", "mulakat_sorulari"],
    },
}

KRITER_SISTEM = """Sen deneyimli bir insan kaynakları uzmanısın. İş ilanını okuyup adayları
adil ve ölçülebilir biçimde değerlendirmek için kriterler çıkarırsın.
- İlanda açıkça "aranan / şart / zorunlu" olanlar zorunlu, "tercih sebebi / artı" olanlar tercih olsun.
- Kriterler CV'den doğrulanabilir olsun (beceri, deneyim süresi, eğitim, dil, sertifika).
- Yaş, cinsiyet, medeni durum, askerlik dışı kişisel özellikler, fotoğraf, uyruk, din gibi
  ayrımcılığa yol açabilecek kriterleri ASLA ekleme. Askerlik yalnızca ilanda açıkça yazıyorsa eklenebilir.
- Sonucu `ilan_kriterlerini_kaydet` aracıyla döndür."""

DEGERLENDIRME_SISTEM = """Sen tarafsız bir işe alım değerlendiricisisin.
Kurallar:
- Yalnızca CV'de YAZANLARA dayan. Tahmin yürütme; CV'de yoksa durum "hayir".
- "evet" veya "kismen" dediğin her kriter için `kanit` alanına CV'den BİREBİR kopyaladığın kısa bir alıntı yaz.
  Alıntıyı değiştirme, özetleme veya çevirme.
- Adayın adı, yaşı, cinsiyeti, medeni durumu, fotoğrafı, uyruğu, dini, mezun olduğu okulun prestiji
  değerlendirmeyi ETKİLEMESİN.
- Maskelenmiş alanlar ([E-POSTA], [TELEFON] vb.) normaldir, eksiklik sayma.
- Puan verme; sadece kriter bazında karar ver. Sonucu `aday_degerlendirmesini_kaydet` aracıyla döndür."""


class CVAnalyzer:
    def __init__(self, client: Any | None = None, model: str = DEFAULT_MODEL, paralel: int = 4):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.paralel = paralel

    def _arac_cagir(self, sistem: str, arac: dict[str, Any], icerik: str) -> dict[str, Any]:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=sistem,
            tools=[arac],
            tool_choice={"type": "tool", "name": arac["name"]},
            messages=[{"role": "user", "content": icerik}],
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == arac["name"]:
                return dict(block.input)
        raise RuntimeError("Claude beklenen araç çağrısını döndürmedi.")

    def kriterleri_cikar(self, ilan_metni: str) -> Ilan:
        veri = self._arac_cagir(KRITER_SISTEM, KRITER_ARACI, f"<ilan>\n{ilan_metni}\n</ilan>")
        return Ilan.from_dict(veri)

    def cv_degerlendir(self, ilan: Ilan, dosya: str, cv_metni: str) -> AdayDegerlendirme:
        maskeli = mask_personal_data(cv_metni)
        kriter_listesi = "\n".join(
            f"- {k.id} [{k.tur}] {k.ad}: {k.aciklama}" for k in ilan.kriterler
        )
        icerik = (
            f"Pozisyon: {ilan.pozisyon}\n\nKriterler:\n{kriter_listesi}\n\n"
            f"<cv>\n{maskeli}\n</cv>\n\nHer kriter için tam bir değerlendirme yap."
        )
        veri = self._arac_cagir(DEGERLENDIRME_SISTEM, DEGERLENDIRME_ARACI, icerik)
        aday = AdayDegerlendirme.from_dict(dosya, veri)
        return puanla(aday, ilan, maskeli)

    def tara(
        self,
        ilan: Ilan,
        cvler: dict[str, str],
        on_progress: Callable[[str], None] | None = None,
    ) -> list[AdayDegerlendirme]:
        """cvler: {dosya_adi: cv_metni}. Adayları paralel değerlendirip sıralı döndürür."""
        log = on_progress or (lambda _m: None)
        sonuclar: list[AdayDegerlendirme] = []
        with ThreadPoolExecutor(max_workers=self.paralel) as ex:
            gelecekler = {ex.submit(self.cv_degerlendir, ilan, ad, metin): ad for ad, metin in cvler.items()}
            for fut, ad in gelecekler.items():
                try:
                    sonuclar.append(fut.result())
                    log(f"✓ {ad} değerlendirildi")
                except Exception as e:  # Bir CV'nin hatası diğerlerini durdurmasın
                    log(f"✗ {ad}: {e}")
        return sirala(sonuclar)
