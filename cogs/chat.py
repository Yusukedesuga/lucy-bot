import discord
from discord.ext import commands
import google.generativeai as genai
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompts import LUCY_SYSTEM_PROMPT
from utils import load_macros, save_macros

class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chat_history = []
        
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=LUCY_SYSTEM_PROMPT
            )
        else:
            print("⚠️ 警告: GEMINI_API_KEY が設定されていません！")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return

        is_mention = self.bot.user in message.mentions
        is_bot_thread = isinstance(message.channel, discord.Thread) and message.channel.owner_id == self.bot.user.id

        if is_mention or is_bot_thread:
            async with message.channel.typing():
                try:
                    clean_text = message.content.replace(f'<@{self.bot.user.id}>', '').strip()

                    # ★修正：search.pyと同じキーワードにする
                    search_keywords = ["って何", "ってなに", "とは", "調べて", "検索", "教えて", "なんですか"]
                    # ※「教えて」はマクロ一覧とかぶる可能性があるので、
                    # 「マクロ」という言葉が入っていない場合のみ検索に回す、というロジックにするとより安全ですが、
                    # 一旦はこれで動かしてみましょう！
                    
                    if any(k in clean_text for k in search_keywords):
                        # ただし「マクロ」の話をしている時は検索に回さない（chat.pyで処理する）
                        if "マクロ" not in clean_text:
                            return
                    
                    macros = load_macros()

                    # --- マクロ登録機能 ---
                    if clean_text.startswith("マクロ登録") and '\n' in clean_text:
                        lines = clean_text.split('\n', 1)
                        if len(lines) >= 2:
                            header = lines[0].replace("マクロ登録", "").strip()
                            header = header.replace("[", "").replace("]", "").replace("【", "").replace("】", "")
                            
                            if not header:
                                await message.reply("登録する名前がないよ！ `マクロ登録 [名前]` にしてね！")
                                return
                            
                            macros[header] = lines[1].strip()
                            save_macros(macros)
                            await message.reply(f"『{header}』を覚えたよ！📦")
                            return

                    # --- Gemini会話機能 ---
                    
                    prompt_add_info = ""

                    # ★修正：判定を緩くした一覧表示ロジック
                    keywords_main = ["マクロ", "覚え", "登録", "記憶", "知っ"]
                    keywords_sub = ["一覧", "何", "なん", "教えて", "見せて", "ある", "どんな", "リスト", "全部", "すべて"]
                    
                    if any(k in clean_text for k in keywords_main) and any(k in clean_text for k in keywords_sub):
                        if macros:
                            macro_list = ", ".join(macros.keys())
                            prompt_add_info += f"【システム情報: 現在登録されているマクロ名の一覧】\n{macro_list}\n\n"
                        else:
                            prompt_add_info += "【システム情報: 現在登録されているマクロはありません】\n\n"

                    # マクロ検索（部分一致）
                    referenced_macro = ""
                    found_key = ""
                    for key, value in macros.items():
                        if key in clean_text:
                            referenced_macro = value
                            found_key = key
                            break
                    
                    # 時間取得
                    jst_now = datetime.utcnow() + timedelta(hours=9)
                    time_str = jst_now.strftime('%Y/%m/%d %H:%M')
                    weekday_str = ["月", "火", "水", "木", "金", "土", "日"][jst_now.weekday()]
                    
                    prompt = f"【システム情報: 現在は {time_str} ({weekday_str}) です】\n"
                    prompt += prompt_add_info
                    
                    if referenced_macro:
                        prompt += f"【参考データ】登録されているマクロ({found_key}):\n{referenced_macro}\n\n"
                    
                    prompt += f"ユーザーの発言: {clean_text}"

                    chat = self.model.start_chat(history=self.chat_history)
                    response = chat.send_message(prompt)
                    bot_reply = response.text.strip()

                    # 募集コマンド処理
                    if bot_reply.startswith("CMD:RECRUIT"):
                        parts = bot_reply.split("|")
                        content = parts[1]
                        time_str = parts[2]
                        comment = parts[3]
                        recruit_type = parts[4] if len(parts) > 4 else "FULL"
                        author_role = parts[5] if len(parts) > 5 else None
                        
                        self.bot.dispatch("recruit_request", message, content, time_str, comment, recruit_type, author_role)
                        self.chat_history = [] 
                        return 

                    # 返信処理
                    if not isinstance(message.channel, discord.Thread):
                        thread_name = f"Lucyとのナイショ話 ({message.author.display_name})"
                        try:
                            thread = await message.create_thread(name=thread_name, auto_archive_duration=60)
                            await thread.send(f"{message.author.mention} ここでゆっくり話そう！\n\n{bot_reply}")
                        except:
                            await message.reply(bot_reply)
                    else:
                        await message.reply(bot_reply)
                    
                    self.chat_history.append({"role": "user", "parts": [clean_text]})
                    self.chat_history.append({"role": "model", "parts": [bot_reply]})
                    if len(self.chat_history) > 20: del self.chat_history[0:2]

                except Exception as e:
                    print(f"Chat Error: {e}")
                    await message.reply(f"あわわ、エラーが出ちゃった… `{e}`")

async def setup(bot):
    await bot.add_cog(Chat(bot))
