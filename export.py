"""Sonuçları CSV ve JSON olarak dışa aktarır."""

from __future__ import annotations

import csv
import io
import json

from .models import AdayDegerlendirme, Ilan

DURUM_ISARET = {"evet": "✓", "kismen": "~", "hayir": "✗"}


def to_csv(adaylar: list[AdayDegerlendirme], ilan: Ilan) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Sıra", "Dosya", "Puan", "Deneyim (yıl)", "Zorunlu eksik"] + [k.ad for k in ilan.kriterler] + ["Uyarılar"])
    for i, a in enumerate(adaylar, 1):
        durumlar = {s.kriter_id: DURUM_ISARET[s.durum] for s in a.sonuclar}
        w.writerow(
            [i, a.dosya, a.puan, a.deneyim_yili, ", ".join(a.zorunlu_eksik) or "-"]
            + [durumlar.get(k.id, "?") for k in ilan.kriterler]
            + [" | ".join(a.uyarilar)]
        )
    return "﻿" + buf.getvalue()  # Excel'in Türkçe karakterleri doğru açması için BOM


def to_json(adaylar: list[AdayDegerlendirme], ilan: Ilan) -> str:
    return json.dumps({"ilan": ilan.to_dict(), "adaylar": [a.to_dict() for a in adaylar]}, ensure_ascii=False, indent=2)
