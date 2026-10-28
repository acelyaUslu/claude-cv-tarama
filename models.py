"""Veri modelleri."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Kriter:
    id: str
    ad: str
    tur: str  # "zorunlu" | "tercih"
    aciklama: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Kriter":
        tur = d.get("tur", "tercih")
        return cls(id=str(d["id"]), ad=str(d["ad"]), tur=tur if tur in ("zorunlu", "tercih") else "tercih",
                   aciklama=str(d.get("aciklama", "")))


@dataclass
class Ilan:
    pozisyon: str
    kriterler: list[Kriter]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Ilan":
        return cls(pozisyon=str(d.get("pozisyon", "")), kriterler=[Kriter.from_dict(k) for k in d.get("kriterler", [])])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KriterSonucu:
    kriter_id: str
    durum: str  # "evet" | "kismen" | "hayir"
    kanit: str = ""
    yorum: str = ""
    kanit_dogrulandi: bool | None = None  # Kod tarafından doldurulur

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "KriterSonucu":
        durum = d.get("durum", "hayir")
        return cls(kriter_id=str(d.get("kriter_id", "")), durum=durum if durum in ("evet", "kismen", "hayir") else "hayir",
                   kanit=str(d.get("kanit", "") or ""), yorum=str(d.get("yorum", "") or ""))


@dataclass
class AdayDegerlendirme:
    dosya: str
    aday_ozeti: str
    deneyim_yili: float
    sonuclar: list[KriterSonucu]
    guclu_yonler: list[str] = field(default_factory=list)
    eksikler: list[str] = field(default_factory=list)
    mulakat_sorulari: list[str] = field(default_factory=list)
    # Puanlama sonrası doldurulur
    puan: float = 0.0
    zorunlu_eksik: list[str] = field(default_factory=list)
    uyarilar: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, dosya: str, d: dict[str, Any]) -> "AdayDegerlendirme":
        return cls(
            dosya=dosya,
            aday_ozeti=str(d.get("aday_ozeti", "")),
            deneyim_yili=float(d.get("deneyim_yili", 0) or 0),
            sonuclar=[KriterSonucu.from_dict(s) for s in d.get("degerlendirmeler", [])],
            guclu_yonler=list(d.get("guclu_yonler", [])),
            eksikler=list(d.get("eksikler", [])),
            mulakat_sorulari=list(d.get("mulakat_sorulari", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
