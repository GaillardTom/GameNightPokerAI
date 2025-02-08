import time
import asyncio
import websockets
import json
from bs4 import BeautifulSoup as bs
from datetime import datetime
import requests

retry = 0
MAX_GAMES = 3
TEAM_NAME= "Team Name"
date = datetime.today().strftime("%d_%m_%H_%M_%S")
PATH_TO_WRITE = f"latest_game_{date}.txt"
print("Path to write: ", PATH_TO_WRITE)
print(f"RUNNING FOR {MAX_GAMES} ITERATIONS LOOKING AT PLAYER: {TEAM_NAME}") 


burp0_cookie = "_xsrf=2|9ab36512|93afadbdcf83cbdebda5a1394a3fa659|1738818521"
burp0_headers = {
    "Connection": "Upgrade",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.140 Safari/537.36",
    "Upgrade": "websocket",
    "Origin": "http://localhost:8000",
    "Sec-WebSocket-Version": "13",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-WebSocket-Key": "DmvIoR7PZr4HIvkWdwsuPQ==",
    'Cookie': burp0_cookie
}




async def get_winner(event_html):
    soup = bs(event_html, "html.parser")
    winner = soup.find_all("td")[1].text
    return winner

def write_to_file(winner):
    with open("./test_results/"+PATH_TO_WRITE, "a") as file:
        file.write(winner + "\n")
    
def get_win_percentage(team_name):
    try:
        with open("./test_results/"+PATH_TO_WRITE, 'r') as file:
            data = file.read()
        lines = data.split('\n')
        win_count = lines.count(team_name)
        total_count = len(lines) - 1  # Subtract 1 for the last empty line
        win_percentage = (win_count / total_count) * 100 if total_count > 0 else 0
        # print(f"Win percentage: {win_percentage}%")
        return win_percentage
    except FileNotFoundError:
        print("File not found")
        return 0

async def stop_container():
    process = await asyncio.create_subprocess_shell(
        'docker-compose down',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        print(f"Error stopping container: {stderr.decode()}")
    else:
        print(f"Container stopped: {stdout.decode()}")

async def start_container():
    global retry
    process = await asyncio.create_subprocess_shell(
        'docker-compose up -d',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        print(f"Error starting container: {stderr.decode()}")
        print("Retrying to start container")
        if retry < 3:
            retry += 1
            await stop_container()
            await start_container()
        else:
            print(f"Error starting container after retries: {stderr.decode()}")
            return False
    else:
        # print(f"Container started {stdout.decode()}")
        return True


def check_local_host():
    try:
        response = requests.get('http://localhost:8000')
        if response.status_code == 200:
            # print("Poker game is up and running")
            response = requests.get("http://localhost:8000/pokersocket", headers=burp0_headers)
            # print(f"statusCode: {response.status_code}")
            # print(f"body: {response.text}")
            return True
        else:
            return False
    except requests.RequestException as e:
        print(f"Error: {e}")
        return False
    

async def handle_connection(uri):
    # print("Connecting to server")
    #Ajusted ping_interval and ping_timeout for keep alive bug
    async with websockets.connect(uri, ping_interval=60, ping_timeout=180) as ws:
        # print("Connected to ws server")
        # time.sleep(2)
        await ws.send(json.dumps({"type": "action_start_game"}))
        print("Game started... (This could take a while. Up to 3 min per game)")
        # time.sleep(2)
        while True:
            try:
                #Added this to handle timeout
                async with asyncio.timeout(20):
                    #Receive message from poker server
                    message = await ws.recv()
                    # print(f"Received message: {message}")
                    json_data = json.loads(str(message))
                    # Get the winner and write it to a fiile
                    # print(f"data_received converted to json: {json_data}")
                    # print(f"typeof data_received: {type(json_data)}")
                    # print(f"update_type: {json_data.get('content').get('update_type')}")
                    # print(f"event_html: {json_data.get('content').get('event_html')}")
                    # print(f"{json_data.get('content').get('update_type') == "game_result_message"} ")
                    if str(json_data.get("content").get("update_type")).strip() == "game_result_message":
                        # print("closing connection")
                        await ws.close()
                        # print("Connection closed")
                        winner = await get_winner(json_data["content"]["event_html"])
                        print(f"Winner is: {winner}")
                        write_to_file(winner.strip())
                        break
            except Exception as e:
                await ws.close()
                await stop_container()
                print(f"Error: {e}")
                exit(1)

        # await ws.wait_closed()
        await ws.close()
        print("Connection closed")
        print("Stopping container")
        await stop_container()

async def start_poker_game():
    await start_container()
    time.sleep(2)
    if check_local_host():
        await handle_connection('ws://localhost:8000/pokersocket')
        print(f"Current win percentage: {get_win_percentage(TEAM_NAME)} %")




if __name__ == "__main__":
    uri = "ws://localhost:8000/pokersocket"
    try:
        for i in range(MAX_GAMES):
            print(f"Game {i+1}")
            asyncio.run(start_poker_game())
    except KeyboardInterrupt:
        print("KeyboardInterrupt, stopping containers...")
        stop_container()
        exit(0)