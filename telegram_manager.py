import telebot
import threading
import os
import time
from dotenv import load_dotenv

class TelegramManager:
    def __init__(self, ask_callback, speak_callback, set_mode_callback, get_status_callback):
        load_dotenv()
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.allowed_users = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
        self.allowed_users = [u.strip() for u in self.allowed_users if u.strip()]
        
        if not self.token or self.token == "your_telegram_bot_token_here":
            print("WARNING: Telegram Token non configurato nel file .env.")
            self.bot = None
            return

        self.bot = telebot.TeleBot(self.token)
        self.ask_callback = ask_callback
        self.speak_callback = speak_callback
        self.set_mode_callback = set_mode_callback
        self.get_status_callback = get_status_callback
        
        self._setup_handlers()

    def _setup_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def start(message):
            if not self._is_authorized(message): return
            self.bot.reply_to(message, "🤖 *Absalom OS Online*\n\nCiao! Sono pronto a ricevere i tuoi comandi. Prova a scrivermi qualcosa o usa /status.")

        @self.bot.message_handler(commands=['status'])
        def status(message):
            if not self._is_authorized(message): return
            status_info = self.get_status_callback()
            msg = f"🛰 *Stato Absalom*\n\n"
            msg += f"- Modalità: {'SVEGLIO' if status_info['is_awake'] else 'STANDBY'}\n"
            msg += f"- Occupato: {'SÌ' if status_info['is_busy'] else 'NO'}\n"
            msg += f"- Ora sistema: {time.strftime('%H:%M:%S')}"
            self.bot.reply_to(message, msg, parse_mode='Markdown')

        @self.bot.message_handler(commands=['sleep'])
        def sleep(message):
            if not self._is_authorized(message): return
            self.set_mode_callback("asleep")
            self.bot.reply_to(message, "💤 Impostata modalità Standby.")

        @self.bot.message_handler(commands=['wake'])
        def wake(message):
            if not self._is_authorized(message): return
            self.set_mode_callback("awake")
            self.bot.reply_to(message, "🔆 Absalom si è svegliato!")

        @self.bot.message_handler(func=lambda m: True)
        def handle_text(message):
            if not self._is_authorized(message): return
            
            user_input = message.text
            print(f"TELEGRAM: Ricevuto '{user_input}'")
            
            self.bot.send_chat_action(message.chat.id, 'typing')
            
            # Esecuzione LLM (e caricamento busy gestito all'interno o esternamente?)
            # Per ora passiamo il comando ad ask_llm
            response = self.ask_callback(user_input)
            
            if response:
                self.bot.reply_to(message, response)
                
                # Attivazione TTS come richiesto dall'utente
                if self.speak_callback:
                    threading.Thread(target=self.speak_callback, args=(response,), daemon=True).start()
            else:
                self.bot.reply_to(message, "Non sono riuscito a elaborare la richiesta.")

    def _is_authorized(self, message):
        user_id = str(message.from_user.id)
        if not self.allowed_users:
            # Se non configurato, permetti a tutti per ora ma avvisa
            print(f"WARNING: Nessun ID autorizzato configurato. Permetto accesso a {user_id}")
            return True
        if user_id in self.allowed_users:
            return True
        
        print(f"DENIED: Utente {user_id} ({message.from_user.username}) ha provato ad accedere.")
        self.bot.reply_to(message, f"❌ Accesso negato.\nIl tuo ID è: `{user_id}`\nConfiguralo in .env per abilitare l'accesso.", parse_mode='Markdown')
        return False

    def start(self):
        if not self.bot:
            return
        print("Avvio polling Telegram Bot...")
        # Usiamo non-blocking per integrarlo nel main
        thread = threading.Thread(target=self.bot.infinity_polling, daemon=True)
        thread.start()
        return thread

    def send_notification(self, text):
        """Metodo per inviare notifiche push (se CHAT_ID è configurato)."""
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if self.bot and chat_id:
            try:
                self.bot.send_message(chat_id, text, parse_mode='Markdown')
            except Exception as e:
                print(f"Errore invio notifica Telegram: {e}")
