# 📄 Claude ile CV Tarama

İnsan kaynakları ekipleri için, iş ilanına göre CV'leri **kriter kriter, kanıta dayalı** değerlendiren ve adayları sıralayan bir ön eleme aracı.

> Sorun: LLM'lere "bu CV uygun mu, 10 üzerinden puan ver" demek hem açıklanamaz hem de uydurmaya açık bir sonuç verir.
> Bu proje kararı parçalara ayırır: Claude her kriter için **CV'den birebir kanıt** gösterir, kanıt kodla CV'de aranır ve
> puanı Claude değil **şeffaf bir formül** hesaplar. Nihai karar her zaman İK uzmanına aittir.

![Uygulama ekranı](docs/ekran.png)

## Nasıl çalışır?

1. **İlan → kriterler:** Claude ilanı okur ve zorunlu / tercih edilen kriterleri çıkarır. İK uzmanı tabloyu düzenleyebilir.
2. **KVKK maskeleme:** E-posta, telefon, TC kimlik no ve sosyal medya linkleri Claude'a gönderilmeden **maskelenir**.
3. **Kriter bazlı değerlendirme:** Her CV için Claude, her kriteri `evet / kısmen / hayır` olarak işaretler ve CV'den alıntı yapar.
   CV'ler paralel değerlendirilir.
4. **Kanıt doğrulama:** Gösterilen alıntı CV'de gerçekten geçiyor mu, kodla kontrol edilir. Geçmiyorsa:
   - o kriterin puan katkısı yarıya düşer ve uyarı gösterilir,
   - zorunlu bir kriterse aday "zorunlu kriter eksik" olarak işaretlenir.
5. **Şeffaf puan:** Zorunlu kriter ağırlığı 3, tercih edilen 1; evet = 1, kısmen = 0,5, hayır = 0 → 0–100 puan.
   Sıralamada önce zorunlu kriterlerin tamamını karşılayanlar gelir.
6. **Çıktı:** Sıralama tablosu, aday bazlı güçlü yönler / eksikler, adaya özel 3 mülakat sorusu, Excel uyumlu CSV ve JSON.

## Adil değerlendirme

- Claude'a ad, yaş, cinsiyet, medeni durum, fotoğraf, uyruk, din ve okul prestijini **değerlendirmeye katmaması** açıkça söylenir.
- Bu tür bilgiler ilan kriteri olarak da çıkarılmaz.
- Puan modelin "hissi" değil, kanıtlanmış kriterlerden hesaplanır; her karar tabloda kanıtıyla görünür.

## Mimari

```
İlan metni ──► Claude (tool: ilan_kriterlerini_kaydet) ──► Kriter tablosu (İK düzenler)
                                                               │
CV'ler (PDF/TXT) ──► metin çıkarma ──► KVKK maskeleme ──► Claude (tool: aday_degerlendirmesini_kaydet)
                                                               │  (paralel)
                                                               ▼
                                         kanıt doğrulama + şeffaf puanlama ──► sıralama / CSV / JSON
```

| Dosya | Görev |
|---|---|
| `cv_tarama/analyzer.py` | Prompt'lar, araç şemaları, Claude çağrıları, paralel tarama |
| `cv_tarama/text_utils.py` | PDF/TXT okuma, kişisel veri maskeleme, kanıt doğrulama |
| `cv_tarama/scoring.py` | Ağırlıklı puanlama ve sıralama |
| `cv_tarama/export.py` | CSV (Excel uyumlu) ve JSON |
| `app.py` | Streamlit arayüzü |
| `examples/` | Örnek ilan, kurgusal CV'ler ve örnek sonuçlar |

## Kurulum

```bash
git clone https://github.com/acelyaUslu/claude-cv-tarama.git
cd claude-cv-tarama
pip install -r requirements.txt

export ANTHROPIC_API_KEY=...   # Windows: set ANTHROPIC_API_KEY=...
streamlit run app.py
```

API anahtarı olmadan **"Örnek veriyle dene"** butonuyla demo çalışır. Örnek veride bir adayın SQL kanıtı bilerek
uydurma bırakılmıştır; sistemin bunu yakalayıp adayı geri sıraya düşürdüğünü görebilirsin.

### Kod içinden kullanım

```python
from cv_tarama import CVAnalyzer
from cv_tarama.text_utils import read_cv

an = CVAnalyzer()
ilan = an.kriterleri_cikar(open("ilan.txt", encoding="utf-8").read())
cvler = {ad: read_cv(ad, open(ad, "rb").read()) for ad in ["aday1.pdf", "aday2.pdf"]}

for aday in an.tara(ilan, cvler):
    print(aday.dosya, aday.puan, aday.zorunlu_eksik)
```

## Testler

```bash
python -m pytest -q
```

Maskeleme, kanıt doğrulama, puanlama, sıralama ve uçtan uca Claude akışı (sahte istemciyle) test edilir; API anahtarı gerekmez.

## Sınırlar

- Taranmış (görsel) PDF'lerden metin çıkarılamaz; bu CV'ler uyarıyla atlanır.
- Araç bir **ön eleme yardımcısıdır**; işe alım kararını tek başına vermemelidir.
- Gerçek aday verisiyle kullanmadan önce KVKK aydınlatma metni ve açık rıza süreçleri kurum tarafından sağlanmalıdır.

---

Geliştiren: **Açelya Uslu** · Bilgisayar Mühendisliği Yüksek Lisans, Manisa Celal Bayar Üniversitesi
