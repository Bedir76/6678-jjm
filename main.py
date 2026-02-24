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

# --- WEB SERVER (7/24 AKTİF TUTMA) ---
server = Flask('')

@server.route('/', defaults={'path': ''})
@server.route('/<path:path>')
def catch_all(path):
    return "Bot Aktif ve Uyanik!", 200

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

# Durumlar
AD, SOYAD, IL, SULALE_TC, ADRES_TC, TC_GSM, GSM_TC, IP_STATE = range(8)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- YARDIMCI FONKSİYONLAR ---
def format_person(p, title):
    if not p: return ""
    
    # Memleket birleştirme (İl / İlçe / Köy)
    m_il = p.get('MEMLEKETIL', '')
    m_ilce = p.get('MEMLEKETILCE', '')
    m_koy = p.get('MEMLEKETKOY', '')
    memleket_tam = f"{m_il} / {m_ilce} / {m_koy}".strip(" / ") or "Bilinmiyor"
    
    # Yaşadığı yer birleştirme (İl / İlçe)
    a_il = p.get('ADRESIL', '')
    a_ilce = p.get('ADRESILCE', '')
    yer_tam = f"{a_il} / {a_ilce}".strip(" / ") or m_il + " / " + m_ilce # Adres yoksa memleketi yaz
    
    res = f"🌟 **{title}** 🌟\n\n"
    res += f"🆔 **TC:** `{p.get('TC', 'Bilinmiyor')}`\n"
    res += f"👤 **AD SOYAD:** `{p.get('AD', '')} {p.get('SOYAD', '')}`\n"
    res += f"📅 **DOĞUM:** `{p.get('DOGUMTARIHI', 'Bilinmiyor')}`\n"
    res += f"📱 **GSM:** `{p.get('GSM', 'YOK')}`\n"
    res += f"👪 **ANNE / BABA:** `{p.get('ANNEADI', '?')} / {p.get('BABAADI', '?')}`\n"
    res += f"🗾 **MEMLEKET:** `{memleket_tam}`\n"
    res += f"📍 **YAŞADIĞI YER:** `{yer_tam.strip(' / ')}`\n"
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
    context.user_data.clear()
    msg = "🚀 **SORGU PANELİ**\n\nLütfen bir işlem seçin.\n\n👑 **Kurucu:** @ZEWND / @y9tknz"
    if update.message:
        await update.message.reply_text(msg, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
    else:
        await update.callback_query.message.reply_text(msg, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'main_menu':
        context.user_data.clear()
        await query.edit_message_text("🚀 **ANA MENÜ**", reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END
    
    prompts = {
        'go_adsoyad': "📝 **AD** girin:", 'go_sulale': "🆔 Sülale için **TC** girin:", 
        'go_adres': "🏠 **TC** girin:", 'go_tcgsm': "📱 **TC** girin:", 
        'go_gsmtc': "🆔 **GSM** girin:", 'go_ip': "🌐 **IP ADRESİ** girin:"
    }
    states = {
        'go_adsoyad': AD, 'go_sulale': SULALE_TC, 'go_adres': ADRES_TC,
        'go_tcgsm': TC_GSM, 'go_gsmtc': GSM_TC, 'go_ip': IP_STATE
    }
    await query.edit_message_text(prompts[query.data], parse_mode="Markdown")
    return states[query.data]

# --- SORGULAMA FONKSİYONLARI ---
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
        # API JSON döndürdüğü için .json() kullanıyoruz
        response = requests.post(AD_SOYAD_URL, headers=HEADERS, data=payload)
        data = response.json()
        
        if data:
            # Eğer API bir liste döndürüyorsa döngüye sokuyoruz
            results = data if isinstance(data, list) else [data]
            for p in results[:10]: # Max 10 sonuç gönder (Telegram sınırı için)
                await update.message.reply_text(format_person(p, "SONUÇ"), parse_mode="Markdown")
            await update.message.reply_text("✅ İşlem bitti.", reply_markup=get_back_to_menu_button())
        else:
            await update.message.reply_text("❌ Kayıt bulunamadı.", reply_markup=get_back_to_menu_button())
    except:
        await update.message.reply_text("⚠️ Veri çekme hatası veya geçersiz yanıt.", reply_markup=get_back_to_menu_button())
    return ConversationHandler.END

async def sulale_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tc = update.message.text
    try:
        res = requests.get(f"{SULALE_API_URL}{tc}", headers=HEADERS, timeout=25).json()
        if res.get("person"):
            await update.message.reply_text(format_person(res["person"], "SORGULANAN"), parse_mode="Markdown", reply_markup=get_back_to_menu_button())
        else: await update.message.reply_text("❌ Kayıt yok.")
    except: await update.message.reply_text("⚠️ Hata.")
    return ConversationHandler.END

# --- MAIN ---
if __name__ == '__main__':
    keep_alive() 
    app = ApplicationBuilder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^(go_adsoyad|go_sulale|go_adres|go_tcgsm|go_gsmtc|go_ip)$')],
        states={
            AD: [MessageHandler(filters.TEXT & (~filters.COMMAND), ad_al)],
            SOYAD: [MessageHandler(filters.TEXT & (~filters.COMMAND), soyad_al)],
            IL: [MessageHandler(filters.TEXT & (~filters.COMMAND), ad_soyad_sorgula)],
            SULALE_TC: [MessageHandler(filters.TEXT & (~filters.COMMAND), sulale_sorgula)],
        },
        fallbacks=[
            CallbackQueryHandler(button_handler, pattern='^main_menu$'),
            CommandHandler('start', start)
        ],
        allow_reentry=True
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler, pattern='^main_menu$'))
    app.add_handler(conv)
    
    print("Bot modern JSON formatıyla başlatıldı!")
    app.run_polling()

