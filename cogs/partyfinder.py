import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Select, Modal, TextInput
import os
import datetime
import traceback

JP_DCS = {
    "Elemental": ["Aegis", "Atomos", "Carbuncle", "Garuda", "Gungnir", "Kujata", "Tonberry", "Typhon"],
    "Gaia": ["Alexander", "Bahamut", "Durandal", "Fenrir", "Ifrit", "Ridill", "Tiamat", "Ultima"],
    "Mana": ["Anima", "Asura", "Chocobo", "Hades", "Ixion", "Masamune", "Pandaemonium", "Titan"],
    "Meteor": ["Belias", "Mandragora", "Ramuh", "Shinryu", "Unicorn", "Valefor", "Yojimbo", "Zeromus"] 
}

# ------------------------------------------------------------------
# サーバー絵文字設定
# ------------------------------------------------------------------
ROLE_ICONS = {
    "MT": "🛡️",
    "ST": "🛡️",
    "H1": "💚",
    "H2": "💚",
    "D1": "⚔️",
    "D2": "⚔️",
    "D3": "🏹",
    "D4": "🪄",
    "Tank": "🛡️",
    "Healer": "💚",
    "DPS1": "⚔️",
    "DPS2": "⚔️",
    "Any": "👑"
}

def get_emoji_safe(role_name):
    icon_str = ROLE_ICONS.get(role_name)
    if not icon_str:
        if "MT" in role_name or "ST" in role_name or "Tank" in role_name: icon_str = ROLE_ICONS.get("Tank")
        elif "H" in role_name or "Healer" in role_name: icon_str = ROLE_ICONS.get("Healer")
        elif "D" in role_name or "DPS" in role_name: icon_str = ROLE_ICONS.get("DPS1")
    
    if not icon_str: return None
    if "<:" in icon_str and ">" in icon_str:
        return discord.PartialEmoji.from_str(icon_str)
    return icon_str

# ------------------------------------------------------------------
# 調整枠用のメモ入力Modal
# ------------------------------------------------------------------
class AnyRoleModal(Modal, title="調整枠で参加"):
    note = TextInput(label="出せるロール/ジョブは？", placeholder="例: タンクとヒラなら何でも！", required=True)

    def __init__(self, parent_view, user_name):
        super().__init__()
        self.parent_view = parent_view
        self.user_name = user_name

    async def on_submit(self, interaction: discord.Interaction):
        try:
            entry = {"name": self.user_name, "note": self.note.value}
            self.parent_view.any_members = [m for m in self.parent_view.any_members if m["name"] != self.user_name]
            self.parent_view.any_members.append(entry)
            
            for r, u in self.parent_view.members.items():
                if u == self.user_name: self.parent_view.members[r] = None
                
            self.parent_view.update_buttons()
            await interaction.response.edit_message(embed=self.parent_view.make_embed(), view=self.parent_view)
            
            # 満員チェック
            await self.parent_view.check_full_and_notify(interaction)
            
        except Exception as e:
            print(f"❌ Modal Error: {e}")
            traceback.print_exc()

