import json
import requests
import os

# 1. Load your API Key from the config file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

try:
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
        api_key = config.get("cloud_api", {}).get("api_key")
except Exception as e:
    print(f"❌ Could not load config: {e}")
    exit()

if not api_key or "YOUR" in api_key:
    print("❌ API Key not set in config.json")
    exit()

print(f"🔑 Using API Key: {api_key[:5]}...{api_key[-3:]}")

# 2. Hit the Google "List Models" Endpoint
# Note: We use the standard Google endpoint to list, not the OpenAI one
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

try:
    response = requests.get(url)
    if response.status_code != 200:
        print(f"❌ Error {response.status_code}: {response.text}")
        exit()
    
    data = response.json()
    
    print("\n✅ AVAILABLE MODELS (That support 'generateContent'):")
    print("-" * 60)
    print(f"{'Model Name (Put this in config)':<40} | {'Version'}")
    print("-" * 60)
    
    found_any = False
    for model in data.get("models", []):
        # We only care about models that can generate text/chat
        if "generateContent" in model.get("supportedGenerationMethods", []):
            name = model["name"].replace("models/", "") # Clean up the 'models/' prefix
            version = model.get("version", "unknown")
            print(f"{name:<40} | {version}")
            found_any = True

    if not found_any:
        print("⚠️ No chat models found. Check your API key permissions.")

except Exception as e:
    print(f"❌ Connection failed: {e}")
