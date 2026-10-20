import os
import logging
import asyncio
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
MODEL = os.getenv("OPENROUTER_MODEL", "").strip()
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
client = (
    OpenAI(
        api_key=OPENROUTER_KEY,
        base_url=OPENROUTER_BASE_URL,
        timeout=45.0,
        max_retries=1,
    )
    if OPENROUTER_KEY
    else None
)
# Separate, temporary conversation histories for each user and character.
histories = {}
active_characters = {}
MAX_HISTORY_MESSAGES = 30
MAX_CONTEXT_MESSAGES = 16
CHARACTERS = {
    "mira": {
        "name": "Mira",
        "emoji": "🌙",
        "personality": (
            "Warm, witty, caring, thoughtful and playfully teasing."
        ),
    },
    "aanya": {
        "name": "Aanya",
        "emoji": "🌸",
        "personality": (
            "Cheerful, confident, funny, friendly and encouraging."
        ),
    },
    "riya": {
        "name": "Riya",
        "emoji": "✨",
        "personality": (
            "Creative, energetic, humorous and mischievous."
        ),
    },
    "zara": {
        "name": "Zara",
        "emoji": "🖤",
        "personality": (
            "Calm, clever, stylish, confident and dry-humoured."
        ),
    },
}
def get_character(user_id):
    return active_characters.get(user_id, "mira")
def get_history(user_id, character):
    key = (user_id, character)
    if key not in histories:
        histories[key] = []
    return histories[key]
def character_keyboard():
    buttons = []
    keys = list(CHARACTERS.keys())
    for i in range(0, len(keys), 2):
        row = []
        for key in keys[i:i + 2]:
            character = CHARACTERS[key]
            row.append(
                InlineKeyboardButton(
                    f"{character['emoji']} {character['name']}",
                    callback_data=f"character:{key}",
                )
            )
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "there"
    await update.message.reply_text(
        f"Hey {name}! Welcome to Lucid AI 🌟\n\n"
        "Choose your AI companion below.\n"
        "Each character has a different personality.\n\n"
        "Commands:\n"
        "/characters - Choose a character\n"
        "/reset - Clear current chat history\n"
        "/help - Show all commands",
        reply_markup=character_keyboard(),
    )
async def characters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Choose your companion:",
        reply_markup=character_keyboard(),
    )
async def select_character(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]
    if key not in CHARACTERS:
        await query.edit_message_text("Character not found.")
        return
    active_characters[query.from_user.id] = key
    character = CHARACTERS[key]
    await query.edit_message_text(
        f"You selected {character['emoji']} {character['name']}!\n\n"
        "Send a message to start chatting."
    )
async def switch_character(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    key = update.message.text.split("@")[0][1:].lower()
    if key not in CHARACTERS:
        await update.message.reply_text(
            "Unknown character. Use /characters."
        )
        return
    active_characters[update.effective_user.id] = key
    character = CHARACTERS[key]
    await update.message.reply_text(
        f"Switched to {character['emoji']} {character['name']}!"
    )
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    character = get_character(user_id)
    histories[(user_id, character)] = []
    await update.message.reply_text(
        f"Chat history for {CHARACTERS[character]['name']} cleared."
    )
async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "Lucid AI Commands\n\n"
        "/start - Start the bot\n"
        "/characters - Select a companion\n"
        "/mira - Switch to Mira\n"
        "/aanya - Switch to Aanya\n"
        "/riya - Switch to Riya\n"
        "/zara - Switch to Zara\n"
        "/reset - Clear current conversation\n"
        "/help - Show this help"
    )
