import logging
import requests
import re
import os
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, 
    MessageHandler, CallbackQueryHandler, ConversationHandler, filters
)

# --- WEB SERVER (CANLI TUTMA) ---
server = Flask('')

@server.route('/')
def home():
    return "Bot Aktif!", 200

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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10)",
    "Cookie": "_ym_uid=1770508134870072739; dogrulama=4f0ade62a0339cc6; PHPSESSID=vbf1aquo66orap8jn264jn598e"
}

# Durumlar
AD, SOYAD, IL, SULALE_TC = range(4)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- YARDIMCI FONKSİYONLAR ---
def format_person(p, title):
    if not p: return ""
    
    # Verileri temizle ve birleştir
    isim = f"{p.get('AD', '')} {p.get('SOYAD', '')}".strip()
    ana_baba = f"{p.get('ANNEADI', '?')} / {p.get('BABAADI', '?')}"
    memleket = f"{p.get('MEMLEKETIL', '')} / {p.get('MEMLEKETILCE', '')}".strip(" /")
    ikamet = f"{p.get('ADRESIL', '')} / {p.get('ADRESILCE', '')}".strip(" /")

    res = (
        f"🌟 **{title}** 🌟\n\n"
        f"🆔 **TC:** `{p.get('TC', 'Bilinmiyor')}`\n"
        f"👤 **AD SOYAD:** `{isim}`\n"
        f"📅 **DOĞUM:** `{p.get('DOGUMTARIHI', 'Bilinmiyor')}`\n"
        f"📱 **GSM:** `{p.get('GSM', 'YOK')}`\n"
        f"👪 **ANNE / BABA:** `{ana_baba}`\n"
        f"🗾 **MEMLEKET:** `{memleket if memleket else 'Bilinmiyor'}`\n"
        f"📍 **İKAMETGAH:** `{ikamet if ikamet else 'Bilinmiyor'}`\n"
        f"━━━━━━━━━━━━━━━"
    )
    return res

def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔍 Ad Soyad Sorgu", callback_data='go_adsoyad')],
        [InlineKeyboardButton("👨‍👩‍👧‍👦 Sülale Sorgu", callback_data='go_sulale')],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ana Menüye Dön", callback_data='main_menu')]])

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🚀 **SORGU PANELİ**\n\nLütfen bir işlem seçin."
    if update.message:
        await update.message.reply_text(msg, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
    else:
        await update.callback_query.message.edit_text(msg, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'main_menu':
        await start(update, context)
        return ConversationHandler.END
    
    if query.data == 'go_adsoyad':
        await query.edit_message_text("📝 **AD** girin:")
        return AD
    elif query.data == 'go_sulale':
        await query.edit_message_text("🆔 Sülale için **TC** girin:")
        return SULALE_TC

# --- SORGULAMA MANTIĞI ---
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
    payload = {
        "ad": context.user_data.get('ad'), 
        "soyad": context.user_data.get('soyad'), 
        "adresil": "" if il == "YOK" else il
    }
    
    msg = await update.message.reply_text("🔍 Sorgulanıyor, lütfen bekleyin...")
    
    try:
        res = requests.post(AD_SOYAD_URL, headers=HEADERS, data=payload, timeout=25)
        matches = re.findall(r'<td.*?>(.*?)</td>', res.text)
        
        if matches:
            # Sütun yapısı: ID(0), TC(1), AD(2), SOYAD(3), GSM(4), BABAADI(5)...
            step = 21 
            found_count = 0
            
            for i in range(0, len(matches), step):
                k = matches[i:i+step]
                if len(k) < 15: continue
                
                p = {
                    "TC": k[1],
                    "AD": k[2],
                    "SOYAD": k[3],
                    "GSM": k[4],
                    "BABAADI": k[5],
                    "ANNEADI": k[7],
                    "DOGUMTARIHI": k[9],
                    "MEMLEKETIL": k[12],
                    "MEMLEKETILCE": k[13],
                    "ADRESIL": k[15],
                    "ADRESILCE": k[16]
                }
                await update.message.reply_text(format_person(p, "AD SOYAD SONUÇ"), parse_mode="Markdown")
                found_count += 1
                if found_count >= 10: break # Çok fazla sonuç gelirse botu yormayalım
                
            await update.message.reply_text(f"✅ {found_count} sonuç listelendi.", reply_markup=get_back_to_menu_button())
        else:
            await update.message.reply_text("❌ Kayıt bulunamadı.", reply_markup=get_back_to_menu_button())
            
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hata oluştu: {str(e)}")
    
    return ConversationHandler.END

async def sulale_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tc = update.message.text
    await update.message.reply_text(f"🔍 `{tc}` için sülale taranıyor...")
    try:
        res = requests.get(f"{SULALE_API_URL}{tc}", headers=HEADERS, timeout=25).json()
        if res.get("person"):
            await update.message.reply_text(format_person(res["person"], "KİŞİ BİLGİSİ"), parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Veri bulunamadı.")
    except:
        await update.message.reply_text("⚠️ API bağlantı hatası.")
    return ConversationHandler.END

# --- ANA ÇALIŞTIRICI ---
if __name__ == '__main__':
    keep_alive() 
    app = ApplicationBuilder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^(go_adsoyad|go_sulale)$')],
        states={
            AD: [MessageHandler(filters.TEXT & (~filters.COMMAND), ad_al)],
            SOYAD: [MessageHandler(filters.TEXT & (~filters.COMMAND), soyad_al)],
            IL: [MessageHandler(filters.TEXT & (~filters.COMMAND), ad_soyad_sorgula)],
            SULALE_TC: [MessageHandler(filters.TEXT & (~filters.COMMAND), sulale_sorgula)],
        },
        fallbacks=[CommandHandler('start', start), CallbackQueryHandler(button_handler, pattern='^main_menu$')],
        allow_reentry=True
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    
    print("Bot başlatıldı...")
    app.run_polling()
