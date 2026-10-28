"""CV metnini okuma, kişisel verileri maskeleme ve kanıt doğrulama."""

from __future__ import annotations

import io
import re
import unicodedata

EPOSTA = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
TELEFON = re.compile(r"(?:\+?90[\s-]?)?\(?0?5\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}")
TC_KIMLIK = re.compile(r"\b[1-9]\d{10}\b")
URL_SOSYAL = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin|instagram|facebook|twitter|x)\.com/\S+", re.I)


def read_cv(dosya_adi: str, veri: bytes) -> str:
    """PDF veya TXT dosyasından düz metin çıkarır."""
    if dosya_adi.lower().endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(veri))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    return veri.decode("utf-8", errors="ignore").strip()


def mask_personal_data(metin: str) -> str:
    """KVKK: Değerlendirme için gerekmeyen iletişim ve kimlik bilgilerini Claude'a göndermeden önce maskeler."""
    metin = EPOSTA.sub("[E-POSTA]", metin)
    metin = URL_SOSYAL.sub("[SOSYAL-MEDYA]", metin)
    metin = TC_KIMLIK.sub("[TC-KIMLIK]", metin)
    metin = TELEFON.sub("[TELEFON]", metin)
    return metin


def _norm(metin: str) -> str:
    metin = unicodedata.normalize("NFKC", metin).casefold()
    metin = re.sub(r"[^\w\s]", " ", metin)
    return re.sub(r"\s+", " ", metin).strip()


def kanit_cv_de_var_mi(kanit: str, cv_metni: str, esik: float = 0.8) -> bool:
    """Claude'un gösterdiği kanıt cümlesi CV'de gerçekten geçiyor mu?

    Önce birebir (normalize edilmiş) eşleşmeye bakar; olmazsa kanıttaki anlamlı
    kelimelerin en az %80'i CV'de geçiyorsa kabul eder.
    """
    k, cv = _norm(kanit), _norm(cv_metni)
    if not k:
        return False
    if k in cv:
        return True
    kelimeler = [w for w in k.split() if len(w) > 2]
    if not kelimeler:
        return False
    cv_kelimeleri = set(cv.split())
    return sum(w in cv_kelimeleri for w in kelimeler) / len(kelimeler) >= esik
