import time
import datetime
import html_generator
import firebase_manager

if __name__ == "__main__":
    print("--- 🖥️ BusPal Dashboard Monitor: Active ---")
    
    while True:
        now = datetime.datetime.now()
        print(f"[{now.strftime('%H:%M:%S')}] Refreshing Dashboard...")
        
        # 1. Generate the HTML from whatever is currently in Firebase
        if html_generator.generate_html():
            # 2. Deploy it immediately
            html_generator.deploy()
            
        print("Done. Waiting 60s for next update.")
        time.sleep(60) # You can make this faster or slower independently