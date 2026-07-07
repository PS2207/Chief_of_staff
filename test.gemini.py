import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

key = os.getenv("GEMINI_API_KEY")
print(key[:10])

genai.configure(api_key=key)

model = genai.GenerativeModel("gemini-2.5-flash")

response = model.generate_content("Say Hello")

print(response.text)

# Check your installed package
# pip show google-generativeai