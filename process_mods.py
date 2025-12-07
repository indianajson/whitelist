import os
import json
import requests
import hashlib
import glob

# Configuration
SOURCE_URL = "https://onb.keristero.com/mod_list/"
MOD_DOWNLOAD_TEMPLATE = "https://onb.keristero.com/mods/{}.zip"
STATUS_FILE = "status_cache.json"

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def get_singular_name(type_name):
    # Simple logic to convert "players" -> "player", "skins" -> "skin"
    if type_name.endswith('s'):
        return type_name[:-1]
    return type_name

def main():
    print("Fetching mod list...")
    try:
        response = requests.get(SOURCE_URL)
        response.raise_for_status()
        mod_list = response.json()
    except Exception as e:
        print(f"Failed to fetch mod list: {e}")
        return

    # Load existing status cache
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'r') as f:
            status_cache = json.load(f)
    else:
        status_cache = {}

    # Containers for splitting JSON by type
    type_buckets = {}
    
    # Containers for hash lines by type
    hash_buckets = {}

    updates_made = False

    for key, item in mod_list.items():
        # Safely extract required fields
        data = item.get('data', {})
        attachment_data = item.get('attachment_data', {})
        
        mod_type = data.get('type', 'unknown')
        mod_id = data.get('id')
        attachment_id = attachment_data.get('attachment_id')
        timestamp = attachment_data.get('timestamp')

        # Skip if essential data is missing
        if not mod_id or not attachment_id:
            print(f"Skipping entry {key}: Missing ID or Attachment ID")
            continue

        # Initialize buckets if new type found
        singular_type = get_singular_name(mod_type)
        if singular_type not in type_buckets:
            type_buckets[singular_type] = {}
            hash_buckets[singular_type] = []

        # Add to type-specific JSON bucket
        type_buckets[singular_type][key] = item

        # Check cache to see if we need to download/hash
        cache_entry = status_cache.get(str(attachment_id))
        
        current_md5 = None
        
        # Condition: New file OR timestamp changed
        if not cache_entry or cache_entry.get('timestamp') != timestamp:
            print(f"Processing new/updated mod: {mod_id} (Type: {mod_type})")
            
            zip_url = MOD_DOWNLOAD_TEMPLATE.format(attachment_id)
            zip_filename = f"{attachment_id}.zip"
            
            try:
                # Download
                print(f"  Downloading {zip_url}...")
                r = requests.get(zip_url, stream=True)
                if r.status_code == 200:
                    with open(zip_filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    # Calculate MD5
                    current_md5 = calculate_md5(zip_filename)
                    print(f"  MD5: {current_md5}")
                    
                    # Delete Zip
                    os.remove(zip_filename)
                    
                    # Update Cache
                    status_cache[str(attachment_id)] = {
                        "timestamp": timestamp,
                        "md5": current_md5,
                        "id": mod_id
                    }
                    updates_made = True
                else:
                    print(f"  Failed to download {zip_url} (Status: {r.status_code})")
                    # If download fails, skip adding to hash list for now
                    continue
            except Exception as e:
                print(f"  Error processing {mod_id}: {e}")
                if os.path.exists(zip_filename):
                    os.remove(zip_filename)
                continue
        else:
            # Use cached MD5
            current_md5 = cache_entry.get('md5')

        # Add to hash bucket (Format: MD5 ID)
        if current_md5:
            hash_buckets[singular_type].append(f"{current_md5} {mod_id}")

    # --- SAVE OUTPUTS ---

    # 1. Save Status Cache
    if updates_made:
        print("Updating status cache file...")
        with open(STATUS_FILE, 'w') as f:
            json.dump(status_cache, f, indent=2)
    else:
        print("No new downloads required.")

    # 2. Save Split JSON files (e.g., player.json, skin.json)
    for type_name, data_dict in type_buckets.items():
        filename = f"{type_name}.json"
        with open(filename, 'w') as f:
            json.dump(data_dict, f, indent=2)
        print(f"Saved {filename}")

    # 3. Save Hash files (e.g., player_hash.txt)
    for type_name, lines in hash_buckets.items():
        filename = f"{type_name}_hash.txt"
        with open(filename, 'w') as f:
            f.write("\n".join(lines))
        print(f"Saved {filename}")

if __name__ == "__main__":
    main()
