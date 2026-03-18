from gradio_client import Client, handle_file
from dotenv import load_dotenv
import os
import json 
load_dotenv()
TOKEN = os.getenv('TOKEN')
PROJ_KEY = os.getenv('PROJ_NAME')

#triggering the client
client = Client(PROJ_KEY, token=TOKEN)
print(client.view_api())

def extract_the_data(img_path):
    try:
        result = client.predict(
            image=handle_file(img_path),
            api_name='/predict'
        )
        data = json.loads(result)
        return data
    
    except Exception as e:
        print(f"API Error: {e}")
        return {"Error": "Failed to reach OCR Engine"}
