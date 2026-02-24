import logging
import requests
import io
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

def run():
    port = int(os.environ.get('PORT', 8080))
    server.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run); t.daemon = True; t.start()

# --- AYARLAR ---
TOKEN = "8261166451:AAHT4vInOHOCMD9bGa41BA4O2eAlY405HLY"
BASE_URL = "https://hukumsuz.de/api"
AD_SOYAD_URL = "https://hukumsuz.de/panel/page/adsoyadil.php" # Bu bazen farklı dönebilir

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Cookie": "dogrulama=4f0ade62a0339cc6; PHPSESSID=vbf1aquo66orap8jn264jn598e"
}

# Durumlar
AD, SOYAD, IL, SULALE_TC, ADRES_TC, TC_GSM, GSM_TC, IP_STATE = range(8)

logging.basicConfig(level=logging.INFO)

# --- YARDIMCI FONKSİYONLAR ---
def format_data(p):
    """Gelen JSON verisini okunaklı metne dönüştürür."""
    return (
        f"🆔 TC: {p.get('TC', 'Yok')}\n"
        f"👤 İSİM: {p.get('AD', '')} {p.get('SOYAD', '')}\n"
        f"📱 GSM: {p.get('GSM', 'Yok')}\n"
        f"👪 ANA/BABA: {p.get('ANNEADI', '?')} / {p.get('BABAADI', '?')}\n"
        f"📅 DOĞUM: {p.get('DOGUMTARIHI', '')} - {p.get('DOGUMYERI', '')}\n"
        f"🗾 MEMLEKET: {p.get('MEMLEKETIL', '')} / {p.get('MEMLEKETILCE', '')}\n"
        f"📍 ADRES: {p.get('ADRESIL', '')} / {p.get('ADRESILCE', '')}\n"
        f"{'-'*30}\n"
    )

async def send_result(update, text, count):
    """Veri çoksa dosya, azsa mesaj atar."""
    if count > 2:
        bio = io.BytesIO(text.encode('utf-8'))
        bio.name = "sorgu_sonucu.txt"
        await update.message.reply_document(document=bio, caption=f"✅ {count} sonuç bulundu.")
    else:
        await update.message.reply_text(f"🔍 **SONUÇLAR:**\n\n{text}", parse_mode="Markdown")

# --- MENÜLER ---
def main_menu():
    keyboard = [
        [InlineKeyboardButton("🔍 Ad Soyad", callback_data='go_adsoyad'), InlineKeyboardButton("👨‍👩‍👧 Sülale", callback_data='go_sulale')],
        [InlineKeyboardButton("📱 TC -> GSM", callback_data='go_tcgsm'), InlineKeyboardButton("🆔 GSM -> TC", callback_data='go_gsmtc')],
        [InlineKeyboardButton("🏠 Adres (TC)", callback_data='go_adres'), InlineKeyboardButton("🌐 IP Sorgu", callback_data='go_ip')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 **Sorgu Paneli Aktif**", reply_markup=main_menu(), parse_mode="Markdown")
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    prompts = {
        'go_adsoyad': (AD, "📝 **AD** girin:"), 'go_sulale': (SULALE_TC, "🆔 **TC** girin:"),
        'go_tcgsm': (TC_GSM, "📱 **TC** girin:"), 'go_gsmtc': (GSM_TC, "📱 **GSM** (0-sız) girin:"),
        'go_adres': (ADRES_TC, "🏠 **TC** girin:"), 'go_ip': (IP_STATE, "🌐 **IP** girin:")
    }
    state, text = prompts[query.data]
    await query.edit_message_text(text, parse_mode="Markdown")
    return state

# --- SORGULAMA FONKSİYONLARI ---
async def ad_soyad_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    il = update.message.text.upper()
    payload = {"ad": context.user_data['ad'], "soyad": context.user_data['soyad'], "adresil": "" if il == "YOK" else il}
    try:
        res = requests.post(AD_SOYAD_URL, data=payload, headers=HEADERS, timeout=20).json()
        if isinstance(res, list) and len(res) > 0:
            output = "".join([format_data(p) for p in res])
            await send_result(update, output, len(res))
        else: await update.message.reply_text("❌ Kayıt bulunamadı.")
    except: await update.message.reply_text("⚠️ API Hatası (JSON bekleniyordu).")
    return ConversationHandler.END

async def gsm_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text
    url = f"{BASE_URL}/gsm.php?{'tc' if context.user_data.get('type')=='tc' else 'gsm'}={val}"
    try:
        res = requests.get(url, headers=HEADERS).json()
        if res: await update.message.reply_text(f"📱 **Sonuç:**\n`{res}`")
        else: await update.message.reply_text("❌ Kayıt yok.")
    except: await update.message.reply_text("⚠️ Hata.")
    return ConversationHandler.END

# --- DİĞER DURUMLAR ---
async def ad_al(update, context): context.user_data['ad'] = update.message.text.upper(); return SOYAD
async def soyad_al(update, context): context.user_data['soyad'] = update.message.text.upper(); return IL

# --- ANA PROGRAM ---
if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={
            AD: [MessageHandler(filters.TEXT, ad_al)],
            SOYAD: [MessageHandler(filters.TEXT, soyad_al)],
            IL: [MessageHandler(filters.TEXT, ad_soyad_sorgula)],
            TC_GSM: [MessageHandler(filters.TEXT, gsm_sorgula)],
            GSM_TC: [MessageHandler(filters.TEXT, gsm_sorgula)],
            SULALE_TC: [MessageHandler(filters.TEXT, gsm_sorgula)], # Örnek amaçlı
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv)
    app.run_polling()

