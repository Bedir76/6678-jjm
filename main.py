import logging
import requests
import io
import re
import os
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, 
    MessageHandler, CallbackQueryHandler, ConversationHandler, filters
)

# --- WEB SERVER ---
server = Flask('')
@server.route('/')
def home(): return "Bot Aktif!", 200

def run(): server.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- AYARLAR ---
TOKEN = "8261166451:AAHT4vInOHOCMD9bGa41BA4O2eAlY405HLY"
AD_SOYAD_URL = "https://hukumsuz.de/panel/page/adsoyadil.php"
SULALE_API_URL = "https://hukumsuz.de/api/sulale.php?tc="
TC_GSM_URL = "https://hukumsuz.de/api/gsm.php?tc="

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10)",
    "Cookie": "_ym_uid=1770508134870072739; dogrulama=4f0ade62a0339cc6; PHPSESSID=vbf1aquo66orap8jn264jn598e"
}

AD, SOYAD, IL, SULALE_TC, TC_GSM = range(5)

logging.basicConfig(level=logging.INFO)

# --- FORMATLAYICI ---
def format_person(p, title):
    if not p: return ""
    m_il = p.get('MEMLEKETIL') or p.get('NUFUSIL') or ""
    m_ilce = p.get('MEMLEKETILCE') or ""
    m_koy = p.get('MEMLEKETKOY') or ""
    memleket = f"{m_il} / {m_ilce} / {m_koy}".strip(" / ") or "Bilinmiyor"
    
    a_il = p.get('ADRESIL') or p.get('GUNCELADRES') or ""
    a_ilce = p.get('ADRESILCE') or ""
    yer = f"{a_il} / {a_ilce}".strip(" / ") or memleket
    
    res = f"🌟 **{title}** 🌟\n\n"
    res += f"🆔 **TC:** `{p.get('TC')}`\n👤 **AD SOYAD:** `{p.get('AD')} {p.get('SOYAD')}`\n"
    res += f"📅 **DOĞUM:** `{p.get('DOGUMTARIHI')}`\n📱 **GSM:** `{p.get('GSM', 'YOK')}`\n"
    res += f"👪 **ANNE / BABA:** `{p.get('ANNEADI')} / {p.get('BABAADI')}`\n"
    res += f"🗾 **MEMLEKET:** `{memleket}`\n📍 **YAŞADIĞI YER:** `{yer}`\n"
    res += "━━━━━━━━━━━━━━━"
    return res

# --- SORGULAR ---
async def sulale_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tc = update.message.text.strip()
    await update.message.reply_text("🔍 Sülale dökümü hazırlanıyor, lütfen bekleyin...")
    try:
        res = requests.get(f"{SULALE_API_URL}{tc}", headers=HEADERS, timeout=30).json()
        if res.get("person"):
            # Ekrana ana kişiyi bas
            await update.message.reply_text(format_person(res["person"], "SORGULANAN KİŞİ"), parse_mode="Markdown")
            
            # TXT İçeriği Hazırla
            txt_content = f"--- {tc} SÜLALE DÖKÜMÜ ---\n\n"
            yakinliklar = ["anne", "baba", "kardesler", "cocuklar", "es"]
            
            for yakin in yakinliklar:
                data = res.get(yakin)
                if not data: continue
                txt_content += f"[{yakin.upper()}]\n"
                items = data if isinstance(data, list) else [data]
                for p in items:
                    txt_content += f"TC: {p.get('TC')} | Ad: {p.get('AD')} {p.get('SOYAD')} | Dogum: {p.get('DOGUMTARIHI')} | GSM: {p.get('GSM', 'YOK')}\n"
                txt_content += "-"*30 + "\n"

            # Dosyayı Gönder
            buf = io.BytesIO(txt_content.encode('utf-8'))
            buf.name = f"{tc}_sulale.txt"
            await update.message.reply_document(document=buf, caption="📂 Sülale listesi TXT olarak hazırlandı.")
        else:
            await update.message.reply_text("❌ Kayıt bulunamadı.")
    except:
        await update.message.reply_text("⚠️ Bir hata oluştu.")
    return ConversationHandler.END

async def ad_soyad_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    il = update.message.text.upper()
    payload = {"ad": context.user_data['ad'], "soyad": context.user_data['soyad'], "adresil": "" if il == "YOK" else il}
    try:
        res = requests.post(AD_SOYAD_URL, headers=HEADERS, data=payload, timeout=20)
        # Tablo veya JSON kontrolü
        matches = re.findall(r'<td.*?>(.*?)</td>', res.text)
        if matches:
            for i in range(0, min(len(matches), 12), 6):
                k = matches[i:i+6]
                p = {"TC": k[0], "AD": k[1], "SOYAD": context.user_data['soyad'], "DOGUMTARIHI": k[2], "ANNEADI": k[3], "BABAADI": k[4], "MEMLEKETIL": k[5]}
                await update.message.reply_text(format_person(p, "SONUÇ"), parse_mode="Markdown")
        else:
            data = res.json()
            results = data if isinstance(data, list) else [data]
            for p in results[:5]: await update.message.reply_text(format_person(p, "SONUÇ"), parse_mode="Markdown")
    except: await update.message.reply_text("❌ Kayıt bulunamadı.")
    return ConversationHandler.END

# --- DİĞER HANDLERLAR (SADELEŞTİRİLMİŞ) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kbd = [[InlineKeyboardButton("🔍 Ad Soyad", callback_data='go_ad')], [InlineKeyboardButton("👨‍👩‍👧‍👦 Sülale", callback_data='go_su')], [InlineKeyboardButton("📱 GSM", callback_data='go_gs')]]
    await update.message.reply_text("🚀 **SORGU PANELİ**", reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    return ConversationHandler.END

async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == 'go_ad': 
        await q.edit_message_text("📝 **AD** girin:"); return AD
    if q.data == 'go_su': 
        await q.edit_message_text("👨‍👩‍👧‍👦 **TC** girin:"); return SULALE_TC
    if q.data == 'go_gs': 
        await q.edit_message_text("📱 **TC** girin:"); return TC_GSM

async def ad_al(u, c): c.user_data['ad'] = u.message.text.upper(); await u.message.reply_text("📝 **SOYAD**:"); return SOYAD
async def sy_al(u, c): c.user_data['soyad'] = u.message.text.upper(); await u.message.reply_text("📍 **İL** (Yoksa YOK):"); return IL

# --- MAIN ---
if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(btn)],
        states={
            AD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_al)],
            SOYAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, sy_al)],
            IL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_soyad_sorgula)],
            SULALE_TC: [MessageHandler(filters.TEXT & ~filters.COMMAND, sulale_sorgula)],
            TC_GSM: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: ad_soyad_sorgula(u,c))] # Örnek
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv)
    app.run_polling()

