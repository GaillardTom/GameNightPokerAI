import json
import os
import subprocess
from datetime import datetime

import asyncio
import websockets
from bs4 import BeautifulSoup as bs
from websockets import ConnectionClosedError

# Configuration
NUM_CONTAINERS = 10  # Number of container to spawn
ITERATIONS = 20  # Iteration per container
STARTING_PORT = 8001  # Starting port, keep 8000 free for manual testing
TEAM_NAME = "35 Signals Regiment - 35rtrans"
DATE = datetime.today().strftime("%d_%m_%H_%M_%S")
PATH_TO_WRITE = f"latest_game_{DATE}.txt"
RESULT_PATH = "./test_results/"
print("Path to write: ", PATH_TO_WRITE)
print(f"RUNNING FOR {ITERATIONS} ITERATIONS LOOKING AT PLAYER: {TEAM_NAME}")

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
    if not os.path.exists(RESULT_PATH):
        os.makedirs(RESULT_PATH)
        print(f"Directory '{RESULT_PATH}' created.")
    with open(RESULT_PATH + PATH_TO_WRITE, "a") as file:
        file.write(winner + "\n")


def print_win_percentage(team_name):
    try:
        with open(RESULT_PATH + PATH_TO_WRITE, 'r') as file:
            data = file.read()
        lines = data.split('\n')
        win_count = lines.count(team_name)
        total_count = len(lines) - 1  # Subtract 1 for the last empty line
        win_percentage = (win_count / total_count) * 100 if total_count > 0 else 0
        # print(f"Win percentage: {win_percentage}%")
        print(f"[{datetime.today()}] Current win percentage {team_name} : {win_percentage} % - Total game played {total_count}")
    except FileNotFoundError:
        print("File not found")
        return 0


async def run_websocket_command(host_port, command, container_id, iteration):
    uri = f"ws://localhost:{host_port}/pokersocket"
    try:
        game_started = False
        end_of_game = False
        error = False
        while not end_of_game and not error:
            async with websockets.connect(uri, ping_interval=None, ping_timeout=180) as websocket:
                print(f"[Connection] Iteration {iteration} for {container_id}")
                if not game_started:
                    await websocket.send(command)
                game_started = True
                while True:
                    try:
                        # Added this to handle timeout
                        async with asyncio.timeout(20):
                            # Receive message from poker server
                            message = await websocket.recv()
                            # print(f"Received message: {message}")
                            json_data = json.loads(str(message))

                            if str(json_data.get("content").get("update_type")).strip() == "game_result_message":
                                end_of_game = True
                                await websocket.close()
                                winner = await get_winner(json_data["content"]["event_html"])
                                print(f"Winner is: {winner}")
                                write_to_file(winner.strip())
                                print_win_percentage(TEAM_NAME)
                                break
                    except ConnectionClosedError as e:
                        await websocket.close()
                        print(f"[Error] ConnectionClosedError iteration {iteration} for {container_id}: {e}")
                        break
                    except Exception as e:
                        await websocket.close()
                        print(f"[Error] iteration {iteration} won't count for container {container_id}: {e}")
                        error = True
                        break

    except Exception as e:
        print(f"Communication error {uri} : {e}")
        return None

async def container_loop(container_id, host_port, iterations):
    for i in range(iterations):

        print(f"Container {container_id} - port {host_port} - iteration {i + 1}")
        # Leave time for container to boot
        await asyncio.sleep(5)
        await run_websocket_command(host_port, json.dumps({"type": "action_start_game"}), container_id, i + 1)

        print(f"Reboot container {container_id}...")
        try:
            await asyncio.to_thread(
                subprocess.run,
                ["docker", "restart", container_id],
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"[Error] Reboot container {container_id} : {e}")


async def main():
    containers = []
    cwd = os.getcwd()

    for i in range(NUM_CONTAINERS):
        host_port = STARTING_PORT + i
        docker_cmd = [
            "docker", "run", "-d",
            "-p", f"{host_port}:8000",
            "-v", f"{cwd}/logs:/app/logs",
            "-v", f"{cwd}/conf:/app/conf",
            "-v", f"{cwd}/players:/app/players",
            "-e", "GAME_SPEED=fast",
            "poker_server-app:latest"
        ]
        print("Launch container with command :")
        print(" ".join(docker_cmd))
        try:
            result = subprocess.run(
                docker_cmd, capture_output=True, text=True, check=True
            )
            container_id = result.stdout.strip()
            containers.append((container_id, host_port))
            print(f"Container spawned = {container_id} - port = {host_port}")
        except subprocess.CalledProcessError as e:
            print(f"[Error] Container spawned = {container_id} : {e}")

    tasks = []
    for container_id, host_port in containers:
        tasks.append(container_loop(container_id, host_port, ITERATIONS))
        await asyncio.sleep(1)
    await asyncio.gather(*tasks)

    for container_id, _ in containers:
        print(f"Stop and delete container {container_id}...")
        try:
            await asyncio.to_thread(
                subprocess.run,
                ["docker", "stop", container_id],
                check=True
            )
            await asyncio.to_thread(
                subprocess.run,
                ["docker", "rm", container_id],
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"[Error] Stop and delete container {container_id} : {e}")


if __name__ == "__main__":
    asyncio.run(main())
