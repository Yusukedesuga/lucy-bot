import discord
from discord.ext import commands
from discord.ui import Button, View
import os

# --- パネルの見た目を作るクラス（ここは変更なし） ---
class RecruitmentView(View):
    def __init__(self, author_name, content_name, time_str, comment, recruit_type, author_role):
        super().__init__(timeout=None)
        self.author_name = author_name
        self.content_name = content_name
        self.time_str = time_str
        self.comment = comment
        self.recruit_type = recruit_type
        
        # 枠の初期化
        if recruit_type == "LIGHT":
            self.members = {"Tank": None, "Healer": None, "DPS1": None, "DPS2": None}
        elif recruit_type == "FREE8":
            self.members = {f"参加枠{i}": None for i in range(1, 9)}
        elif recruit_type == "FREE4":
            self.members = {f"参加枠{i}": None for i in range(1, 5)}
        else: # FULL
            self.members = {
                "MT": None, "ST": None, "H1": None, "H2": None, 
                "D1": None, "D2": None, "D3": None, "D4": None
            }

        # 主催者の自動着席
        if author_role and author_role != "None":
            if author_role in self.members:
                self.members[author_role] = author_name
            else:
                if recruit_type == "FULL":
                    if "Tank" in author_role: self.members["MT"] = author_name
                    elif "Healer" in author_role: self.members["H1"] = author_name
                    elif "DPS" in author_role: self.members["D1"] = author_name

        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        for role, user in self.members.items():
            label = f"{role}: {user}" if user else f"{role} に参加"
            style = discord.ButtonStyle.secondary
            if not user:
                if "Tank" in role or role in ["MT", "ST"]: style = discord.ButtonStyle.primary
                elif "Healer" in role or role in ["H1", "H2"]: style = discord.ButtonStyle.success
                elif "DPS" in role or role in ["D1", "D2", "D3", "D4"]: style = discord.ButtonStyle.danger
                else: style = discord.ButtonStyle.primary
            else:
                style = discord.ButtonStyle.secondary

            button = Button(label=label, style=style, custom_id=role, disabled=(user is not None))
            button.callback = self.create_callback(role)
            self.add_item(button)
        
        cancel_btn = Button(label="❌ キャンセル", style=discord.ButtonStyle.secondary, custom_id="cancel")
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

    def create_callback(self, role):
        async def callback(interaction: discord.Interaction):
            user_name = interaction.user.display_name
            for r, u in self.members.items():
                if u == user_name: self.members[r] = None
            self.members[role] = user_name
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        return callback

    async def cancel_callback(self, interaction: discord.Interaction):
        user_name = interaction.user.display_name
        for r, u in self.members.items():
            if u == user_name: self.members[r] = None
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    def create_embed(self):
        color_map = {"FULL": 0xff9900, "LIGHT": 0x00b0f4, "FREE8": 0xeb459e, "FREE4": 0xeb459e}
        embed_color = color_map.get(self.recruit_type, 0xff9900)
        
        embed = discord.Embed(title=f"⚔️ 募集中: {self.content_name}", color=embed_color)
        embed.add_field(name="⏰ 時間", value=self.time_str, inline=True)
        embed.add_field(name="📝 コメント", value=self.comment, inline=True)
        
        member_list = ""
        for role, user in self.members.items():
            status = f"**{user}**" if user else "(募集中...)"
            icon = "👤"
            if "Tank" in role or role in ["MT", "ST"]: icon = "🛡️"
            elif "Healer" in role or role in ["H1", "H2"]: icon = "🏥"
            elif "DPS" in role or role in ["D1", "D2", "D3", "D4"]: icon = "⚔️"
            member_list += f"{icon} **{role}**: {status}\n"
            
        embed.add_field(name="現在のメンバー", value=member_list, inline=False)
        embed.set_footer(text=f"主催: {self.author_name} | タイプ: {self.recruit_type}")
        return embed

# --- ★ここから下：募集機能を管理する Cog ---
class PartyFinder(commands.Cog):  # クラス名も PartyFinder に変更！
    def __init__(self, bot):
        self.bot = bot
        try:
            self.forum_id = int(os.getenv("RECRUIT_FORUM_ID"))
            self.chat_id = int(os.getenv("CHAT_CHANNEL_ID"))
            self.role_id = int(os.getenv("ROLE_ID"))
        except:
            print("⚠️ PartyFinder Cog: ID Load Error")

    # シェフ(chat.py)からの「recruit_request」を受け取る部分
    @commands.Cog.listener()
    async def on_recruit_request(self, message, content, time_str, comment, recruit_type, author_role):
        forum_channel = self.bot.get_channel(self.forum_id)
        chat_channel = self.bot.get_channel(self.chat_id)

        if forum_channel and chat_channel:
            view = RecruitmentView(message.author.display_name, content, time_str, comment, recruit_type, author_role)
            embed = view.create_embed()
            
            thread = await forum_channel.create_thread(
                name=f"【募集中】{content} @{time_str}",
                content=f"参加ボタンを押してね！",
                embed=embed,
                view=view
            )
            
            notification = f"<@&{self.role_id}> **{content}** の募集が出たよ！\n参加する人はこっち！ -> {thread.thread.jump_url}"
            await chat_channel.send(notification)
            
            role_msg = f"（**{author_role}** に入れておいたよ！）" if author_role and author_role != "None" else ""
            await message.reply(f"完了！募集タイプ **{recruit_type}** で作成しました！{role_msg}📢")
        else:
            await message.reply("IDの設定を確認してね！")

async def setup(bot):
    await bot.add_cog(PartyFinder(bot))
