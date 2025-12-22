import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
import json
import os

DATA_FILE = "data/knowledge.json"

# ------------------------------------------------------------------
# 確認用ビュー (Yes/Noボタン)
# ------------------------------------------------------------------
class ConfirmActionView(View):
    def __init__(self, cog, action_type, name, content=None):
        super().__init__(timeout=60)
        self.cog = cog
        self.action_type = action_type # "add_macro", "del_macro", "add_strat", "del_strat"
        self.name = name
        self.content = content

    @discord.ui.button(label="はい (実行)", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        # アクションの種類によって処理を分岐
        if self.action_type == "add_macro":
            self.cog.data["macros"][self.name] = self.content
            msg = f"✅ マクロ **「{self.name}」** を登録しました！"
        
        elif self.action_type == "del_macro":
            if self.name in self.cog.data["macros"]:
                del self.cog.data["macros"][self.name]
                msg = f"🗑️ マクロ **「{self.name}」** を削除しました。"
            else:
                msg = "❌ エラー: そのマクロは既にありません。"

        elif self.action_type == "add_strat":
            self.cog.data["strategies"][self.name] = self.content
            msg = f"✅ 攻略ボード **「{self.name}」** を登録しました！"

        elif self.action_type == "del_strat":
            if self.name in self.cog.data["strategies"]:
                del self.cog.data["strategies"][self.name]
                msg = f"🗑️ 攻略ボード **「{self.name}」** を削除しました。"
            else:
                msg = "❌ エラー: そのボードは既にありません。"
        
        # 保存して終了
        self.cog.save_data()
        await interaction.response.edit_message(content=msg, view=None, embed=None)

    @discord.ui.button(label="いいえ (キャンセル)", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="❌ 操作をキャンセルしました。", view=None, embed=None)

# ------------------------------------------------------------------
# メイン機能クラス
# ------------------------------------------------------------------
class Knowledge(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = self.load_data()

    def load_data(self):
        if not os.path.exists("data"): os.makedirs("data")
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump({"macros": {}, "strategies": {}}, f)
            return {"macros": {}, "strategies": {}}
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_data(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def format_macro(self, content):
        if "\n" not in content and "/p " in content:
            return content.replace("/p ", "\n/p ").strip()
        return content

    # ===============================================================
    # マクロ機能
    # ===============================================================
    
    # 登録 (オートコンプリート無し)
    @app_commands.command(name="addmacro", description="マクロを登録します")
    @app_commands.rename(name="コンテンツ名", content="マクロ内容")
    async def add_macro(self, interaction: discord.Interaction, name: str, content: str):
        preview_content = self.format_macro(content)
        msg = f"**以下の内容で登録しますか？**\nコンテンツ名: `{name}`\n\nプレビュー:\n```text\n{preview_content}\n```"
        view = ConfirmActionView(self, "add_macro", name, content)
        await interaction.response.send_message(msg, view=view, ephemeral=True)

    # 削除
    @app_commands.command(name="deletemacro", description="登録済みマクロを削除します")
    @app_commands.rename(name="コンテンツ名")
    async def delete_macro(self, interaction: discord.Interaction, name: str):
        if name not in self.data["macros"]:
            await interaction.response.send_message(f"❌ 「{name}」というマクロは見つかりません。", ephemeral=True)
            return

        content = self.format_macro(self.data["macros"][name])
        msg = f"⚠️ **本当に削除しますか？**\nコンテンツ名: `{name}`\n\n中身:\n```text\n{content}\n```"
        view = ConfirmActionView(self, "del_macro", name)
        await interaction.response.send_message(msg, view=view, ephemeral=True)

    # 閲覧
    @app_commands.command(name="viewmacro", description="マクロを表示します")
    @app_commands.rename(name="コンテンツ名")
    async def view_macro(self, interaction: discord.Interaction, name: str):
        content = self.data["macros"].get(name, "❌ 見つかりません")
        formatted = self.format_macro(content)
        await interaction.response.send_message(f"**{name}**:\n```text\n{formatted}\n```", ephemeral=True)

    # ★修正: add_macro のオートコンプリートを削除しました
    @delete_macro.autocomplete("name")
    @view_macro.autocomplete("name")
    async def macro_autocomplete(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=k, value=k) for k in self.data["macros"].keys() if current.lower() in k.lower()][:25]

    # ===============================================================
    # ストラテジーボード機能
    # ===============================================================

    # 登録 (オートコンプリート無し)
    @app_commands.command(name="addstrategyboard", description="攻略ボードを登録します")
    @app_commands.rename(name="コンテンツ名", code="コード")
    async def add_strat(self, interaction: discord.Interaction, name: str, code: str):
        msg = f"**以下の内容で登録しますか？**\nコンテンツ名: `{name}`\n\nプレビュー:\n```{code}```"
        view = ConfirmActionView(self, "add_strat", name, code)
        await interaction.response.send_message(msg, view=view, ephemeral=True)

    # 削除
    @app_commands.command(name="deletestrategyboard", description="登録済み攻略ボードを削除します")
    @app_commands.rename(name="コンテンツ名")
    async def delete_strat(self, interaction: discord.Interaction, name: str):
        if name not in self.data["strategies"]:
            await interaction.response.send_message(f"❌ 「{name}」というボードは見つかりません。", ephemeral=True)
            return

        code = self.data["strategies"][name]
        msg = f"⚠️ **本当に削除しますか？**\nコンテンツ名: `{name}`\n\n中身:\n```{code}```"
        view = ConfirmActionView(self, "del_strat", name)
        await interaction.response.send_message(msg, view=view, ephemeral=True)

    # 閲覧
    @app_commands.command(name="viewstrategyboard", description="攻略ボードを表示します")
    @app_commands.rename(name="コンテンツ名")
    async def view_strat(self, interaction: discord.Interaction, name: str):
        code = self.data["strategies"].get(name, "❌ 見つかりません")
        await interaction.response.send_message(f"**{name}**:\n```{code}```", ephemeral=True)

    # ★修正: add_strat のオートコンプリートを削除しました
    @delete_strat.autocomplete("name")
    @view_strat.autocomplete("name")
    async def strat_autocomplete(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=k, value=k) for k in self.data["strategies"].keys() if current.lower() in k.lower()][:25]

async def setup(bot):
    await bot.add_cog(Knowledge(bot))