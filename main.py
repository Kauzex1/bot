from keep_alive import keep_alive
import discord
from discord.ext import tasks
from discord import app_commands
import requests
import os
import json

# --- CẤU HÌNH ---
TOKEN = os.getenv("DISCORD_TOKEN")
DB_FILE = "sale_history.json"
CONFIG_FILE = "bot_config.json"
GUILD_CONFIGS = "guild_configs.json"
ROLE_NAME = "Sale Hunter"

PAYPAL_LINK = "https://paypal.me/HieuNguyen73" 
MOMO_QR_URL = "https://your-momo-qr-link.png" # Sư Huynh dán link ảnh QR MoMo vào đây

# --- DỮ LIỆU NGÔN NGỮ ---
LANGUAGES = {
    "vi": {
        "tag_msg": "🔔 {mention}! Có kèo thơm mới từ Steam!",
        "role_btn": "Theo Dõi Kèo Sale",
        "role_ok": "🚀 Đã nhận Role **{role}**!",
        "role_remove": "✅ Đã hủy theo dõi.",
        "summary_title": "🚀 DANH SÁCH KÈO SALE MỚI",
        "summary_desc": "Phát hiện các cực phẩm vừa lên sàn:",
        "price_label": "💰 Giá",
        "rating_label": "Đánh giá",
        "link_label": "🔗 Liên kết",
        "browser": "Trình Duyệt",
        "app_steam": "App Steam",
        "run_msg": "🔄 Đang bắt đầu quét sale...",
        "coming_soon_title": "📅 GAME SẮP RA MẮT ĐÁNG CHÚ Ý",
        "release_date": "📅 Ngày ra mắt",
        "no_new_deals": "Hiện không có kèo mới phù hợp bộ lọc.",
        "settings_title": "⚙️ BẢNG ĐIỀU KHIỂN BOT",
        "settings_desc": "Tùy chỉnh hệ thống.\n\n**Ngôn ngữ:** {lang}\n**Giá tối đa:** ${price:.2f}",
        "set_price_btn": "Chỉnh Giá USD",
        "modal_title": "Cấu hình giá tiền",
        "modal_label": "Nhập giá USD tối đa",
        "filter_set": "✅ Đã cập nhật mức giá tối đa: ${price:.2f}",
        "set_channel_ok": "✅ Đã thiết lập kênh báo kèo tại đây!",
        "setup_req": "❌ Vui lòng dùng lệnh `/setup_channel` trước!",
        "donate_title": "☕ Ủng Hộ Sư Huynh Hiếu",
        "donate_desc": "Mời tôi một ly cà phê để duy trì Bot nhé!",
        "donate_paypal": "PayPal (Quốc tế)"
    },
    "en": {
        "tag_msg": "🔔 {mention}! New hot deals found on Steam!",
        "role_btn": "Follow Sale Deals",
        "role_ok": "🚀 Role **{role}** assigned!",
        "role_remove": "✅ Unfollowed successfully.",
        "summary_title": "🚀 NEW SALE DEALS FOUND",
        "summary_desc": "New premium deals just listed:",
        "price_label": "💰 Price",
        "rating_label": "Rating",
        "link_label": "🔗 Links",
        "browser": "Browser",
        "app_steam": "Steam App",
        "run_msg": "🔄 Starting sale scan...",
        "coming_soon_title": "📅 NOTABLE UPCOMING GAMES",
        "release_date": "📅 Release Date",
        "no_new_deals": "No new deals found matching your filter.",
        "settings_title": "⚙️ BOT CONTROL PANEL",
        "settings_desc": "Customize settings.\n\n**Language:** {lang}\n**Max Price:** ${price:.2f}",
        "set_price_btn": "Set USD Price",
        "modal_title": "Price Configuration",
        "modal_label": "Enter max USD price",
        "filter_set": "✅ Maximum price updated to: ${price:.2f}",
        "set_channel_ok": "✅ Notification channel set successfully!",
        "setup_req": "❌ Please use `/setup_channel` first!",
        "donate_title": "☕ Support Kirosa",
        "donate_desc": "Buy me a coffee to keep the bot running!",
        "donate_paypal": "Support via PayPal"
    }
}

