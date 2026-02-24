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

# --- WEB SERVER (RENDER CANLI TUTMA & 200 OK) ---
server = Flask('')

@server.route('/', defaults={'path': ''})
@server.route('/<path:path>')
def catch_all(path):
    # Gelen her türlü isteğe (ping/ziyaret) 200 OK döner
    return "Bot Aktif ve Uyanik!", 200

def run():
    # Render'ın atadığı portu veya varsayılan 8080'i kullanır
    port = int(os.environ.get('PORT', 8080))
    server.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- AYARLAR ---
TOKEN = "8456869490:AAG697NMJTw9aA1YXuPg6clsaslq8wleZuU"
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

# Conversation States
AD, SOYAD, IL, SULALE_TC, ADRES_TC, TC_GSM, GSM_TC, IP_STATE = range(8)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- YARDIMCI FONKSİYONLAR ---
def format_person(p, title):
    if not p: return ""
    res = f"🌟 **{title}** 🌟\n\n"
    if p.get('TC'): res += f"🆔 **TC:** `{p.get('TC')}`\n"
    isim = f"{p.get('AD', '')} {p.get('SOYAD', '')}".strip()
    if isim: res += f"👤 **AD SOYAD:** `{isim}`\n"
    if p.get('DOGUMTARIHI') and p.get('DOGUMTARIHI') != "YOK":
        res += f"📅 **DOĞUM:** `{p.get('DOGUMTARIHI')}`\n"
    if p.get('GSM') and p.get('GSM') != "YOK" and p.get('GSM') != "":
        res += f"📱 **GSM:** `{p.get('GSM')}`\n"
    
    ana = p.get('ANNEADI', '')
    baba = p.get('BABAADI', '')
    if ana or baba:
        res += f"👪 **ANNE / BABA:** `{ana if ana else '?' } / {baba if baba else '?'}`\n"
        
    res += "━━━━━━━━━━━━━━━"
    return res

