import discord
from discord.ext import commands
import google.generativeai as genai
import os
import sys
import asyncio
from duckduckgo_search import DDGS

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompts import LUCY_SYSTEM_PROMPT, SEARCH_ADDON

class Search(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=LUCY_SYSTEM_PROMPT + SEARCH_ADDON
            )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return

        # ★修正：判定ロジックを強化（スレッド内ならメンション不要にする）
        is_mention = self.bot.user in message.mentions
        is_bot_thread = isinstance(message.channel, discord.Thread) and message.channel.owner_id == self.bot.user.id

        # メンション または Botのスレッド内での発言なら処理開始
        if is_mention or is_bot_thread:
            clean_text = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            
            keywords = ["って何", "ってなに", "とは", "調べて", "検索", "教えて", "なんですか"]
            is_search_request = any(k in clean_text for k in keywords)

            # 検索キーワードが含まれていたら実行
            if is_search_request:
                print(f"🔍 検索リクエスト検知: {clean_text}") # デバッグ
                
                async with message.channel.typing():
                    try:
                        # 1. 検索ワードの抽出
                        search_query = clean_text
                        for k in keywords:
                            search_query = search_query.replace(k, "")
                        search_query = search_query.strip().replace("?", "").replace("？", "")

                        # クエリ作成（FF14を追加）
                        final_query = f"FF14 {search_query}"
                        print(f"🔍 検索ワード: {final_query}")
                        
                        # 2. 検索実行
                        print("⏳ DuckDuckGo検索開始...")
                        results = []
                        
                        def run_search():
                            try:
                                with DDGS() as ddgs:
                                    return list(ddgs.text(final_query, region='jp-jp', max_results=3))
                            except Exception as e:
                                print(f"❌ DDGS内部エラー: {e}")
                                return []
                        
                        results = await asyncio.to_thread(run_search)
                        print(f"✅ 検索完了: {len(results)}件ヒット")

                        if not results:
                            await message.reply(f"ごめんね、「{search_query}」について調べてみたけど、情報が見つからなかったよ…😢")
                            return

                        # 3. テキスト整形
                        search_text = "【Web検索結果】\n"
                        for res in results:
                            search_text += f"タイトル: {res['title']}\n内容: {res['body']}\nURL: {res['href']}\n---\n"

                        # 4. Gemini生成
                        print("⏳ Gemini生成開始...")
                        prompt = f"ユーザーの質問: 「{clean_text}」\n\n{search_text}\n\nこの検索結果を使って回答してください。"
                        
                        response = self.model.generate_content(prompt)
                        bot_reply = response.text.strip()
                        print("✅ Gemini生成完了")

                        await message.reply(bot_reply)

                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        print(f"❌ 全体エラー: {e}")
                        await message.reply(f"あわわ、目が回っちゃった…（エラー: `{e}`）")

async def setup(bot):
    await bot.add_cog(Search(bot))
