from app import create_app
from pyngrok import ngrok
import os
import certifi


app = create_app()

os.environ["SSL_CERT_FILE"] = certifi.where()

if __name__ == "__main__":
    port = 4491
    public_url = ngrok.connect(port)
    print(f" SHOP DATABASE LINK AVAILABLE AT: {public_url}")
    print(f"USE THIS LINK {public_url} TO VIEW")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)