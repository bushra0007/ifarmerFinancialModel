from pyngrok import ngrok
import time

url = ngrok.connect(8501, bind_tls=True)
print(f"\nPUBLIC URL: {url}")
print("\nShare this link with anyone!")
print("Password: ifarmer2026")
print("\nPress Ctrl+C to stop.\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    ngrok.kill()
