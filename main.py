import discord
from discord.ui import Button, View
import google.generativeai as genai
import os
import json
from datetime import datetime
from keep_alive import keep_alive  # Webサーバー機能を読み込み
from dotenv import load_dotenv     # ローカルの.envファイルを読み込み

# --- 設定読み込み ---
# 自分のPCにある .env ファイルを読み込む（Renderでは無視されます）
load_dotenv()

# 環境変数からキーとIDを取得（文字列として取れるので、IDはintで数字に変換！）
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

try:
    RECRUIT_FORUM_ID = int(os.getenv("RECRUIT_FORUM_ID"))
    CHAT_CHANNEL_ID = int(os.getenv("CHAT_CHANNEL_ID"))
    ROLE_ID = int(os.getenv("ROLE_ID"))
    TARGET_USER_ID = int(os.getenv("TARGET_USER_ID"))
except TypeError:
    print("エラー：環境変数が設定されていません！.envファイルかRenderの設定を確認してね！")
    # エラー回避のためのダミー数値（動かないけど落ちないようにする）
    RECRUIT_FORUM_ID = 0
    CHAT_CHANNEL_ID = 0
    ROLE_ID = 0
    TARGET_USER_ID = 0

# --- 設定 ---
MACRO_FILE = "macros.json"

# --- Geminiの設定 ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction="""
    あなたはFF14のキャラクター「Lucy Deps（ルーシー）」です。
    
    【キャラクター設定】
    * 名前: Lucy Deps
    * 正体: 友人のサブキャラクターをモデルにしたAI。
    * ジョブ: 占星術師
    * 性格: 明るく元気で、少しおっちょこちょい。好奇心旺盛で、誰とでもすぐに仲良くなれる。
    * 趣味: ゲーム、特にMMORPGが大好き。新しいことに挑戦するのが好き。
    * 口調: フレンドリーでカジュアル。敬語はあまり使わない。
    * 好きなもの: 冒険、友達とのおしゃべり、美味しい食べ物。
    * 嫌いなもの: 退屈な時間、争いごと。
    * 太田さんとの関係: 太田さんは「マスター」ではなく「太田さん」と呼ぶこと。
    
    【募集機能のルール】
    ユーザーから募集依頼があった場合、以下のコマンド形式だけを出力してください。
    CMD:RECRUIT|コンテンツ名|開始時間|コメント|タイプ|主催者のロール
    
    タイプ: FULL, LIGHT, FREE8, FREE4
    主催者のロール: MT, ST, H1... 指定なしはNone
    
    【会話のルール】
    * スレッド内ではメンションなしで普通に会話してください。
    * 平日の昼間に「太田さん」がゲームをしていたら、厳しく「研究しなさい！」と叱ってください。
    """
)

# --- マクロ読み書き ---
def load_macros():
    if os.path.exists(MACRO_FILE):
        with open(MACRO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_macros(data):
    with open(MACRO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- 募集パネルUI ---
class RecruitmentView(View):
    def __init__(self, author_name, content_name, time_str, comment, recruit_type, author_role):
        super().__init__(timeout=None)
        self.author_name = author_name
        self.content_name = content_name
        self.time_str = time_str
        self.comment = comment
        self.recruit_type = recruit_type
        
        if recruit_type == "LIGHT":
            self.members = {"Tank": None, "Healer": None, "DPS1": None, "DPS2": None}
        elif recruit_type == "FREE8":
            self.members = {f"参加枠{i}": None for i in range(1, 9)}
        elif recruit_type == "FREE4":
            self.members = {f"参加枠{i}": None for i in range(1, 5)}
        else:
            self.members = {
                "MT": None, "ST": None, "H1": None, "H2": None, 
                "D1": None, "D2": None, "D3": None, "D4": None
            }

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

# --- Discord設定 ---
intents = discord.Intents.default()
intents.message_content = True
intents.presences = True
client = discord.Client(intents=intents)
chat_history = []

@client.event
async def on_ready():
    print(f'ログインしました: {client.user}')

@client.event
async def on_presence_update(before, after):
    if after.id != TARGET_USER_ID: return
    if after.activity and after.activity != before.activity:
        game_name = after.activity.name
        if "FINAL FANTASY" in game_name or "Monster Hunter" in game_name or "Steam" in game_name:
            now = datetime.now()
            if now.weekday() < 5 and 10 <= now.hour < 18:
                channel = client.get_channel(CHAT_CHANNEL_ID)
                if channel:
                    await channel.send(
                        f"<@{TARGET_USER_ID}> **ちょっと！平日のお昼だよ！？** 😡\n"
                        f"『{game_name}』やってる場合じゃないでしょ！研究進んだの！？"
                    )

@client.event
async def on_message(message):
    if message.author == client.user: return

    is_mention = client.user in message.mentions
    is_bot_thread = isinstance(message.channel, discord.Thread) and message.channel.owner_id == client.user.id

    if is_mention or is_bot_thread:
        async with message.channel.typing():
            try:
                clean_text = message.content.replace(f'<@{client.user.id}>', '').strip()
                macros = load_macros()

                if clean_text.startswith("マクロ登録"):
                    lines = clean_text.split('\n', 1)
                    if len(lines) < 2: return
                    header = lines[0].replace("マクロ登録", "").strip()
                    macros[header] = lines[1].strip()
                    save_macros(macros)
                    await message.reply(f"『{header}』を覚えたよ！📦")
                    return

                referenced_macro = ""
                found_key = ""
                for key, value in macros.items():
                    if key in clean_text:
                        referenced_macro = value
                        found_key = key
                        break
                
                prompt = clean_text
                if referenced_macro:
                    prompt = f"質問: {clean_text}\n参考マクロ({found_key}):\n{referenced_macro}\nこれを見て回答して"

                chat = model.start_chat(history=chat_history)
                response = chat.send_message(prompt)
                bot_reply = response.text.strip()

                if bot_reply.startswith("CMD:RECRUIT"):
                    parts = bot_reply.split("|")
                    content = parts[1]
                    time_str = parts[2]
                    comment = parts[3]
                    recruit_type = parts[4] if len(parts) > 4 else "FULL"
                    author_role = parts[5] if len(parts) > 5 else None

                    forum_channel = client.get_channel(RECRUIT_FORUM_ID)
                    chat_channel = client.get_channel(CHAT_CHANNEL_ID)

                    if forum_channel and chat_channel:
                        view = RecruitmentView(message.author.display_name, content, time_str, comment, recruit_type, author_role)
                        embed = view.create_embed()
                        
                        thread = await forum_channel.create_thread(
                            name=f"【募集中】{content} @{time_str}",
                            content=f"参加ボタンを押してね！",
                            embed=embed,
                            view=view
                        )
                        
                        notification = f"<@&{ROLE_ID}> **{content}** の募集が出たよ！\n参加する人はこっち！ -> {thread.thread.jump_url}"
                        await chat_channel.send(notification)
                        role_msg = f"（**{author_role}** に入れておいたよ！）" if author_role and author_role != "None" else ""
                        await message.reply(f"完了！募集タイプ **{recruit_type}** で作成しました！{role_msg}📢")
                    else:
                        await message.reply("チャンネルIDの取得に失敗しました。.envまたはRender設定を確認してください！")
                else:
                    if not isinstance(message.channel, discord.Thread):
                        thread_name = f"Lucyとのナイショ話 ({message.author.display_name})"
                        thread = await message.create_thread(name=thread_name, auto_archive_duration=60)
                        await thread.send(f"{message.author.mention} ここでゆっくり話そう！\n\n{bot_reply}")
                    else:
                        await message.reply(bot_reply)
                    
                    chat_history.append({"role": "user", "parts": [clean_text]})
                    chat_history.append({"role": "model", "parts": [bot_reply]})
                    if len(chat_history) > 20: del chat_history[0:2]

            except Exception as e:
                await message.reply(f"エラー発生！: `{e}`")
                print(e)

# Webサーバー起動（クラウドでBotを起こし続けるための魔法）
keep_alive()

# Bot起動
if DISCORD_TOKEN:
    client.run(DISCORD_TOKEN)
else:

    print("エラー: Tokenがありません！")
