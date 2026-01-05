import ollama

# Match this exactly to what worked in your terminal
MODEL = "llama3.2" 

print(f"🧠 Connecting to Ollama ({MODEL})...")

try:
    # We use stream=True so we can see if it hangs immediately or mid-sentence
    stream = ollama.chat(
        model=MODEL,
        messages=[{'role': 'user', 'content': 'Say "Hello World" and nothing else.'}],
        stream=True,
    )
    
    print("✅ Connection established! Receiving response:")
    print("---------------------------------------------")
    
    full_response = ""
    for chunk in stream:
        content = chunk['message']['content']
        print(content, end='', flush=True)
        full_response += content
        
    print("\n---------------------------------------------")
    print("✅ Test Complete.")

except Exception as e:
    print(f"\n❌ Error: {e}")