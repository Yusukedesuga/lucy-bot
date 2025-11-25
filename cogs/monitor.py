import discord
from discord.ext import commands
import os
from datetime import datetime, timedelta

class Monitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_scold_date = None # 最後に怒った日を覚えるメモ
        
        # ID読み込み
        try:
            self.chat_id = int(os.getenv("CHAT_CHANNEL_ID"))
            self.target_id = int(os.getenv("TARGET_USER_ID"))
        except:
            print("⚠️ Monitor Cog: ID Load Error")

    # ステータス変化を監視するイベント
    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        # ターゲット（太田さん）以外は無視
        if after.id != self.target_id: return

        # ゲームを起動したかチェック
        if after.activity and after.activity != before.activity:
            game_name = after.activity.name
            
            # 監視対象のゲームリスト
            target_games = ["FINAL FANTASY", "Monster Hunter", "Steam"]
            
            # ゲーム名が含まれているかチェック（部分一致）
            if any(t_game in game_name for t_game in target_games):
                
                # 時間チェック（日本時間）
                jst_now = datetime.utcnow() + timedelta(hours=9)
                today_str = jst_now.strftime('%Y-%m-%d')

                # 【条件】平日(月～金) の 10時～18時
                if jst_now.weekday() < 5 and 10 <= jst_now.hour < 18:
                    
                    # 今日まだ怒ってない場合だけ怒る
                    if self.last_scold_date != today_str:
                        channel = self.bot.get_channel(self.chat_id)
                        if channel:
                            await channel.send(
                                f"<@{self.target_id}> **ちょっと！平日のお昼だよ！？** 😡\n"
                                f"『{game_name}』やってる場合じゃないでしょ！研究進んだの！？"
                            )
                            # 「今日怒った」と記録
                            self.last_scold_date = today_str

async def setup(bot):
    await bot.add_cog(Monitor(bot))
