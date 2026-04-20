from kiteconnect import KiteConnect

API_KEY = "kmsyy686a52wo9g3"
API_SECRET = "vclp730ysva38u1j29xi5dwfvz9l11e0"

kite = KiteConnect(api_key=API_KEY)

# Step 1: print login URL and open it in browser
print("Login URL:", kite.login_url())

# After login, copy request_token from redirect URL and paste here
request_token = input("Enter request_token: ").strip()

data = kite.generate_session(request_token, api_secret=API_SECRET)
access_token = data["access_token"]
print("ACCESS TOKEN:", access_token)