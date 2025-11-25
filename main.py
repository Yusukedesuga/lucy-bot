import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
from keep_alive import keep_alive

# --- 設定読み込み ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# --- Botの設定 ---
# Cogsを使うために commands.Bot にアップグレードします
intents = discord.Intents.default()
intents.message_content = True
intents.presences = True # 監視機能のために必要！

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# --- 起動時の処理 ---
@bot.event
async def on_ready():
    print(f'--------------------------------')
    print(f'ログインしました: {bot.user}')
    print(f'ID: {bot.user.id}')
    print(f'--------------------------------')
    print(f'Lucy Deps, 全システム稼働開始！🚀')

# --- Cogs（機能）を読み込む魔法 ---
async def load_extensions():
    # cogsフォルダの中にある .py ファイルを全部読み込む
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')
            print(f"拡張機能ロード完了: {filename}")

# --- メイン実行関数 ---
async def main():
    # 1. Webサーバー起動（Render用）
    keep_alive()
    
    if not TOKEN:
        print("エラー: DISCORD_TOKEN が見つかりません！.envを確認してね！")
        return

    # 2. Bot起動プロセス
    async with bot:
        await load_extensions() # ここで chat, partyfinder, monitor を合体！
        await bot.start(TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Ctrl+C で止めた時のエラーを無視
        pass