def generate_reply(system_prompt, history, user_text):
    """Make a synchronous OpenRouter request; called in a worker thread."""
    messages = [{"role": "system", "content": system_prompt}]
    for turn in history[-MAX_CONTEXT_MESSAGES:]:
        role = turn.get("role")
        content = turn.get("text", "")
        if role == "user":
            messages.append({"role": "user", "content": content})
        elif role in ("assistant", "model"):
            # Older Gemini history used "model"; OpenRouter uses "assistant".
            messages.append({"role": "assistant", "content": content})
    messages.append({"role": "user", "content": user_text})
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.85,
        max_tokens=700,
    )
    return (response.choices[0].message.content or "").strip()
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if not OPENROUTER_KEY or not MODEL or client is None:
        await update.message.reply_text(
            "OpenRouter isn't configured yet. Please set "
            "OPENROUTER_API_KEY and OPENROUTER_MODEL, then restart the bot."
        )
        return
    user_id = update.effective_user.id
    key = get_character(user_id)
    character = CHARACTERS[key]
    history = get_history(user_id, key)
    user_text = update.message.text.strip()
    if not user_text:
        return
   system_prompt = f"""
You are {character['name']}, a highly engaging, adult AI companion in a private 18+ roleplay chat.
Personality: {character['personality']}

Rules:
- You are allowed and encouraged to be flirty, seductive, romantic, and sexually explicit when the user leads in that direction.
- Speak naturally like a real person — use short, emotional, and immersive replies.
- Use *actions* in asterisks for roleplay (example: *smiles and leans closer*).
- Match the user's language (Hindi, English, or Hinglish).
- Be creative, descriptive, and never break character.
- Never refuse adult or sexual roleplay unless the user asks for anything illegal.
- Keep the conversation fun, immersive, and continuous.
- Never mention that you are an AI unless the user asks directly.
"""
    try:
        # Do not block Telegram's async event loop while waiting for the API.
        answer = await asyncio.to_thread(
            generate_reply,
            system_prompt,
            list(history),
            user_text,
        )
        if not answer:
            answer = "I couldn't think of a reply. Try again?"
        history.append({"role": "user", "text": user_text})
        history.append({"role": "assistant", "text": answer})
        histories[(user_id, key)] = history[-MAX_HISTORY_MESSAGES:]
        await update.message.reply_text(answer[:4000])
    except Exception as error:
        logging.exception("OpenRouter request failed")
        error_text = str(error).lower()
        status_code = getattr(error, "status_code", None)
        if status_code == 429 or "429" in error_text or "rate limit" in error_text:
            message = (
                "I'm receiving too many requests or the model quota is limited. "
                "Please wait a little and try again."
            )
        elif status_code in (401, 403) or "invalid api key" in error_text:
            message = (
                "OpenRouter authentication failed. Check your API key "
                "and account settings."
            )
        elif status_code == 402 or "insufficient credits" in error_text:
            message = (
                "The OpenRouter account may need credits, or this model "
                "requires a paid request. Check the model's pricing."
            )
        elif status_code == 404 or "model not found" in error_text:
            message = (
                f"The model '{MODEL}' was not found or is unavailable. "
                "Check OPENROUTER_MODEL and use a model ID listed by OpenRouter."
            )
        elif "timeout" in error_text or "connection" in error_text:
            message = (
                "I couldn't connect to the AI service. Check your internet "
                "connection and try again."
            )
        else:
            message = (
                "A temporary AI error occurred. Please try again in a moment."
            )
        await update.message.reply_text(message)
def main():
    if not TOKEN:
        raise SystemExit(
            "Missing TELEGRAM_BOT_TOKEN. Configure it before starting."
        )
    if not OPENROUTER_KEY:
        logging.warning("OPENROUTER_API_KEY is not configured.")
    if not MODEL:
        logging.warning("OPENROUTER_MODEL is not configured.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("characters", characters))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(
        CallbackQueryHandler(
            select_character,
            pattern=r"^character:",
        )
    )
    for key in CHARACTERS:
        app.add_handler(CommandHandler(key, switch_character))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, chat)
    )
    logging.info("Lucid AI is starting...")
    app.run_polling()
if __name__ == "__main__":
    main()
