import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
from wakeword_service import WakeWordService

if __name__ == "__main__":
    print("--------------------------------------")
    print(" 👂 TEST LISTEN: Say 'Hey Jarvis'")
    print("--------------------------------------")

    # Pass debug=True to see the volume/score logs
    service = WakeWordService(
        model_names=["hey_jarvis"], 
        sensitivity=0.5, 
        debug=True 
    )

    try:
        service.start()
    except KeyboardInterrupt:
        print("\n👋 Stopping...")