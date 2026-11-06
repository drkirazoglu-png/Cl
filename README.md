# Dialogbrain

Claude API ile çalışan, konuşma geçmişini hatırlayan bir WhatsApp sohbet botu (Python).

- **WhatsApp Cloud API** (Meta) webhook'u üzerinden mesaj alır ve cevap gönderir
- **Claude** (`claude-opus-5-5`) ile cevap üretir
- Her telefon numarasının konuşma geçmişini **SQLite**'ta saklar ve her mesajda Claude'a geri gönderir
- Güvenlik sınıflandırıcısı bir isteği reddederse, sunucu tarafındaki yedek model devralır (`fallbacks: "default"`)
- Prompt önbelleği açık: uzun konuşmalarda geçmiş, önbellekten ucuza okunur
- Komutlar: `/sıfırla` (geçmişi siler), `/yardım`

## Kurulum

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # değerleri doldurun (bot .env dosyasını kendisi okur)
uvicorn dialogbrain.app:app --host 0.0.0.0 --port 8000
```

## WhatsApp tarafı

1. [Meta for Developers](https://developers.facebook.com/) üzerinde bir uygulama oluşturun ve **WhatsApp** ürününü ekleyin.
2. *WhatsApp → API Setup* sayfasından **Access Token** ve **Phone Number ID** değerlerini `.env` dosyasına yazın.
   Geçici token 24 saatte sona erer. Kalıcı kullanım için bir System User token'ı oluşturun.
3. Sunucuyu internete açın (geliştirme için ör. `ngrok http 8000`).
4. *WhatsApp → Configuration → Webhook* kısmında:
   - Callback URL: `https://<adresiniz>/webhook`
   - Verify token: `.env` içindeki `WHATSAPP_VERIFY_TOKEN`
   - `messages` alanına abone olun.
5. `WHATSAPP_APP_SECRET` değerini girerseniz gelen istekler imzayla doğrulanır (önerilir).

## Ayarlar

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `ANTHROPIC_API_KEY` | – | Claude API anahtarı |
| `WHATSAPP_TOKEN` | – | WhatsApp Cloud API erişim token'ı |
| `WHATSAPP_PHONE_NUMBER_ID` | – | Gönderici numaranın ID'si |
| `WHATSAPP_VERIFY_TOKEN` | – | Webhook doğrulama kelimesi |
| `WHATSAPP_APP_SECRET` | boş | Webhook imza doğrulaması |
| `CLAUDE_MODEL` | `claude-opus-5-5` | Kullanılacak model |
| `CLAUDE_EFFORT` | `low` | Düşünme derinliği (`low`…`max`). Sohbet için `low` hızlı ve ucuz |
| `DIALOGBRAIN_DB` | `dialogbrain.db` | SQLite dosyası |
| `SYSTEM_PROMPT` | Türkçe asistan | Botun kişiliği ve talimatları |

## Yapı

```
dialogbrain/
  app.py       FastAPI webhook sunucusu
  brain.py     Claude API çağrısı ve konuşma mantığı
  memory.py    SQLite konuşma hafızası
  whatsapp.py  WhatsApp Cloud API istemcisi
  config.py    Ortam değişkenleri
tests/         pytest testleri
```

## Testler

```bash
pip install pytest
python -m pytest -q
```

## Notlar

- Geçmiş yalnızca sona eklenerek (append-only) tutulur, Claude'un cevap blokları değiştirilmeden saklanır.
  Bu sayede hem önbellek isabet eder hem de modelin düşünme blokları geçerli kalır. Geçmişi elle düzenlemeyin,
  gerekirse `/sıfırla` kullanın.
- Şimdilik yalnızca metin mesajları işlenir. Fotoğraf, ses ve benzeri mesajlara bilgilendirme cevabı gönderilir.
- WhatsApp kuralı: kullanıcı son 24 saat içinde size yazmadıysa serbest metin gönderemezsiniz (template gerekir).
  Bot yalnızca gelen mesajlara cevap verdiği için bu sorun yaratmaz.