# --- HÀM TIỆN ÍCH ---
def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding='utf-8') as f:
            try: return json.load(f)
            except: return default
    return default

def save_json(filename, data):
    with open(filename, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- CÁC LỚP GIAO DIỆN (UI) ---
class DonateView(discord.ui.View):
    def __init__(self, lang):
        super().__init__(timeout=60)
        self.add_item(discord.ui.Button(label=LANGUAGES[lang]["donate_paypal"], url=PAYPAL_LINK, emoji="💳"))

class PriceModal(discord.ui.Modal):
    def __init__(self, bot_obj):
        lang = bot_obj.config["lang"]
        super().__init__(title=LANGUAGES[lang]["modal_title"])
        self.bot_obj = bot_obj
        self.price_input = discord.ui.TextInput(
            label=LANGUAGES[lang]["modal_label"],
            placeholder="15.0",
            default=str(bot_obj.config["max_price_usd"]),
            min_length=1, max_length=5
        )
        self.add_item(self.price_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = float(self.price_input.value)
            self.bot_obj.config["max_price_usd"] = val
            save_json(CONFIG_FILE, self.bot_obj.config)
            await interaction.response.send_message(LANGUAGES[self.bot_obj.config["lang"]]["filter_set"].format(price=val), ephemeral=True)
        except:
            await interaction.response.send_message("❌ Error!", ephemeral=True)

class SettingsView(discord.ui.View):
    def __init__(self, bot_obj):
        super().__init__(timeout=60)
        self.bot_obj = bot_obj
        lang = bot_obj.config["lang"]
        btn = discord.ui.Button(label=LANGUAGES[lang]["set_price_btn"], style=discord.ButtonStyle.primary, emoji="💵")
        btn.callback = self.set_price_callback
        self.add_item(btn)

    async def set_price_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PriceModal(self.bot_obj))

    @discord.ui.select(
        placeholder="Language",
        options=[
            discord.SelectOption(label="Tiếng Việt", value="vi", emoji="🇻🇳"),
            discord.SelectOption(label="English", value="en", emoji="🇺🇸")
        ]
    )
    async def select_lang(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.bot_obj.config["lang"] = select.values[0]
        save_json(CONFIG_FILE, self.bot_obj.config)
        await interaction.response.send_message("✅ OK!", ephemeral=True)

class RoleView(discord.ui.View):
    def __init__(self, lang):
        super().__init__(timeout=None)
        self.lang = lang
        self.children[0].label = LANGUAGES[lang]["role_btn"]

    @discord.ui.button(style=discord.ButtonStyle.success, custom_id="role_v15", emoji="🔔")
    async def toggle_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name=ROLE_NAME)
        if not role:
            role = await interaction.guild.create_role(name=ROLE_NAME, color=discord.Color.gold(), mentionable=True)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(LANGUAGES[self.lang]["role_remove"], ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(LANGUAGES[self.lang]["role_ok"].format(role=ROLE_NAME), ephemeral=True)

# --- CLASS CHÍNH CỦA BOT ---
class SteamSaleBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.config = load_json(CONFIG_FILE, {"lang": "vi", "max_price_usd": 60.0})
        self.history = load_json(DB_FILE, {})
        self.guilds_data = load_json(GUILD_CONFIGS, {})

    async def setup_hook(self):
        self.add_view(RoleView(self.config["lang"]))
        self.check_sales.start()

    async def on_ready(self):
        await self.tree.sync()
        activity = discord.Activity(type=discord.ActivityType.watching, name="Steam Sale cùng Kirosa")
        await self.change_presence(activity=activity)
        print(f'✅ Bot Ready!')

    async def do_scan(self, manual_guild=None):
        lang = self.config["lang"]
        max_p = self.config["max_price_usd"]
        api_lang = "vietnamese" if lang == "vi" else "english"
        
        try:
            res = requests.get(f"https://store.steampowered.com/api/featuredcategories/?l={api_lang}&cc=US").json()
            specials = res.get('specials', {}).get('items', [])
            
            # === BẮT ĐẦU LOGIC DỌN DẸP JSON ===
            current_sale_ids = [str(g['id']) for g in specials]
            expired_ids = [gid for gid in self.history.keys() if gid not in current_sale_ids]
            for gid in expired_ids:
                del self.history[gid]
            # === KẾT THÚC DỌN DẸP ===

            new_games = [g for g in specials if str(g['id']) not in self.history and (g.get('final_price', 0)/100) <= max_p]
            
            if not new_games: return False

            target_guilds = {str(manual_guild.id): self.guilds_data[str(manual_guild.id)]} if manual_guild else self.guilds_data

            # 1. GỬI BẢNG TỔNG HỢP
            summary = discord.Embed(title=LANGUAGES[lang]["summary_title"], color=discord.Color.red())
            summary.description = LANGUAGES[lang]["summary_desc"] + "\n\n" + "\n".join(
                [f"{i+1}. **{g['name']}** (-{g['discount_percent']}%) - `${(g['final_price']/100):.2f}`" for i, g in enumerate(new_games[:15])]
            )
            
            for gid, cid in target_guilds.items():
                chan = self.get_channel(int(cid))
                if chan:
                    role = discord.utils.get(chan.guild.roles, name=ROLE_NAME)
                    await chan.send(content=LANGUAGES[lang]["tag_msg"].format(mention=role.mention if role else f"@{ROLE_NAME}"), embed=summary, view=RoleView(lang))

            # 2. GỬI CHI TIẾT GAME
            for g in new_games[:5]:
                g_id = str(g['id'])
                review_api = f"https://store.steampowered.com/appreviews/{g_id}?json=1&language=all"
                review_res = requests.get(review_api).json()
                
                query_summary = review_res.get('query_summary', {})
                pos = query_summary.get('total_positive', 0)
                total = query_summary.get('total_reviews', 0)
                
                if total > 0:
                    real_score = round((pos / total) * 10, 1)
                    rating_display = f"{real_score}/10 ⭐"
                else:
                    rating_display = "N/A ⭐"

                d_res = requests.get(f"https://store.steampowered.com/api/appdetails?appids={g_id}&cc=US&l={api_lang}").json()
                if d_res and d_res[g_id]['success']:
                    info = d_res[g_id]['data']
                    embed = discord.Embed(
                        title=f"🎮 {info['name']}", 
                        description=info.get('short_description', 'No description available.'),
                        url=f"https://store.steampowered.com/app/{g_id}", 
                        color=discord.Color.blue()
                    )
                    p = info.get('price_overview', {})
                    price_text = f"~~{p.get('initial_formatted')}~~ **{p.get('final_formatted')}** (-{p.get('discount_percent')}%)"
                    embed.add_field(name=LANGUAGES[lang]["price_label"], value=price_text, inline=True)
                    embed.add_field(name=LANGUAGES[lang]["rating_label"], value=f"**{rating_display}**", inline=True)
                    
                    genres = ", ".join([gen['description'] for gen in info.get('genres', [])[:3]])
                    if genres:
                        embed.add_field(name="🏷️ Thể loại", value=genres, inline=False)
                    
                    embed.set_image(url=info.get('header_image'))
                    embed.set_footer(text="via Sale Steam |•© Kirosa")

                    view = discord.ui.View()
                    view.add_item(discord.ui.Button(label=LANGUAGES[lang]["browser"], url=embed.url, emoji="🌐"))
                    view.add_item(discord.ui.Button(label=LANGUAGES[lang]["app_steam"], url=f"https://freestuffbot.xyz/ext/open-client/steam/{g_id}", emoji="🎮"))

                    for gid, cid in target_guilds.items():
                        chan = self.get_channel(int(cid))
                        if chan: await chan.send(embed=embed, view=view)
                
                if not manual_guild: self.history[g_id] = True
            
            if not manual_guild: save_json(DB_FILE, self.history)
            return True
        except Exception as e:
            print(f"Error scan: {e}")
            return False

    @tasks.loop(hours=24)
    async def check_sales(self): 
        await self.do_scan()

bot = SteamSaleBot()

# --- LỆNH SLASH COMMANDS ---
@bot.tree.command(name="setup_channel", description="Thiết lập kênh báo kèo")
@app_commands.checks.has_permissions(administrator=True)
async def setup_channel(interaction: discord.Interaction):
    bot.guilds_data[str(interaction.guild_id)] = interaction.channel_id
    save_json(GUILD_CONFIGS, bot.guilds_data)
    await interaction.response.send_message(LANGUAGES[bot.config["lang"]]["set_channel_ok"], ephemeral=True)

@bot.tree.command(name="settings", description="Bảng điều khiển Bot")
async def settings(interaction: discord.Interaction):
    lang = bot.config["lang"]
    embed = discord.Embed(title=LANGUAGES[lang]["settings_title"], color=discord.Color.green())
    embed.description = LANGUAGES[lang]["settings_desc"].format(lang="Tiếng Việt" if lang=="vi" else "English", price=bot.config["max_price_usd"])
    await interaction.response.send_message(embed=embed, view=SettingsView(bot), ephemeral=True)

@bot.tree.command(name="donate", description="Ủng hộ Bot")
async def donate(interaction: discord.Interaction):
    lang = bot.config["lang"]
    embed = discord.Embed(title=LANGUAGES[lang]["donate_title"], description=LANGUAGES[lang]["donate_desc"], color=discord.Color.gold())
    embed.set_image(url=MOMO_QR_URL)
    await interaction.response.send_message(embed=embed, view=DonateView(lang), ephemeral=True)

@bot.tree.command(name="run", description="Quét sale ngay")
async def run(interaction: discord.Interaction):
    if str(interaction.guild_id) not in bot.guilds_data:
        return await interaction.response.send_message(LANGUAGES[bot.config["lang"]]["setup_req"], ephemeral=True)
    await interaction.response.send_message(LANGUAGES[bot.config["lang"]]["run_msg"], ephemeral=True)
    await bot.do_scan(manual_guild=interaction.guild)

@bot.tree.command(name="coming_soon", description="Game sắp ra mắt")
async def coming_soon(interaction: discord.Interaction):
    await interaction.response.defer()
    res = requests.get(f"https://store.steampowered.com/api/featuredcategories/?cc=US").json()
    for g in res.get('coming_soon', {}).get('items', [])[:3]:
        embed = discord.Embed(title=g['name'], color=discord.Color.gold())
        embed.set_image(url=g.get('header_image'))
        embed.add_field(name=LANGUAGES[bot.config["lang"]]["release_date"], value=f"`{g.get('release_date', 'TBA')}`")
        embed.set_footer(text="via Sale Steam |•© Kirosa")
        await interaction.followup.send(embed=embed)

# --- CHÈN ĐOẠN DEBUG NÀY VÀO TRƯỚC keep_alive() ---
if TOKEN is None:
    print("❌ LỖI LỚN: Render KHÔNG tìm thấy biến môi trường DISCORD_TOKEN!")
else:
    print(f"✅ Render ĐÃ ĐỌC được Token! Bắt đầu với: {TOKEN[:5]}... | Độ dài: {len(TOKEN)} ký tự.")
# ---------------------------------------------------

keep_alive()
bot.run(TOKEN)
