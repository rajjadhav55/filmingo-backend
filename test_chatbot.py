import json
import urllib.request

url = 'http://localhost:8000/api/chatbot/'
data = json.dumps({'message': 'Where can I watch Inception?'}).encode('utf-8')
headers = {'Content-Type': 'application/json'}

try:
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    response = urllib.request.urlopen(req)
    print("Success:")
    print(response.read().decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
