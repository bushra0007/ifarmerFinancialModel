import threading
import time
from pyngrok import ngrok

# Start Streamlit in background
def run_streamlit():
    import subprocess
    subprocess.run(["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "localhost"])

t = threading.Thread(target=run_streamlit, daemon=True)
t.start()
time.sleep(3)

# Create public tunnel
public_url = ngrok.connect(8501)
print(f"\n{'='*50}")
print(f"PUBLIC URL: {public_url}")
print(f"{'='*50}")
print(f"\nShare this link with anyone, anywhere.")
print(f"Viewer password: ifarmer2026")
print(f"\nPress Ctrl+C to stop.\n")

# Keep running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    ngrok.kill()
