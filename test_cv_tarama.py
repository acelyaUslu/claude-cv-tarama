from types import SimpleNamespace

from cv_tarama.analyzer import DEGERLENDIRME_ARACI, KRITER_ARACI, CVAnalyzer
from cv_tarama.export import to_csv
from cv_tarama.models import AdayDegerlendirme, Ilan, Kriter
from cv_tarama.scoring import puanla, sirala
from cv_tarama.text_utils import kanit_cv_de_var_mi, mask_personal_data

ILAN = Ilan(
    pozisyon="Veri Analisti",
    kriterler=[Kriter("k1", "Python", "zorunlu"), Kriter("k2", "SQL", "zorunlu"), Kriter("k3", "Tableau", "tercih")],
)
CV = "Python ve pandas ile satış raporları hazırladım.\nSQL sorguları yazdım.\nBeceriler: Excel"


def aday(*sonuclar):
    return AdayDegerlendirme.from_dict(
        "cv.txt",
        {"aday_ozeti": "", "deneyim_yili": 1,
         "degerlendirmeler": [{"kriter_id": k, "durum": d, "kanit": kn, "yorum": ""} for k, d, kn in sonuclar]},
    )


# --- Maskeleme ---
def test_maskeleme():
    metin = "ali@ornek.com | 0532 111 22 33 | +90 541 222 33 44 | 12345678901 | linkedin.com/in/ali"
    m = mask_personal_data(metin)
    for gizli in ("ali@ornek.com", "0532", "541 222", "12345678901", "linkedin.com/in/ali"):
        assert gizli not in m
    assert m.count("[TELEFON]") == 2


# --- Kanıt doğrulama ---
def test_kanit_birebir_ve_kucuk_farklarla_bulunur():
    assert kanit_cv_de_var_mi("Python ve pandas ile satış raporları hazırladım.", CV)
    assert kanit_cv_de_var_mi("python ve pandas ile satış raporları hazırladım", CV)


def test_uydurma_kanit_yakalanir():
    assert not kanit_cv_de_var_mi("MySQL ile veritabanı yönetimi yaptım ve 5 yıl çalıştım", CV)
    assert not kanit_cv_de_var_mi("", CV)


# --- Puanlama ---
def test_tam_puan():
    a = puanla(aday(("k1", "evet", "Python ve pandas ile"), ("k2", "evet", "SQL sorguları yazdım"),
                    ("k3", "evet", "Excel")), ILAN, CV)
    assert a.puan == 100 and not a.zorunlu_eksik and not a.uyarilar


def test_zorunlu_eksik_listelenir():
    a = puanla(aday(("k1", "evet", "Python ve pandas ile"), ("k2", "hayir", ""), ("k3", "hayir", "")), ILAN, CV)
    assert a.zorunlu_eksik == ["SQL"]
    assert a.puan == round(100 * 3 / 7, 1)


def test_uydurma_kanit_puan_dusurur_ve_zorunluyu_eksik_sayar():
    a = puanla(aday(("k1", "evet", "Python ve pandas ile"), ("k2", "evet", "PostgreSQL yöneticisiyim"),
                    ("k3", "hayir", "")), ILAN, CV)
    assert a.puan == round(100 * (3 + 1.5) / 7, 1)
    assert any("kanıt doğrulanamadı" in z for z in a.zorunlu_eksik)
    assert a.uyarilar


def test_degerlendirilmeyen_kriter():
    a = puanla(aday(("k1", "evet", "Python ve pandas ile")), ILAN, CV)
    assert "SQL" in a.zorunlu_eksik and len(a.uyarilar) == 2


def test_siralama_zorunlu_tamam_olanlar_once():
    yuksek_ama_eksik = AdayDegerlendirme("a", "", 0, [], puan=90, zorunlu_eksik=["SQL"])
    dusuk_ama_tam = AdayDegerlendirme("b", "", 0, [], puan=60)
    assert [x.dosya for x in sirala([yuksek_ama_eksik, dusuk_ama_tam])] == ["b", "a"]


def test_csv_excel_uyumlu():
    a = puanla(aday(("k1", "evet", "Python ve pandas ile")), ILAN, CV)
    csv = to_csv([a], ILAN)
    assert csv.startswith("﻿") and "Python" in csv and ";" in csv


# --- Claude akışı (sahte istemci) ---
class FakeClient:
    def __init__(self):
        self.cagrilar = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.cagrilar.append(kw)
        ad = kw["tools"][0]["name"]
        if ad == KRITER_ARACI["name"]:
            girdi = {"pozisyon": "Veri Analisti", "kriterler": [k.__dict__ for k in ILAN.kriterler]}
        else:
            girdi = {"aday_ozeti": "x", "deneyim_yili": 1, "guclu_yonler": [], "eksikler": [], "mulakat_sorulari": [],
                     "degerlendirmeler": [{"kriter_id": "k1", "durum": "evet", "kanit": "Python ve pandas ile", "yorum": ""},
                                          {"kriter_id": "k2", "durum": "evet", "kanit": "SQL sorguları yazdım", "yorum": ""},
                                          {"kriter_id": "k3", "durum": "hayir", "kanit": "", "yorum": ""}]}
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", name=ad, input=girdi)])


def test_uctan_uca_akis_ve_maskeleme():
    client = FakeClient()
    an = CVAnalyzer(client=client, model="test")
    ilan = an.kriterleri_cikar("ilan metni")
    sonuc = an.tara(ilan, {"cv1.txt": CV + "\nmail: ali@ornek.com"})
    assert len(sonuc) == 1 and sonuc[0].puan == round(100 * 6 / 7, 1)
    degerlendirme_cagrisi = client.cagrilar[1]
    assert degerlendirme_cagrisi["tool_choice"]["name"] == DEGERLENDIRME_ARACI["name"]
    assert "ali@ornek.com" not in degerlendirme_cagrisi["messages"][0]["content"]
