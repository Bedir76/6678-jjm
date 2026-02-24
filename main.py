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

# --- WEB SERVER (7/24 Aktif Tutma) ---
server = Flask('')
@server.route('/')
def home(): return "Bot Aktif!", 200

def run():
    port = int(os.environ.get('PORT', 8080))
    server.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- AYARLAR ---
TOKEN = "8261166451:AAHT4vInOHOCMD9bGa41BA4O2eAlY405HLY"
AD_SOYAD_URL = "https://hukumsuz.de/panel/page/adsoyadil.php"
SULALE_API_URL = "https://hukumsuz.de/api/sulale.php?tc="
ADRES_API_URL = "https://hukumsuz.de/api/adres.php?tc="
TC_GSM_URL = "https://hukumsuz.de/api/gsm.php?tc="
GSM_TC_URL = "https://hukumsuz.de/api/gsm.php?gsm="
IP_API_URL = "https://ipinfo.io/{}/json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10)",
    "Cookie": "_ym_uid=1770508134870072739; dogrulama=4f0ade62a0339cc6; PHPSESSID=vbf1aquo66orap8jn264jn598e"
}

# Durumlar (States)
AD, SOYAD, IL, SULALE_TC, ADRES_TC, TC_GSM, GSM_TC, IP_STATE = range(8)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- VERİ FORMATLAMA (Düzeltilmiş) ---
def format_person(p, title):
    if not p: return ""
    res = f"🌟 **{title}** 🌟\n\n"
    res += f"🆔 **TC:** `{p.get('TC', '???')}`\n"
    res += f"👤 **AD SOYAD:** `{p.get('AD', '')} {p.get('SOYAD', '')}`\n"
    
    if p.get('DOGUMTARIHI'): res += f"📅 **DOĞUM:** `{p.get('DOGUMTARIHI')}`\n"
    if p.get('GSM') and p.get('GSM') != "YOK": res += f"📱 **GSM:** `{p.get('GSM')}`\n"
    
    ana = p.get('ANNEADI', '?')
    baba = p.get('BABAADI', '?')
    res += f"👪 **ANNE / BABA:** `{ana} / {baba}`\n"
    
    # Memleket (JSON yapına tam uygun)
    m_il = p.get('MEMLEKETIL', '')
    m_ilce = p.get('MEMLEKETILCE', '')
    memleket = f"{m_il} / {m_ilce}".strip(" /")
    res += f"🗾 **MEMLEKET:** `{memleket if memleket else 'Bilinmiyor'}`\n"
    
    # Yaşadığı Yer (ADRESIL + ADRESILCE)
    a_il = p.get('ADRESIL', p.get('IL', ''))
    a_ilce = p.get('ADRESILCE', p.get('ILCE', ''))
    yer = f"{a_il} / {a_ilce}".strip(" /")
    if not yer: yer = p.get('ADRES', 'Bilinmiyor')
    res += f"📍 **YAŞADIĞI YER:** `{yer}`\n"
    
    res += "━━━━━━━━━━━━━━━"
    return res