# ------------------------------------------------------------------
# 最終的な募集パネル
# ------------------------------------------------------------------
class RecruitmentPanel(View):
    def __init__(self, data):
        super().__init__(timeout=None)
        self.data = data
        self.members = {}
        self.notified_full = False # 通知済みフラグ
        
        if "4" in data["type"] or "LIGHT" in data["type"]:
            self.max_members = 4
        else:
            self.max_members = 8

        if data["type"] == "LIGHT": roles = ["Tank", "Healer", "DPS1", "DPS2"]
        elif data["type"] == "FULL": roles = ["MT", "ST", "H1", "H2", "D1", "D2", "D3", "D4"]
        elif data["type"] == "FREE8": roles = [f"参加枠{i}" for i in range(1, 9)]
        else: roles = [f"参加枠{i}" for i in range(1, 5)]
        
        for r in roles: self.members[r] = None
        self.any_members = []

        author = data["author"]
        my_role = data["my_role"]
        
        if my_role and my_role != "None":
            if my_role == "Any":
                self.any_members.append({"name": author, "note": "主催者(All OK)"})
            elif my_role in self.members:
                self.members[my_role] = author
            elif "Tank" in my_role: 
                if "MT" in self.members: self.members["MT"] = author
            elif "参加枠" in my_role:
                 self.members["参加枠1"] = author

        self.update_buttons()

    def get_current_count(self):
        seated_count = sum(1 for u in self.members.values() if u is not None)
        any_count = len(self.any_members)
        return seated_count + any_count

    def is_user_joined(self, user_name):
        in_seat = user_name in self.members.values()
        in_any = any(m["name"] == user_name for m in self.any_members)
        return in_seat or in_any

    # 満員通知
    async def check_full_and_notify(self, interaction: discord.Interaction):
        if self.notified_full: return
        
        if self.get_current_count() >= self.max_members:
            self.notified_full = True
            author_id = self.data.get("author_id")
            if author_id:
                await interaction.channel.send(
                    f"<@{author_id}> 🎉 **メンバーが満員になりました！**\n出発準備をお願いします！"
                )

    def update_buttons(self):
        self.clear_items()
        
        current_total = self.get_current_count()
        is_full = current_total >= self.max_members

        # 1. ロールボタン
        for role, user in self.members.items():
            style = discord.ButtonStyle.secondary
            disabled = False
            
            if user:
                label = f"{role}: {user}"
                disabled = True
            else:
                label = role
                if role in ["MT", "ST"] or "Tank" in role: style = discord.ButtonStyle.primary
                elif role in ["H1", "H2"] or "Healer" in role: style = discord.ButtonStyle.success
                elif "D" in role: style = discord.ButtonStyle.danger
            
            emoji = get_emoji_safe(role)
            btn = Button(label=label, style=style, custom_id=f"rec_{role}", disabled=disabled, emoji=emoji)
            btn.callback = self.make_role_callback(role)
            self.add_item(btn)
        
        # 2. 調整枠ボタン
        any_label = "調整枠に入る"
        if is_full: any_label = "調整枠 (満員)"
        
        any_btn = Button(label=any_label, style=discord.ButtonStyle.secondary, custom_id="rec_any", emoji=get_emoji_safe("Any"))
        any_btn.callback = self.join_any_callback
        self.add_item(any_btn)

        # 3. 離脱ボタン
        leave_btn = Button(label="参加を取り消す", style=discord.ButtonStyle.secondary, custom_id="rec_leave", emoji="👋", row=4)
        leave_btn.callback = self.leave_callback
        self.add_item(leave_btn)

        # 4. 削除ボタン
        cancel = Button(label="募集を削除", style=discord.ButtonStyle.danger, custom_id="rec_delete", row=4)
        cancel.callback = self.cancel_callback
        self.add_item(cancel)

    # --- コールバック ---
    def make_role_callback(self, role):
        async def cb(interaction: discord.Interaction):
            try:
                user_name = interaction.user.display_name
                if not self.is_user_joined(user_name):
                    if self.get_current_count() >= self.max_members:
                        await interaction.response.send_message(f"❌ **満員です！**", ephemeral=True)
                        return

                for r, u in self.members.items():
                    if u == user_name: self.members[r] = None
                self.any_members = [m for m in self.any_members if m["name"] != user_name]

                self.members[role] = user_name
                self.update_buttons()
                await interaction.response.edit_message(embed=self.make_embed(), view=self)
                
                # 満員チェック
                await self.check_full_and_notify(interaction)
                
            except Exception as e:
                print(f"❌ Role Error: {e}")
                traceback.print_exc()
        return cb

    async def join_any_callback(self, interaction: discord.Interaction):
        try:
            user_name = interaction.user.display_name
            if not self.is_user_joined(user_name):
                if self.get_current_count() >= self.max_members:
                    await interaction.response.send_message(f"❌ **満員です！**", ephemeral=True)
                    return
            await interaction.response.send_modal(AnyRoleModal(self, user_name))
        except Exception as e:
            print(f"❌ Any Error: {e}")
            traceback.print_exc()

    async def leave_callback(self, interaction: discord.Interaction):
        try:
            user_name = interaction.user.display_name
            removed = False
            for r, u in self.members.items():
                if u == user_name:
                    self.members[r] = None
                    removed = True
            original_len = len(self.any_members)
            self.any_members = [m for m in self.any_members if m["name"] != user_name]
            if len(self.any_members) < original_len:
                removed = True

            if removed:
                self.notified_full = False # 通知リセット
                self.update_buttons()
                await interaction.response.edit_message(embed=self.make_embed(), view=self)
                await interaction.followup.send("参加を取り消しました！", ephemeral=True)
            else:
                await interaction.response.send_message("あなたはまだ参加していません！", ephemeral=True)
        except Exception as e:
            print(f"❌ Leave Error: {e}")
            traceback.print_exc()

    # ★修正: 募集削除と同時にスレッドを閉じる
    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user.display_name == self.data["author"]:
            # まずパネルを削除済みにする
            await interaction.response.edit_message(content="❌ **募集は削除されました。(スレッドを閉じます)**", embed=None, view=None)
            
            # スレッドならアーカイブしてロックする（お掃除機能）
            if isinstance(interaction.channel, discord.Thread):
                try:
                    await interaction.channel.edit(archived=True, locked=True)
                except Exception as e:
                    print(f"Failed to archive thread: {e}")
        else:
            await interaction.response.send_message("募集主しか削除できません！", ephemeral=True)

    def make_embed(self):
        total = self.get_current_count()
        status_text = f"現在の参加者: {total}/{self.max_members}人"
        
        embed = discord.Embed(title=f"⚔️ {self.data['content']}", color=discord.Color.orange())
        embed.set_author(name=status_text)
        
        info_text = (
            f"📍 **場所**: {self.data['dc']} / {self.data['world']}\n"
            f"⏰ **時間**: {self.data['time']}\n"
            f"📝 **メモ**: {self.data['comment']}\n"
            "━━━━━━━━━━━━━━━"
        )
        embed.description = info_text

        member_text = ""
        for r, u in self.members.items():
            icon = get_emoji_safe(r) or "▫️"
            if u:
                member_text += f"{icon} **{r}** : **`{u}`**\n"
            else:
                member_text += f"{icon} {r} : 　\n"

        if self.any_members:
            member_text += "\n**👑 調整・補欠 (Any):**\n"
            for m in self.any_members:
                member_text += f"┗ **{m['name']}** ({m['note']})\n"

        embed.add_field(name="👥 メンバー表", value=member_text, inline=False)
        embed.set_footer(text=f"主催: {self.data['author']}")
        return embed

