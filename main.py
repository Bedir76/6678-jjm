import logging
import requests
import io
import os
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# --- RENDER İÇİN WEB SERVER (UYKUYU ENGELLEMEK İÇİN) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running! 200 OK"

def run_web():
    # Render PORT değişkenini otomatik atar
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- BOT AYARLARI ---
TOKEN = "8261166451:AAHT4vInOHOCMD9bGa41BA4O2eAlY405HLY"
MERNIS_API = "https://hukumsuz.de/api/mernis.php"
SULALE_API = "https://hukumsuz.de/api/sulale.php"
ADRES_API = "https://hukumsuz.de/api/adres.php"
TC_GSM_API = "https://hukumsuz.de/api/gsm.php"
GSM_TC_API = "https://hukumsuz.de/api/gsm.php"
IP_API = "https://ipinfo.io/{}/json"

# Conversation Durumları
AD, SOYAD, SEHIR, TC_AL, IP_AL = range(5)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Ad Soyad Sorgu", callback_data='ad_soyad_sorgu')],
        [InlineKeyboardButton("👥 Sülale Sorgu (TC)", callback_data='sulale_sorgu')],
        [InlineKeyboardButton("🏠 Adres Sorgu (TC)", callback_data='adres_sorgu')],
        [InlineKeyboardButton("📱 TC -> GSM Sorgu", callback_data='tc_gsm_sorgu')],
        [InlineKeyboardButton("🆔 GSM -> TC Sorgu", callback_data='gsm_tc_sorgu')],
        [InlineKeyboardButton("🌐 IP Sorgu", callback_data='ip_sorgu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🚀 **SORGU PANELİ**\n\nLütfen bir işlem seçin.\n\n👑 Kurucu: @ZEWND / @y9tknz"

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return ConversationHandler.END

# --- SORGU MOTORLARI ---
async def sorgu_motoru(update: Update, url: str, params: dict, dosya_adi: str):
    wait_msg = await update.message.reply_text("⏳ Sorgulanıyor...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=25)
        content = response.text.strip()
        if response.status_code == 200 and len(content) > 10:
            file_io = io.BytesIO(content.encode('utf-8'))
            file_io.name = dosya_adi
            await update.message.reply_document(document=file_io, caption="✅ İşlem Başarılı.")
        else:
            await update.message.reply_text(f"❌ Kayıt bulunamadı veya API hatası.\nYanıt: `{content[:50]}`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hata: {str(e)}")
    await wait_msg.delete()
    return await start(update, None)

async def ip_sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ip_addr = update.message.text.strip()
    wait_msg = await update.message.reply_text(f"🌐 `{ip_addr}` sorgulanıyor...")
    try:
        response = requests.get(IP_API.format(ip_addr), timeout=15)
        if response.status_code == 200:
            d = response.json()
            res = (f"🌐 **IP SONUÇ**\n\n📍 **IP:** `{d.get('ip')}`\n🏙 **Şehir:** {d.get('city')}\n"
                   f"🚩 **Ülke:** {d.get('country')}\n🏢 **ISP:** {d.get('org')}\n📍 **Konum:** `{d.get('loc')}`")
            await update.message.reply_text(res, parse_mode='Markdown')
        else: await update.message.reply_text("❌ Bilgi alınamadı.")
    except: await update.message.reply_text("❌ API Hatası.")
    await wait_msg.delete()
    return await start(update, None)

# --- AKIŞ YÖNETİMİ ---
async def ad_soyad_basla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("🔍 Sorgulanacak kişinin **ADINI** giriniz:")
    return AD

async def ad_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ad'] = update.message.text.strip().upper()
    await update.message.reply_text("🔍 **SOYADINI** giriniz:")
    return SOYAD

async def soyad_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['soyad'] = update.message.text.strip().upper()
    await update.message.reply_text("📍 **İL** (Yoksa . koyun):")
    return SEHIR

async def sehir_al_ve_bitir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sehir = update.message.text.strip().upper()
    p = {'ad': context.user_data['ad'], 'soyad': context.user_data['soyad']}
    if sehir != ".": p['il'] = sehir
    await sorgu_motoru(update, MERNIS_API, p, "mernis.txt")
    return ConversationHandler.END

async def tc_gsm_ip_istek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['islem'] = query.data
    texts = {
        'sulale_sorgu': "👥 Sülale için **TC** giriniz:",
        'adres_sorgu': "🏠 Adres için **TC** giriniz:",
        'tc_gsm_sorgu': "📱 GSM bulmak için **TC** giriniz:",
        'gsm_tc_sorgu': "🆔 TC bulmak için **GSM** giriniz:",
        'ip_sorgu': "🌐 **IP ADRESİ** giriniz:"
    }
    await query.edit_message_text(texts[query.data])
    return IP_AL if query.data == 'ip_sorgu' else TC_AL

async def tc_gsm_isleme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    i = context.user_data.get('islem')
    if i == 'sulale_sorgu': await sorgu_motoru(update, SULALE_API, {'tc': v}, "sulale.txt")
    elif i == 'adres_sorgu': await sorgu_motoru(update, ADRES_API, {'tc': v}, "adres.txt")
    elif i == 'tc_gsm_sorgu': await sorgu_motoru(update, TC_GSM_API, {'tc': v}, "gsm.txt")
    elif i == 'gsm_tc_sorgu': await sorgu_motoru(update, GSM_TC_API, {'gsm': v}, "gsmtc.txt")
    return ConversationHandler.END

def main():
    # Web server'ı başlat
    keep_alive()
    
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ad_soyad_basla, pattern='^ad_soyad_sorgu$'),
            CallbackQueryHandler(tc_gsm_ip_istek, pattern='^(sulale_sorgu|adres_sorgu|tc_gsm_sorgu|gsm_tc_sorgu|ip_sorgu)$')
        ],
        states={
            AD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ad_al)],
            SOYAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, soyad_al)],
            SEHIR: [MessageHandler(filters.TEXT & ~filters.COMMAND, sehir_al_ve_bitir)],
            TC_AL: [MessageHandler(filters.TEXT & ~filters.COMMAND, tc_gsm_isleme)],
            IP_AL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ip_sorgula)],
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    
    print("--- BOT VE WEB SERVER 200 OK ---")
    app.run_polling()

if __name__ == '__main__':
    main()