# --- KLAVYELER ---
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🔍 Ad Soyad", callback_data='go_ad'), InlineKeyboardButton("👨‍👩‍👧‍👦 Sülale (+TXT)", callback_data='go_su')],
        [InlineKeyboardButton("🏠 Adres Sorgu", callback_data='go_adr'), InlineKeyboardButton("🌐 IP Sorgu", callback_data='go_ip')],
        [InlineKeyboardButton("📱 TC -> GSM", callback_data='go_tgsm'), InlineKeyboardButton("🆔 GSM -> TC", callback_data='go_gtc')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🚀 **SORGU PANELİ AKTİF**\nLütfen bir işlem seçin.\n\n👑 **Kurucu:** @ZEWND"
    if update.message:
        await update.message.reply_text(msg, reply_markup=get_main_menu(), parse_mode="Markdown")
    else:
        await update.callback_query.message.reply_text(msg, reply_markup=get_main_menu(), parse_mode="Markdown")
    return ConversationHandler.END

async def btn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    prompts = {
        'go_ad': ("AD girin:", AD), 'go_su': ("Sülale için TC girin:", SULALE_TC),
        'go_adr': ("Adres için TC girin:", ADRES_TC), 'go_ip': ("IP Adresi girin:", IP_STATE),
        'go_tgsm': ("GSM için TC girin:", TC_GSM), 'go_gtc': ("TC için GSM girin:", GSM_TC)
    }
    
    text, next_state = prompts[q.data]
    await q.edit_message_text(f"📝 **{text}**", parse_mode="Markdown")
    return next_state

# --- SORGULAMA FONKSİYONLARI ---
async def sulale_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tc = update.message.text
    await update.message.reply_text(f"🔍 `{tc}` Sülale hazırlanıyor...")
    try:
        r = requests.get(f"{SULALE_API_URL}{tc}", headers=HEADERS, timeout=25).json()
        if r.get("person"):
            await update.message.reply_text(format_person(r["person"], "SORGULANAN KİŞİ"), parse_mode="Markdown")
            sulale = r.get("sulale", [])
            if sulale:
                out = io.StringIO()
                out.write(f"--- {tc} SULALE LISTESI ---\n\n")
                for m in sulale:
                    out.write(f"TC: {m.get('TC')} | {m.get('AD')} {m.get('SOYAD')} | {m.get('YAKINLIK')}\n")
                bio = io.BytesIO(out.read().encode()); bio.name = f"{tc}_sulale.txt"
                await update.message.reply_document(document=bio, caption="📂 Sülale dosyası.")
        else: await update.message.reply_text("❌ Kayıt yok.")
    except: await update.message.reply_text("⚠️ Hata!")
    return ConversationHandler.END

async def ad_soyad_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    il = update.message.text.upper()
    p_load = {"ad": context.user_data['ad'], "soyad": context.user_data['soyad'], "adresil": "" if il == "YOK" else il}
    try:
        res = requests.post(AD_SOYAD_URL, headers=HEADERS, data=p_load)
        m = re.findall(r'<td.*?>(.*?)</td>', res.text)
        if m:
            for i in range(0, min(len(m), 18), 6):
                k = m[i:i+6]
                p = {"TC": k[0], "AD": k[1], "DOGUMTARIHI": k[2], "ANNEADI": k[3], "GSM": k[4], "ADRES": k[5]}
                await update.message.reply_text(format_person(p, "SONUÇ"), parse_mode="Markdown")
        else: await update.message.reply_text("❌ Kayıt yok.")
    except: await update.message.reply_text("⚠️ Hata.")
    return ConversationHandler.END

async def generic_sorgu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text
    # Hangi state'de olduğumuzu kontrol edip ona göre API seçiyoruz
    # Bu kısım basitlik için tekil API çağrıları içindir
    await update.message.reply_text(f"🔍 `{val}` Sorgulanıyor...")
    # Burada diğer API'lerini (GSM, Adres) aynı mantıkla çağırabilirsin.
    return ConversationHandler.END

# --- MAIN ---
if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(btn_handler, pattern='^go_')],
        states={
            AD: [MessageHandler(filters.TEXT & (~filters.COMMAND), lambda u,c: (c.user_data.update({'ad': u.message.text.upper()}), u.message.reply_text("SOYAD gir:"), SOYAD)[2])],
            SOYAD: [MessageHandler(filters.TEXT & (~filters.COMMAND), lambda u,c: (c.user_data.update({'soyad': u.message.text.upper()}), u.message.reply_text("İL gir (veya YOK):"), IL)[2])],
            IL: [MessageHandler(filters.TEXT & (~filters.COMMAND), ad_soyad_sorgula)],
            SULALE_TC: [MessageHandler(filters.TEXT & (~filters.COMMAND), sulale_sorgula)],
            ADRES_TC: [MessageHandler(filters.TEXT & (~filters.COMMAND), generic_sorgu)],
            TC_GSM: [MessageHandler(filters.TEXT & (~filters.COMMAND), generic_sorgu)],
            GSM_TC: [MessageHandler(filters.TEXT & (~filters.COMMAND), generic_sorgu)],
            IP_STATE: [MessageHandler(filters.TEXT & (~filters.COMMAND), generic_sorgu)],
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv)
    app.run_polling()