# ------------------------------------------------------------------
# ウィザード
# ------------------------------------------------------------------
class ConfirmView(View):
    def __init__(self, data):
        super().__init__(timeout=180)
        self.data = data
    
    @discord.ui.button(label="投稿する！", style=discord.ButtonStyle.green)
    async def post(self, interaction: discord.Interaction, button: Button):
        forum_id = os.getenv("RECRUIT_FORUM_ID")
        channel = interaction.guild.get_channel(int(forum_id)) if forum_id else None
        if not channel:
            await interaction.response.send_message("❌ フォーラムIDエラー", ephemeral=True)
            return

        final_view = RecruitmentPanel(self.data)
        thread = await channel.create_thread(
            name=f"【募集】{self.data['content']} @{self.data['time']}",
            content=f"📢 **{self.data['content']}** 行くよ！",
            embed=final_view.make_embed(),
            view=final_view
        )
        
        chat_id = os.getenv("CHAT_CHANNEL_ID")
        role_id = os.getenv("ROLE_ID")
        if chat_id and role_id:
            chat_channel = interaction.guild.get_channel(int(chat_id))
            if chat_channel:
                await chat_channel.send(
                    f"<@&{role_id}> **{self.data['content']}** の募集が出たよ！\n"
                    f"参加する人はこっち！ -> {thread.thread.jump_url}"
                )
        await interaction.response.edit_message(content=f"✅ 募集を公開しました！\n{thread.thread.jump_url}", embed=None, view=None)

    @discord.ui.button(label="❌ やり直す", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="❌ キャンセルしました。", embed=None, view=None)