def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔍 Ad Soyad Sorgu", callback_data='go_adsoyad')],
        [InlineKeyboardButton("👨‍👩‍👧‍👦 Sülale Sorgu (Detaylı)", callback_data='go_sulale')],
        [InlineKeyboardButton("🏠 Adres Sorgu (TC)", callback_data='go_adres')],
        [InlineKeyboardButton("📱 TC -> GSM Sorgu", callback_data='go_tcgsm')],
        [InlineKeyboardButton("🆔 GSM -> TC Sorgu", callback_data='go_gsmtc')],
        [InlineKeyboardButton("🌐 IP Sorgu", callback_data='go_ip')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ana Menüye Dön", callback_data='main_menu')]])

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🚀 **SORGU PANELİ**\n\nLütfen bir işlem seçin.\n\n👑 **Kurucu:** @ZEWND / @y9tknz"
    await update.message.reply_text(msg, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'main_menu':
        await query.edit_message_text("🚀 **ANA MENÜ**\n\n👑 @ZEWND / @y9tknz", reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END
    
    prompts = {
        'go_adsoyad': "📝 **AD** girin:", 'go_sulale': "🆔 Sülale dökümü için **TC** girin:", 
        'go_adres': "🏠 **TC** girin:", 'go_tcgsm': "📱 **TC** girin:", 
        'go_gsmtc': "🆔 **GSM** girin:", 'go_ip': "🌐 **IP ADRESİ** girin:"
    }
    states = {
        'go_adsoyad': AD, 'go_sulale': SULALE_TC, 'go_adres': ADRES_TC,
        'go_tcgsm': TC_GSM, 'go_gsmtc': GSM_TC, 'go_ip': IP_STATE
    }
    await query.edit_message_text(prompts[query.data], parse_mode="Markdown")
    return states[query.data]

# --- SORGULAR ---
async def sulale_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tc = update.message.text
    await update.message.reply_text(f"🔍 `{tc}` için detaylı sülale taranıyor...")
    try:
        res = requests.get(f"{SULALE_API_URL}{tc}", headers=HEADERS, timeout=25).json()
        if res.get("person"):
            await update.message.reply_text(format_person(res["person"], "SORGULANAN KİŞİ"), parse_mode="Markdown")
            txt = f"--- {tc} SÜLALE RAPORU ---\n\n"
            yakinliklar = {"anne": "ANNE", "baba": "BABA", "kardesler": "KARDEŞLER", "cocuklar": "ÇOCUKLAR", "dayi_teyze": "DAYI/TEYZE", "amca_hala": "AMCA/HALA"}
            for key, baslik in yakinliklar.items():
                v = res.get(key)
                if not v: continue
                txt += f"[{baslik}]\n"
                items = v if isinstance(v, list) else [v]
                for p in items:
                    txt += f"👤 {p.get('AD', '')} {p.get('SOYAD', '')} - TC: {p.get('TC', '')} - GSM: {p.get('GSM', 'YOK')}\n"
                txt += "----------------\n"
            buf = io.BytesIO(txt.encode('utf-8'))
            buf.name = f"{tc}_sulale_detay.txt"
            await update.message.reply_document(document=buf, caption="📂 Detaylı sülale raporu hazırlandı.")
        else: await update.message.reply_text("❌ Kayıt bulunamadı.")
    except: await update.message.reply_text("⚠️ API Hatası.")
    return ConversationHandler.END

async def ip_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        res = requests.get(IP_API_URL.format(update.message.text.strip())).json()
        m = f"🌐 **IP SONUCU**\n\n🌍 IP: `{res.get('ip')}`\n📍 Ülke: `{res.get('country')}`\n🏙 Şehir: `{res.get('city')}`\n📡 ISP: `{res.get('org')}`"
        await update.message.reply_text(m, parse_mode="Markdown", reply_markup=get_back_to_menu_button())
    except: await update.message.reply_text("⚠️ Hata.")
    return ConversationHandler.END

async def gsm_tc_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        res = requests.get(f"{GSM_TC_URL}{update.message.text.strip()}", headers=HEADERS).json()
        if res.get("results"):
            m = "✅ **TC BULUNDU**\n\n"
            for r in res["results"]: m += f"📱 GSM: `{r.get('GSM')}`\n🆔 TC: `{r.get('TC')}`\n"
            await update.message.reply_text(m, parse_mode="Markdown", reply_markup=get_back_to_menu_button())
        else: await update.message.reply_text("❌ Kayıt yok.")
    except: await update.message.reply_text("⚠️ Hata.")
    return ConversationHandler.END

async def ad_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ad'] = update.message.text.upper()
    await update.message.reply_text("📝 **SOYAD** girin:")
    return SOYAD

async def soyad_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['soyad'] = update.message.text.upper()
    await update.message.reply_text("📍 **İL** (Yoksa YOK yaz):")
    return IL

async def ad_soyad_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    il = update.message.text.upper()
    payload = {"ad": context.user_data['ad'], "soyad": context.user_data['soyad'], "adresil": "" if il == "YOK" else il}
    try:
        res = requests.post(AD_SOYAD_URL, headers=HEADERS, data=payload)
        matches = re.findall(r'<td.*?>(.*?)</td>', res.text)
        if matches:
            for i in range(0, min(len(matches), 18), 6):
                k = matches[i:i+6]
                p = {"TC": k[0], "AD": k[1], "DOGUMTARIHI": k[2], "ANNEADI": k[3], "GSM": k[4]}
                await update.message.reply_text(format_person(p, "SONUÇ"), parse_mode="Markdown")
            await update.message.reply_text("✅ İşlem bitti.", reply_markup=get_back_to_menu_button())
        else: await update.message.reply_text("❌ Kayıt yok.", reply_markup=get_back_to_menu_button())
    except: await update.message.reply_text("⚠️ Hata.")
    return ConversationHandler.END

async def adres_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        res = requests.get(f"{ADRES_API_URL}{update.message.text}", headers=HEADERS).json()
        if res.get("data"):
            a = res["data"][0]
            m = f"📍 **ADRES**\n\n🆔 TC: `{a.get('TC')}`\n🏠 GÜNCEL: `{a.get('GUNCELADRES')}`\n⌛ GEÇMİŞ: `{a.get('GECMISADRES')}`"
            await update.message.reply_text(m, parse_mode="Markdown", reply_markup=get_back_to_menu_button())
        else: await update.message.reply_text("❌ Kayıt yok.")
    except: await update.message.reply_text("⚠️ Hata.")
    return ConversationHandler.END

async def tc_gsm_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        res = requests.get(f"{TC_GSM_URL}{update.message.text}", headers=HEADERS).json()
        if res.get("results"):
            m = "✅ **GSM BULUNDU**\n\n"
            for r in res["results"]: m += f"🆔 TC: `{r.get('TC')}`\n📱 GSM: `{r.get('GSM')}`\n"
            await update.message.reply_text(m, parse_mode="Markdown", reply_markup=get_back_to_menu_button())
        else: await update.message.reply_text("❌ Kayıt yok.")
    except: await update.message.reply_text("⚠️ Hata.")
    return ConversationHandler.END

# --- MAIN ---
if __name__ == '__main__':
    keep_alive() # Web Sunucusunu Başlat
    app = ApplicationBuilder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^(go_adsoyad|go_sulale|go_adres|go_tcgsm|go_gsmtc|go_ip)$')],
        states={
            AD: [MessageHandler(filters.TEXT & (~filters.COMMAND), ad_al)],
            SOYAD: [MessageHandler(filters.TEXT & (~filters.COMMAND), soyad_al)],
            IL: [MessageHandler(filters.TEXT & (~filters.COMMAND), ad_soyad_sorgula)],
            SULALE_TC: [MessageHandler(filters.TEXT & (~filters.COMMAND), sulale_sorgula)],
            ADRES_TC: [MessageHandler(filters.TEXT & (~filters.COMMAND), adres_sorgula)],
            TC_GSM: [MessageHandler(filters.TEXT & (~filters.COMMAND), tc_gsm_sorgula)],
            GSM_TC: [MessageHandler(filters.TEXT & (~filters.COMMAND), gsm_tc_sorgula)],
            IP_STATE: [MessageHandler(filters.TEXT & (~filters.COMMAND), ip_sorgula)],
        },
        fallbacks=[CallbackQueryHandler(button_handler, pattern='^main_menu$')],
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler, pattern='^main_menu$'))
    app.add_handler(conv)
    
    print("Bot başlatılıyor...")
    app.run_polling()
