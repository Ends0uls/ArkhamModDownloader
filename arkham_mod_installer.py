import os
import re
import shutil
import subprocess
import sys
import time

# ============================================================
# AUTO-INSTALL DEPENDENCIES
# ============================================================
try:
    import requests
    from tqdm import tqdm
except ImportError:
    print("[Setup] Missing required packages. Installing 'requests' and 'tqdm'...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "tqdm"])
    import requests
    from tqdm import tqdm

# ============================================================
# CONFIGURATION
# ============================================================

API_KEY   = "ApiKeyHere"
MODS_FILE = "mods.txt"
SEVENZIP  = r"C:\Program Files\7-Zip\7z.exe"

BASE_DIR      = r"C:\AKMods"
DOWNLOAD_DIR  = os.path.join(BASE_DIR, "downloads")
EXTRACT_DIR   = os.path.join(BASE_DIR, "extracted")
MISC_MODS_DIR = os.path.join(BASE_DIR, "misc_mods")

GAME_CONFIGS = {
    "batmanarkhamknight": {
        "nexus_game":   "batmanarkhamknight",
        "dlc_install":  r"C:\Program Files (x86)\Steam\steamapps\common\Batman Arkham Knight\DLC\356474",
        "misc_name":    "Batman Arkham Knight",
        "type":         "knight",
    },
    "batmanarkhamorigins": {
        "nexus_game":   "batmanarkhamorigins",
        "dlc_install":  r"C:\Program Files (x86)\Steam\steamapps\common\Batman Arkham Origins\SinglePlayer\DLC\257070",
        "misc_name":    "Batman Arkham Origins",
        "type":         "origins",
    },
    "batmanarkhamcity": {
        "nexus_game":   "batmanarkhamcity",
        "dlc_install":  r"C:\Program Files (x86)\Steam\steamapps\common\Batman Arkham City GOTY",
        "misc_name":    "Batman Arkham City",
        "type":         "city",
        "pcgame_ini":   r"C:\Program Files (x86)\Steam\steamapps\common\Batman Arkham City GOTY\BmGame\Config\PC\PCGame.ini",
    },
}

SKIP_CATEGORIES = {"archive", "old_version", "oldversion", "archived", "old version"}

API_DELAY = 1.5
DL_DELAY  = 1.0

# ============================================================
# SETUP
# ============================================================

for _dir in [DOWNLOAD_DIR, EXTRACT_DIR]:
    os.makedirs(_dir, exist_ok=True)

session = requests.Session()
session.headers.update({"apikey": API_KEY, "Accept": "application/json"})

# ============================================================
# URL PARSING & API HELPERS
# ============================================================

def parse_nexus_url(url):
    pattern = r"nexusmods\.com/([a-z0-9]+)/mods/(\d+)"
    match = re.search(pattern, url.lower())
    return (match.group(1), match.group(2)) if match else (None, None)

def resolve_game_config(slug):
    return GAME_CONFIGS.get(slug)

def api_get(url, retries=3):
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 60))
                print(f"  [Rate limit] Waiting {wait}s...")
                time.sleep(wait)
                continue
            if r.status_code == 200:
                return r.json()
            print(f"  [API] HTTP {r.status_code} — {url}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"  [API] Request error (attempt {attempt + 1}): {e}")
            time.sleep(5)
    return None

def get_mod_files(nexus_game, mod_id):
    time.sleep(API_DELAY)
    data = api_get(f"https://api.nexusmods.com/v1/games/{nexus_game}/mods/{mod_id}/files.json")
    return data.get("files", []) if data else []

def get_download_link(nexus_game, mod_id, file_id):
    time.sleep(API_DELAY)
    data = api_get(f"https://api.nexusmods.com/v1/games/{nexus_game}/mods/{mod_id}/files/{file_id}/download_link.json")
    if data:
        try:
            return data[0]["URI"]
        except (IndexError, KeyError):
            pass
    return None

def classify_file(f):
    category = f.get("category_name", "").lower().strip()
    for skip in SKIP_CATEGORIES:
        if skip in category:
            return "skip"
    if "main" in category:
        return "main"
    if "optional" in category or "misc" in category or "supplemental" in category:
        return "optional"
    return "skip"

def get_latest_main_files(files):
    candidates = [f for f in files if classify_file(f) == "main"]
    if not candidates:
        return []
    # Sort them by ID just in case, newest first, but return ALL of them
    candidates.sort(key=lambda x: x.get("file_id", 0), reverse=True)
    return candidates

# ============================================================
# DOWNLOAD & EXTRACTION
# ============================================================

def download_file(url, filename, dest_dir):
    dest_path = os.path.join(dest_dir, filename)
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        print(f"  [Skip] Already downloaded: {filename}")
        return dest_path

    try:
        r = session.get(url, stream=True, timeout=120)
        r.raise_for_status()
        total_bytes = int(r.headers.get("content-length", 0))

        with open(dest_path, "wb") as fh, tqdm(
            desc=f"  {filename}", total=total_bytes, unit="B",
            unit_scale=True, unit_divisor=1024, ncols=80,
        ) as bar:
            for chunk in r.iter_content(chunk_size=256 * 1024):
                if chunk:
                    fh.write(chunk)
                    bar.update(len(chunk))
        return dest_path
    except Exception as e:
        print(f"  [Download] Failed: {filename} — {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return None

SUPPORTED_EXTENSIONS = {".zip", ".rar", ".7z"}

def extract_archive(archive_path):
    archive_name = os.path.basename(archive_path)
    ext = os.path.splitext(archive_name)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        print(f"  [Extract] Unsupported format: {archive_name}")
        return None

    out_folder = os.path.join(EXTRACT_DIR, archive_name)
    if os.path.exists(out_folder) and os.listdir(out_folder):
        print(f"  [Skip] Already extracted: {archive_name}")
        return out_folder

    os.makedirs(out_folder, exist_ok=True)
    try:
        result = subprocess.run(
            [SEVENZIP, "x", archive_path, f"-o{out_folder}", "-y"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=300,
        )
        if result.returncode != 0:
            err = result.stderr.decode(errors="replace").strip()
            print(f"  [Extract] 7-Zip error ({archive_name}): {err}")
    except subprocess.TimeoutExpired:
        print(f"  [Extract] Timed out: {archive_name}")
    except Exception as e:
        print(f"  [Extract] Exception: {archive_name} — {e}")

    return out_folder

# ============================================================
# FIND MOD ROOT & STRUCTURE DETECTION
# ============================================================

def find_immediate_mod_root(extracted_folder):
    """
    Find the actual mod folder (1 level down from extraction root).
    Returns the first non-hidden folder at depth 1.
    """
    items = os.listdir(extracted_folder)
    items = [item for item in items if not item.startswith('.')]
    
    if len(items) == 1:
        candidate = os.path.join(extracted_folder, items[0])
        if os.path.isdir(candidate):
            return candidate
    
    return extracted_folder

def find_mod_root_knight(mod_folder):
    """
    For Knight: find folder containing BmGame or CookedPCConsole/Content structure.
    """
    candidates = []
    
    for root, dirs, files in os.walk(mod_folder):
        dirs_lower = [d.lower() for d in dirs]
        
        if "bmgame" in dirs_lower:
            candidates.append(root)
            continue
        
        root_name = os.path.basename(root).lower()
        if root_name == "bmgame":
            if "cookedpcconsole" in dirs_lower or "content" in dirs_lower:
                candidates.append(os.path.dirname(root))
                continue
        
        if "cookedpcconsole" in dirs_lower or "content" in dirs_lower:
            candidates.append(os.path.dirname(root))
            continue
    
    if not candidates:
        return None
    
    candidates.sort(key=lambda p: len(p.split(os.sep)))
    return candidates[0]

def find_mod_root_origins(mod_folder):
    """
    For Origins: find folder that directly contains .upk and .int files.
    This is the flat structure where files sit directly in the mod root.
    """
    def has_upk_files(path):
        try:
            for item in os.listdir(path):
                if item.lower().endswith((".upk", ".int")):
                    return True
        except:
            pass
        return False
    
    # Check if current folder has .upk/.int files
    if has_upk_files(mod_folder):
        return mod_folder
    
    # Check immediate subfolders (one level deep)
    try:
        for item in os.listdir(mod_folder):
            item_path = os.path.join(mod_folder, item)
            if os.path.isdir(item_path) and has_upk_files(item_path):
                return item_path
    except:
        pass
    
    return None

def get_upk_files(folder):
    """Recursively get all .upk files in folder"""
    upks = set()
    for root, dirs, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".upk"):
                upks.add(f.lower())
    return upks

# ============================================================
# KNIGHT / ORIGINS INSTALLATION
# ============================================================

def install_mod_dlc(mod_root_path, target_dir):
    """Copy mod folder into target DLC directory"""
    mod_name = os.path.basename(mod_root_path)
    dest = os.path.join(target_dir, mod_name)

    if os.path.exists(dest):
        print(f"  [Skip] Already installed: {mod_name}")
        return True

    try:
        shutil.copytree(mod_root_path, dest)
        print(f"  [Install] {mod_name}  →  {target_dir}")
        return True
    except Exception as e:
        print(f"  [Install] Failed: {mod_name} — {e}")
        return False

# ============================================================
# CITY INSTALLATION
# ============================================================

def merge_directory(src, dst):
    """Recursively merge src into dst"""
    os.makedirs(dst, exist_ok=True)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            merge_directory(s, d)
        else:
            shutil.copy2(s, d)

def find_city_bmgame(extracted_folder):
    """Find BmGame folder in City mod"""
    for root, dirs, files in os.walk(extracted_folder):
        for d in dirs:
            if d.lower() == "bmgame":
                return os.path.join(root, d)
    return None

def find_city_txt(extracted_folder):
    """Find .txt file containing +PlayableCharactersV2"""
    for root, dirs, files in os.walk(extracted_folder):
        for f in files:
            if f.lower().endswith(".txt"):
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                        if "+PlayableCharactersV2" in content:
                            return path
                except:
                    pass
    return None

def parse_playable_characters(txt_path):
    """
    Parse .txt file and extract character entries.
    Captures: BaseId, Name, and the entire raw line for ID substitution.
    """
    entries = []
    pattern = re.compile(
        r'\+PlayableCharactersV2=\(.*?BaseId=(\d+).*?Name="([^"]+)"(.*?)\)',
        re.IGNORECASE | re.DOTALL
    )

    try:
        with open(txt_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                m = pattern.search(line)
                if m:
                    entries.append({
                        "base_id":  int(m.group(1)),
                        "name":     m.group(2),
                        "raw_line": line,
                    })
    except Exception as e:
        print(f"  [City] Error parsing txt: {e}")
    
    return entries

def edit_pcgame_ini(ini_path, new_entries):
    """
    Add character entries to PCGame.ini.
    Finds highest Id for each BaseId and increments by 1.
    Uses regex to replace dummy Id (XX) in the raw mod line.
    """
    if not os.path.exists(ini_path):
        print(f"  [City] PCGame.ini not found: {ini_path}")
        return False

    try:
        with open(ini_path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except Exception as e:
        print(f"  [City] Error reading ini: {e}")
        return False

    # Pattern to find existing entries in ini
    line_pattern = re.compile(
        r'\+PlayableCharactersV2=\(.*?BaseId=(\d+).*?Id=(\d+).*?Name="([^"]+)"',
        re.IGNORECASE
    )

    for entry in new_entries:
        base_id  = entry["base_id"]
        mod_name = entry["name"]
        raw_line = entry["raw_line"]

        # Check if already installed
        already_installed = any(
            re.search(rf'Name="{re.escape(mod_name)}"', l, re.IGNORECASE)
            for l in lines
        )
        if already_installed:
            print(f"  [City] Already in ini: {mod_name} (BaseId={base_id})")
            continue

        # Find highest Id for this BaseId
        highest_id    = -1
        last_line_idx = -1

        for idx, line in enumerate(lines):
            m = line_pattern.search(line)
            if m and int(m.group(1)) == base_id:
                current_id = int(m.group(2))
                if current_id > highest_id:
                    highest_id = current_id
                last_line_idx = idx

        if last_line_idx == -1:
            print(f"  [City] No entries for BaseId={base_id} — skipping {mod_name}")
            continue

        new_id = highest_id + 1
        
        # Replace Id=XX (or similar) with actual Id=<new_id>
        # This regex handles: Id=XX, Id=#, Id=0, etc.
        new_line_str = re.sub(
            r'(?i)(\bId\s*=\s*)[^,\)]+',
            rf'\g<1>{new_id}',
            raw_line
        )
        
        if not new_line_str.endswith('\n'):
            new_line_str += '\n'

        lines.insert(last_line_idx + 1, new_line_str)
        print(f"  [City] Added: {mod_name} — BaseId={base_id}, Id={new_id}")

    try:
        with open(ini_path, "w", encoding="utf-8") as fh:
            fh.writelines(lines)
        return True
    except Exception as e:
        print(f"  [City] Error writing ini: {e}")
        return False

def install_mod_city(extracted_folder, game_config):
    """Install City mod: merge BmGame and edit PCGame.ini"""
    dlc_install = game_config["dlc_install"]
    ini_path    = game_config["pcgame_ini"]

    # Merge BmGame folder
    bmgame_src = find_city_bmgame(extracted_folder)
    if bmgame_src:
        bmgame_dst = os.path.join(dlc_install, "BmGame")
        print(f"  [City] Merging BmGame  →  {bmgame_dst}")
        try:
            merge_directory(bmgame_src, bmgame_dst)
        except Exception as e:
            print(f"  [City] Merge failed: {e}")
    else:
        print(f"  [City] No BmGame folder found — skipping file merge")

    # Edit PCGame.ini
    txt_path = find_city_txt(extracted_folder)
    if txt_path:
        print(f"  [City] Found: {os.path.basename(txt_path)}")
        entries = parse_playable_characters(txt_path)
        if entries:
            edit_pcgame_ini(ini_path, entries)
        else:
            print(f"  [City] No character entries found in txt")
    else:
        print(f"  [City] No .txt file found — skipping ini edit")

# ============================================================
# MISC HANDLING
# ============================================================

def install_misc(extracted_folder, game_config):
    """Store mod in misc_mods for manual review"""
    game_misc_dir = os.path.join(MISC_MODS_DIR, game_config["misc_name"])
    os.makedirs(game_misc_dir, exist_ok=True)

    folder_name = os.path.basename(extracted_folder)
    dest = os.path.join(game_misc_dir, folder_name)

    if os.path.exists(dest):
        print(f"  [Misc] Already stored: {folder_name}")
        return

    try:
        shutil.copytree(extracted_folder, dest)
        print(f"  [Misc] Stored: {folder_name}")
    except Exception as e:
        print(f"  [Misc] Failed: {e}")

def install_optional_misc(archive_path, game_config):
    """Extract and store optional file"""
    extracted = extract_archive(archive_path)
    if not extracted:
        return

    install_misc(extracted, game_config)

# ============================================================
# PROCESS MOD
# ============================================================

def process_mod(nexus_slug, mod_id, game_config, global_upk_registry):
    game_type   = game_config["type"]
    nexus_game  = game_config["nexus_game"]
    dlc_install = game_config["dlc_install"]

    print(f"\n{'='*60}")
    print(f"  MOD {mod_id}  |  {nexus_game}")
    print(f"{'='*60}")

    os.makedirs(dlc_install, exist_ok=True)

    # Get files from API
    all_files = get_mod_files(nexus_game, mod_id)
    if not all_files:
        print("  [!] No files from API")
        return

    main_files     = get_latest_main_files(all_files)
    optional_files = [f for f in all_files if classify_file(f) == "optional"]

    print(f"  Main: {len(main_files)} | Optional: {len(optional_files)}")

    # Handle optional files
    for f in optional_files:
        link = get_download_link(nexus_game, mod_id, f["file_id"])
        if not link:
            continue
        archive_path = download_file(link, f["file_name"], DOWNLOAD_DIR)
        time.sleep(DL_DELAY)
        if archive_path:
            install_optional_misc(archive_path, game_config)

    if not main_files:
        print("  [!] No main files")
        return

    # Handle main files
    for f in main_files:
        link = get_download_link(nexus_game, mod_id, f["file_id"])
        if not link:
            continue

        archive_path = download_file(link, f["file_name"], DOWNLOAD_DIR)
        time.sleep(DL_DELAY)
        if not archive_path:
            continue

        extracted_folder = extract_archive(archive_path)
        if not extracted_folder:
            continue

        # City: merge BmGame + edit ini
        if game_type == "city":
            install_mod_city(extracted_folder, game_config)
        
        # Knight / Origins: find mod root and install
        else:
            # Get the actual mod folder (1 level into extraction)
            mod_folder = find_immediate_mod_root(extracted_folder)
            
            if game_type == "knight":
                mod_root = find_mod_root_knight(mod_folder)
            else:  # origins
                mod_root = find_mod_root_origins(mod_folder)

            if not mod_root:
                print(f"  [!] Could not detect mod structure → misc")
                install_misc(extracted_folder, game_config)
                continue

            upks      = get_upk_files(mod_root)
            conflicts = upks & global_upk_registry

            if conflicts:
                print(f"  [Conflict] Duplicate UPK(s): {conflicts}")
                print(f"             → misc")
                install_misc(mod_root, game_config)
            else:
                success = install_mod_dlc(mod_root, dlc_install)
                if success:
                    global_upk_registry.update(upks)

# ============================================================
# MAIN
# ============================================================

def main():
    if not os.path.exists(MODS_FILE):
        print(f"[Error] {MODS_FILE} not found")
        return

    with open(MODS_FILE, "r") as fh:
        raw_lines = [line.strip() for line in fh if line.strip()]

    if not raw_lines:
        print("[Error] mods.txt is empty")
        return

    mod_entries = []
    for line in raw_lines:
        slug, mod_id = parse_nexus_url(line)
        if not slug or not mod_id:
            print(f"[Skip] Invalid URL: {line}")
            continue
        game_config = resolve_game_config(slug)
        if not game_config:
            print(f"[Skip] Unknown game: {slug}")
            continue
        mod_entries.append((slug, mod_id, game_config))

    if not mod_entries:
        print("[Error] No valid URLs in mods.txt")
        return

    print(f"Loaded {len(mod_entries)} mod(s)\n")

    upk_registries = {slug: set() for slug, _, _ in mod_entries}

    for slug, mod_id, game_config in mod_entries:
        try:
            process_mod(slug, mod_id, game_config, upk_registries[slug])
        except Exception as e:
            print(f"\n[Fatal] Error on mod {mod_id}: {e}")

    print(f"\n{'='*60}")
    print("  Completed")
    for slug, registry in upk_registries.items():
        if registry:
            print(f"  {slug}: {len(registry)} UPK(s)")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