class DetailModal(Modal, title="詳細コメント"):
    comment = TextInput(label="自由コメント", style=discord.TextStyle.paragraph, placeholder="例: 初見です！マクロはGame8で！", required=False)
    def __init__(self, data):
        super().__init__()
        self.data = data

    async def on_submit(self, interaction: discord.Interaction):
        self.data["comment"] = self.comment.value
        embed = discord.Embed(title="最終確認", description="公開しますか？", color=discord.Color.blue())
        embed.add_field(name="コンテンツ", value=self.data["content"])
        role_disp = "調整(Any)" if self.data["my_role"] == "Any" else self.data["my_role"]
        embed.add_field(name="自分のロール", value=role_disp)
        embed.add_field(name="場所", value=f"{self.data['dc']} / {self.data['world']}")
        embed.add_field(name="時間", value=self.data["time"])
        embed.add_field(name="コメント", value=self.data["comment"])
        await interaction.response.edit_message(embed=embed, view=ConfirmView(self.data))

class LocationTimeView(View):
    def __init__(self, data):
        super().__init__(timeout=180)
        self.data = data
        self.temp_time = {"date": None, "hour": None, "minute": None}
        self.selections = {"dc": None, "world": None}
        self.init_dc_select()
        self.world_select = Select(placeholder="🔒 先にDCを選んでね", options=[discord.SelectOption(label="waiting...", value="dummy")], disabled=True, row=1)
        self.add_item(self.world_select)
        self.init_date_select()
        self.init_hour_select()
        self.init_minute_select()

    def init_dc_select(self):
        options = [discord.SelectOption(label=dc) for dc in JP_DCS.keys()]
        placeholder = f"🌐 {self.selections['dc']}" if self.selections['dc'] else "🌐 DCを選択"
        self.dc_select = Select(placeholder=placeholder, options=options, row=0)
        self.dc_select.callback = self.on_dc_select
        self.add_item(self.dc_select)

    def init_date_select(self):
        today = datetime.date.today()
        dates = []
        weekdays = ['月','火','水','木','金','土','日']
        for i in range(14):
            d = today + datetime.timedelta(days=i)
            label = f"{d.month}/{d.day} ({weekdays[d.weekday()]})"
            if i == 0: label += " [今日]"
            if i == 1: label += " [明日]"
            dates.append(discord.SelectOption(label=label, value=f"{d.year}/{d.month}/{d.day}"))
        placeholder = f"📅 {self.temp_time['date']}" if self.temp_time['date'] else "📅 日付を選択"
        self.date_select = Select(placeholder=placeholder, options=dates, row=2)
        self.date_select.callback = self.on_date_select
        self.add_item(self.date_select)

    def init_hour_select(self):
        hours = [discord.SelectOption(label=f"{h:02d}時", value=f"{h:02d}") for h in range(24)]
        placeholder = f"🕒 {self.temp_time['hour']}時" if self.temp_time['hour'] else "🕒 何時？"
        self.hour_select = Select(placeholder=placeholder, options=hours, row=3)
        self.hour_select.callback = self.on_hour_select
        self.add_item(self.hour_select)

    def init_minute_select(self):
        minutes = [discord.SelectOption(label=f"{m:02d}分", value=f"{m:02d}") for m in [0, 15, 30, 45]]
        placeholder = f"⏱ {self.temp_time['minute']}分" if self.temp_time['minute'] else "⏱ 何分？"
        self.minute_select = Select(placeholder=placeholder, options=minutes, row=4)
        self.minute_select.callback = self.on_minute_select
        self.add_item(self.minute_select)

    async def on_dc_select(self, interaction: discord.Interaction):
        selected_dc = self.dc_select.values[0]
        self.data["dc"] = selected_dc
        self.selections["dc"] = selected_dc
        self.remove_item(self.world_select)
        options = [discord.SelectOption(label=w) for w in JP_DCS[selected_dc]]
        self.world_select = Select(placeholder="🌍 Worldを選択", options=options, row=1)
        self.world_select.callback = self.on_world_select
        self.add_item(self.world_select)
        self.remove_item(self.dc_select)
        self.init_dc_select()
        await interaction.response.edit_message(view=self)

    async def on_world_select(self, interaction: discord.Interaction):
        self.data["world"] = self.world_select.values[0]
        self.selections["world"] = self.data["world"]
        self.world_select.placeholder = f"🌍 {self.data['world']}"
        await self.check_and_submit(interaction)

    async def on_date_select(self, interaction: discord.Interaction):
        self.temp_time["date"] = self.date_select.values[0]
        self.remove_item(self.date_select)
        self.init_date_select()
        await self.check_and_submit(interaction)

    async def on_hour_select(self, interaction: discord.Interaction):
        self.temp_time["hour"] = self.hour_select.values[0]
        self.remove_item(self.hour_select)
        self.init_hour_select()
        await self.check_and_submit(interaction)

    async def on_minute_select(self, interaction: discord.Interaction):
        self.temp_time["minute"] = self.minute_select.values[0]
        self.remove_item(self.minute_select)
        self.init_minute_select()
        await self.check_and_submit(interaction)

    async def check_and_submit(self, interaction: discord.Interaction):
        if "dc" in self.data and "world" in self.data and all(self.temp_time.values()):
            self.data["time"] = f"{self.temp_time['date']} {self.temp_time['hour']}:{self.temp_time['minute']}"
            await interaction.response.send_modal(DetailModal(self.data))
        else:
            await interaction.response.edit_message(view=self)

