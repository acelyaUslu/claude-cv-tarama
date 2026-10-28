"""Streamlit arayüzü: streamlit run app.py"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from cv_tarama.analyzer import DEFAULT_MODEL, CVAnalyzer
from cv_tarama.export import to_csv, to_json
from cv_tarama.models import AdayDegerlendirme, Ilan, Kriter
from cv_tarama.scoring import puanla, sirala
from cv_tarama.text_utils import mask_personal_data, read_cv

ORNEK = Path(__file__).parent / "examples"
DURUM = {"evet": "✅ Evet", "kismen": "🟡 Kısmen", "hayir": "❌ Hayır"}

st.set_page_config(page_title="Claude CV Tarama", page_icon="📄", layout="wide")
st.title("📄 Claude ile CV Tarama")
st.caption(
    "İlandan kriterleri çıkarır, CV'leri kriter kriter kanıtla değerlendirir, kanıtları doğrular ve adayları sıralar. "
    "Nihai karar her zaman İK uzmanına aittir."
)

with st.sidebar:
    st.header("Ayarlar")
    api_key = st.text_input("Anthropic API anahtarı", value=os.getenv("ANTHROPIC_API_KEY", ""), type="password")
    model = st.text_input("Model", value=DEFAULT_MODEL)
    st.divider()
    if st.button("Örnek veriyle dene (API gerekmez)", use_container_width=True):
        veri = json.loads((ORNEK / "ornek_sonuc.json").read_text(encoding="utf-8"))
        ilan = Ilan.from_dict(veri["ilan"])
        adaylar = []
        for dosya, d in veri["degerlendirmeler"].items():
            metin = mask_personal_data((ORNEK / "cvler" / dosya).read_text(encoding="utf-8"))
            adaylar.append(puanla(AdayDegerlendirme.from_dict(dosya, d), ilan, metin))
        st.session_state.update(ilan=ilan, adaylar=sirala(adaylar), ilan_metni=(ORNEK / "ilan.txt").read_text(encoding="utf-8"))
    st.caption("🔒 E-posta, telefon, TC kimlik no ve sosyal medya linkleri Claude'a gönderilmeden maskelenir.")


def analyzer() -> CVAnalyzer | None:
    if not api_key:
        st.warning("API anahtarı gir ya da kenar çubuğundan örnek veriyle dene.")
        return None
    import anthropic

    return CVAnalyzer(client=anthropic.Anthropic(api_key=api_key), model=model)


# 1) İlan → kriterler
st.subheader("1. İlan ve kriterler")
ilan_metni = st.text_area("İlan metni", value=st.session_state.get("ilan_metni", ""), height=180)
if st.button("Kriterleri çıkar") and ilan_metni.strip() and (a := analyzer()):
    with st.spinner("Claude ilanı okuyor…"):
        st.session_state["ilan"] = a.kriterleri_cikar(ilan_metni)
        st.session_state.pop("adaylar", None)

ilan: Ilan | None = st.session_state.get("ilan")
if ilan:
    st.markdown(f"**Pozisyon:** {ilan.pozisyon} · Kriterleri düzenleyebilir, ekleyip silebilirsin.")
    df = pd.DataFrame([k.__dict__ for k in ilan.kriterler])
    duzenlenmis = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={"tur": st.column_config.SelectboxColumn("tur", options=["zorunlu", "tercih"], required=True)},
        key="kriter_editor",
    )
    ilan = Ilan(
        pozisyon=ilan.pozisyon,
        kriterler=[Kriter.from_dict(r) for r in duzenlenmis.to_dict("records") if r.get("id") and r.get("ad")],
    )

    # 2) CV'ler
    st.subheader("2. CV'ler")
    dosyalar = st.file_uploader("PDF veya TXT CV'ler", type=["pdf", "txt"], accept_multiple_files=True)
    if st.button("CV'leri değerlendir", type="primary", disabled=not dosyalar) and (a := analyzer()):
        cvler = {f.name: read_cv(f.name, f.getvalue()) for f in dosyalar}
        bos = [ad for ad, metin in cvler.items() if len(metin) < 50]
        for ad in bos:
            st.warning(f"{ad}: metin okunamadı (taranmış görsel PDF olabilir), atlandı.")
            cvler.pop(ad)
        durum = st.status("Değerlendiriliyor…", expanded=True)
        st.session_state["adaylar"] = a.tara(ilan, cvler, on_progress=durum.write)
        durum.update(label="Tamamlandı", state="complete")

# 3) Sonuçlar
adaylar: list[AdayDegerlendirme] | None = st.session_state.get("adaylar")
if ilan and adaylar:
    st.subheader("3. Sıralama")
    tablo = pd.DataFrame(
        [
            {
                "Sıra": i,
                "Aday (dosya)": a.dosya,
                "Puan": a.puan,
                "Deneyim (yıl)": a.deneyim_yili,
                "Zorunlu kriterler": "✅ Tamam" if not a.zorunlu_eksik else "❌ " + ", ".join(a.zorunlu_eksik),
                "Uyarı": len(a.uyarilar),
            }
            for i, a in enumerate(adaylar, 1)
        ]
    )
    st.dataframe(
        tablo,
        hide_index=True,
        use_container_width=True,
        column_config={"Puan": st.column_config.ProgressColumn("Puan", min_value=0, max_value=100, format="%.1f")},
    )

    kriter_adi = {k.id: k for k in ilan.kriterler}
    for i, a in enumerate(adaylar, 1):
        with st.expander(f"{i}. {a.dosya} — {a.puan} puan"):
            st.write(a.aday_ozeti)
            for u in a.uyarilar:
                st.warning(u)
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Kriter": kriter_adi[s.kriter_id].ad if s.kriter_id in kriter_adi else s.kriter_id,
                            "Tür": kriter_adi[s.kriter_id].tur if s.kriter_id in kriter_adi else "-",
                            "Durum": DURUM[s.durum],
                            "CV'den kanıt": s.kanit or "-",
                            "Kanıt doğrulandı": {True: "✅", False: "⚠️ Bulunamadı", None: "-"}[s.kanit_dogrulandi],
                        }
                        for s in a.sonuclar
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
            c1, c2, c3 = st.columns(3)
            c1.markdown("**Güçlü yönler**\n" + "\n".join(f"- {x}" for x in a.guclu_yonler))
            c2.markdown("**Eksikler**\n" + "\n".join(f"- {x}" for x in a.eksikler))
            c3.markdown("**Mülakat soruları**\n" + "\n".join(f"{j}. {x}" for j, x in enumerate(a.mulakat_sorulari, 1)))

    d1, d2 = st.columns(2)
    d1.download_button("Excel için CSV", to_csv(adaylar, ilan), "aday_siralamasi.csv", mime="text/csv")
    d2.download_button("JSON", to_json(adaylar, ilan), "aday_siralamasi.json", mime="application/json")
