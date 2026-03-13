# Batman Arkham Mod Installer — Setup Guide
Prerequisites
Before anything else, install the following:

* Python — https://www.python.org/downloads/ (let the installer handle everything)
* 7-Zip — https://www.7-zip.org/




# Setup
1. Extract the mod folder
Extract the downloaded folder so it sits at` C:\AKMods`
2. Collect your mod URLs
On Nexus Mods, bookmark every mod you want to download into a folder. When finished, right-click your bookmark folder and select Copy All Links, then paste them into mods.txt inside your AKMods folder.
Each line should be a complete Nexus Mods URL, like:
`https://www.nexusmods.com/batmanarkhamknight/mods/1234
https://www.nexusmods.com/batmanarkhamorigins/mods/5678
https://www.nexusmods.com/batmanarkhamcity/mods/9012`

The script will automatically detect which game each mod belongs to based on the URL.
3. Get your Nexus API key
Go to https://www.nexusmods.com/settings/api-keys, scroll to the bottom, and generate a Personal API Key. Copy it.
4. Add your API key to the script
Open arkham_mod_installer.py in Notepad, find the line:

`codeAPI_KEY = "apikeyhere"`
Replace `apikeyhere `with the key you just copied.
5. Run the installer
Type cmd into the Windows search bar to open Command Prompt. Make sure it's Command Prompt, not PowerShell — if it opened in PowerShell, click the arrow next to the + tab and switch to Command Prompt.
Navigate to your AKMods folder by typing :

`cd C:\AKMods`

Then run in the same console:
`python arkham_mod_installer.py`


# How the Installer Works
## Supported Games
The script supports all three Batman Arkham games:

**Batman Arkham Knight — DLC folder installation**
**Batman Arkham Origins — DLC folder installation (flat mod structure)**
** Batman Arkham City — BmGame merge + PCGame.ini character registration**

## File Organization
The installer automatically creates these folders:
C:\AKMods\
├── downloads\          (downloaded .zip/.rar/.7z files)
├── extracted\          (extracted mod contents)
├── misc_mods\          (mods that couldn't be auto-installed)
│   ├── Batman Arkham Knight\
│   ├── Batman Arkham Origins\
│   └── Batman Arkham City\
└── mods.txt           (your mod URLs)

## What Gets Installed Where
Knight & Origins:

* Main mod files are copied into the game's DLC folder as named subfolders
* UPK conflicts are detected and moved to misc_mods instead
* Optional files are always stored in misc_mods

City:

* BmGame folder is merged into C:\Program Files (x86)\Steam\steamapps\common\Batman Arkham City GOTY\BmGame
* Character entries from mod .txt files are automatically added to PCGame.ini with correct BaseId and incremented Id values
* If BmGame merge fails or no .txt is found, the mod goes to misc_mods

Archived/Old Files
The script automatically skips archived and old version files, but downloads optional/misc files into misc_mods for your review.



# Cleanup & Storage
Free Up Space
If you're running low on disk space, you can safely delete:

* Everything in C:\AKMods\downloads\ (the original .zip files)
* Everything in C:\AKMods\extracted\ (the unpacked contents)

Your mods will still be installed in the game folders. Keep these only if you plan to reinstall or troubleshoot.
Check Misc Folders
After running the script, check:

* C:\AKMods\misc_mods\ — Optional files and mods that couldn't be auto-installed
* Game-specific subfolders for each title


# Configuration (Optional)

Open arkham_mod_installer.py in Notepad if you need to change any defaults:
7-Zip installed somewhere other than default?
Find the folder containing 7z.exe, copy its full path, and replace this line:
`SEVENZIP = r"C:\Program Files\7-Zip\7z.exe"`


# AKMods folder in a different location?

Replace* C:\AKMods* with your actual path throughout the script:
`BASE_DIR = r"C:\Your\Custom\Path\AKMods"`
Steam or games installed on a different drive?
Replace the paths in GAME_CONFIGS with your actual install locations:

Knight:
`"dlc_install": r"C:\Program Files (x86)\Steam\steamapps\common\Batman Arkham Knight\DLC\356474",`
Origins:
`"dlc_install": r"C:\Program Files (x86)\Steam\steamapps\common\Batman Arkham Origins\SinglePlayer\DLC\257070",`
City:
`"dlc_install": r"C:\Program Files (x86)\Steam\steamapps\common\Batman Arkham City GOTY",
"pcgame_ini": r"C:\Program Files (x86)\Steam\steamapps\common\Batman Arkham City GOTY\BmGame\Config\PC\PCGame.ini",`

# Troubleshooting
"Could not detect mod structure — moving to misc"
The script couldn't find the expected mod folder layout. Check C:\AKMods\misc_mods\ for the extracted mod and manually review its structure.

"Duplicate UPK(s) — Moving to misc instead"
This mod uses UPK files that are already installed by another mod. It's been saved to misc_mods to prevent conflicts. You can manually install it if you want to replace the existing version.

"No BmGame folder found" (City mods)
The mod's BmGame folder wasn't found, but optional .txt files may have been processed. Check misc_mods for additional content.

# API or Download Errors
The script retries 3 times with automatic delays. If it still fails:

* Check your internet connection
* Verify your API key is correct
* Wait a few minutes (Nexus rate limiting)
