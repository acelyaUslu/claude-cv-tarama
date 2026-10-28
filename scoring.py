"""Şeffaf puanlama: puanı Claude değil, bu formül hesaplar.

- Zorunlu kriter ağırlığı 3, tercih edilen kriter ağırlığı 1
- evet = 1, kısmen = 0.5, hayır = 0
- Kanıtı CV'de bulunamayan "evet/kısmen" kararlarının katkısı yarıya düşer ve uyarı eklenir;
  zorunlu bir kriterde kanıt doğrulanamazsa o kriter karşılanmamış sayılır
- Puan 0-100 arasıdır; karşılanmayan zorunlu kriterler ayrıca listelenir
"""

from __future__ import annotations

from .models import AdayDegerlendirme, Ilan
from .text_utils import kanit_cv_de_var_mi

AGIRLIK = {"zorunlu": 3.0, "tercih": 1.0}
DEGER = {"evet": 1.0, "kismen": 0.5, "hayir": 0.0}


def puanla(aday: AdayDegerlendirme, ilan: Ilan, cv_metni: str) -> AdayDegerlendirme:
    sonuc_map = {s.kriter_id: s for s in aday.sonuclar}
    toplam = kazanilan = 0.0
    aday.zorunlu_eksik, aday.uyarilar = [], []

    for kriter in ilan.kriterler:
        agirlik = AGIRLIK[kriter.tur]
        toplam += agirlik
        s = sonuc_map.get(kriter.id)
        if s is None:
            aday.uyarilar.append(f"'{kriter.ad}' kriteri değerlendirilmemiş.")
            if kriter.tur == "zorunlu":
                aday.zorunlu_eksik.append(kriter.ad)
            continue

        deger = DEGER[s.durum]
        if s.durum != "hayir":
            s.kanit_dogrulandi = kanit_cv_de_var_mi(s.kanit, cv_metni)
            if not s.kanit_dogrulandi:
                deger /= 2
                aday.uyarilar.append(f"'{kriter.ad}' için gösterilen kanıt CV'de bulunamadı; puan yarıya indirildi.")
                if kriter.tur == "zorunlu":
                    aday.zorunlu_eksik.append(f"{kriter.ad} (kanıt doğrulanamadı)")
        if kriter.tur == "zorunlu" and s.durum == "hayir":
            aday.zorunlu_eksik.append(kriter.ad)
        kazanilan += agirlik * deger

    aday.puan = round(100 * kazanilan / toplam, 1) if toplam else 0.0
    return aday


def sirala(adaylar: list[AdayDegerlendirme]) -> list[AdayDegerlendirme]:
    """Önce zorunlu kriterlerin tamamını karşılayanlar, sonra puana göre."""
    return sorted(adaylar, key=lambda a: (len(a.zorunlu_eksik) > 0, -a.puan))