class OwnerRoleSelectView(View):
    def __init__(self, data):
        super().__init__(timeout=180)
        self.data = data
        if data["type"] == "FULL": roles = ["MT", "ST", "H1", "H2", "D1", "D2", "D3", "D4"]
        else: roles = ["Tank", "Healer", "DPS1", "DPS2"]
            
        for role in roles:
            style = discord.ButtonStyle.secondary
            if "MT" in role or "ST" in role or "Tank" in role: style = discord.ButtonStyle.primary
            elif "H" in role or "Healer" in role: style = discord.ButtonStyle.success
            elif "D" in role or "DPS" in role: style = discord.ButtonStyle.danger
            
            emoji = get_emoji_safe(role)
            btn = Button(label=role, style=style, emoji=emoji)
            btn.callback = self.make_callback(role)
            self.add_item(btn)

        any_btn = Button(label="👑 調整 (Any)", style=discord.ButtonStyle.secondary, emoji=get_emoji_safe("Any"), row=2)
        any_btn.callback = self.make_callback("Any")
        self.add_item(any_btn)

    def make_callback(self, role):
        async def cb(interaction: discord.Interaction):
            self.data["my_role"] = role
            msg = "あなたは **調整枠** ですね！" if role == "Any" else f"あなたは **{role}** ですね！"
            await interaction.response.edit_message(content=f"{msg}\n次は場所と日時を選んでください。", view=LocationTimeView(self.data))
        return cb

class TypeSelectView(View):
    def __init__(self, content_name, author_name, author_id):
        super().__init__(timeout=180)
        self.data = {"content": content_name, "author": author_name, "author_id": author_id, "type": None, "my_role": "None"}
    
    @discord.ui.select(placeholder="募集タイプ", options=[
        discord.SelectOption(label="FULL PARTY (ロール指定あり)", value="FULL", description="討滅戦やレイドに行くならこれ！"),
        discord.SelectOption(label="LIGHT PARTY (ロール指定あり)", value="LIGHT", description="IDやヴァリアントダンジョンに行くならこれ！"),
        discord.SelectOption(label="FULL PARTY (誰でも)", value="FREE8", description="SS撮影会でもするかい？"),
        discord.SelectOption(label="LIGHT PARTY (誰でも)", value="FREE4", description="FLに行く準備は出来たかな？ルレ募集もこれがおすすめ！"),
    ])
    async def on_type(self, interaction: discord.Interaction, select: Select):
        self.data["type"] = select.values[0]
        if "FREE" in self.data["type"]:
            self.data["my_role"] = "参加枠1"
            await interaction.response.edit_message(content="場所と日時を選んでください！", view=LocationTimeView(self.data))
        else:
            await interaction.response.edit_message(content="あなたのロールを選んでください！", view=OwnerRoleSelectView(self.data))

class PartyFinder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="pfinder", description="募集を作成します（非公開で作成）")
    @app_commands.rename(content_name="コンテンツ名") 
    async def pfinder(self, interaction: discord.Interaction, content_name: str):
        await interaction.response.send_message(
            f"「{content_name}」の募集を作成します。\nまずはタイプを選んでください。", 
            view=TypeSelectView(content_name, interaction.user.display_name, interaction.user.id), 
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(PartyFinder(bot))