
// const { start } = require('repl');
const util = require('util');
// const request = require('request');
// const { json } = require('stream/consumers');
const WebSocket = require('ws');
const { DOMParser } = require('xmldom');
const fs = require('fs');
const exec = util.promisify(require('child_process').exec);
const request = util.promisify(require('request'));
// CONST TO RUN THE GAME FOR DESIRED NUMBER OF TIMES
const MAX_GAMES = 3;
const TEAM_NAME = "Team Name";

process.env['NODE_TLS_REJECT_UNAUTHORIZED'] = 0

const today = new Date();
const fileToWrite = "latest_game_" + today.getFullYear().toString() + today.getMonth().toString() + today.getDay().toString() + "_" + today.getTime().toString() + ".txt";

var burp0_cookie = "_xsrf=2|9ab36512|93afadbdcf83cbdebda5a1394a3fa659|1738818521"
var burp0_headers = {
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

var burp0_options = {
    url: "http://localhost:8000/pokersocket",
    headers: burp0_headers,
    method: "get",
}

var ws = null;  




// Function to login to Docker
function loginToDocker() {
    exec("docker login", (err, stdout, stderr) => {
        if(err){ 
            console.error(`Error logging in: ${stderr}`);
            return;
        }    
    });
}
function checkLocalHost() {
        request('http://localhost:8000', (error, response, body) => {
            if (error) {
                console.error(`Error: ${error}`);
            } else {
                console.log(`Response: ${response.statusCode}`);
                if (response.statusCode === 200) {
                    console.log(`Poker game is up and running`);
                    () => request(burp0_options, function (error, response, body) {
                        console.log('statusCode:', response && response.statusCode);
                        console.log('error: ', error);
                        console.log('body: ', body);
                    });
                    return true;
                } else {
                    return false;
                }
            }
        });
}

function getWinner(raw_html){ 
    const parser = new DOMParser();
    const el = parser.parseFromString(raw_html, "text/html");
    var winner = el.getElementsByTagName("td");
    for (var i = 0; i < winner.length; i++) {
        console.log(i + " " + winner[i].textContent);
    }
    winner = winner[1].textContent.toString();
    console.log(winner);
    return String (winner);
}
function writeToFile(winner) {
    //if the file doesn't exist, create it
    if (!fs.existsSync(fileToWrite)) {
        fs.writeFileSync(fileToWrite, '', (err) => {
            if (err) {
                console.error(`Error creating file: ${err}`);
                return;
            }
            console.log('File created');
        });
    }
    // Append to the  file
    fs.appendFile(fileToWrite, winner + "\n", (err) => {
        if (err) {
            console.error(`Error writing to file: ${err}`);
            return;
        }
        console.log('Winner written to file');
    });
    
};    

function getWinPercentage(winner) {
    // Read the file
    var winPercentage = -1;
    fs.readFile(fileToWrite, 'utf8', (err, data) => {
        if (err) {
            console.error(`Error reading file: ${err}`);
            return;
        }
        console.log(`File contents: ${data}`);
        var winCount = 0;
        var totalCount = 0;
        var lines = data.split('\n');
        for (var i = 0; i < lines.length; i++) {
            if (lines[i] === winner) {
                winCount++;
            }
            totalCount++;
        }
        winPercentage = (winCount / totalCount) * 100;
        console.log(`Win percentage: ${winPercentage}%`);
    });
    return winPercentage;
}    

function InteractWithGame() {

    ws.on('open', function open() {
        start_game = '{"type": "action_start_game"}'
        console.log("connected")
        ws.send(start_game);
    });
    ws.on('message', function incoming(data) {
        // console.log(data.toString());
        json_data = JSON.parse(data);
        if(!json_data.content) {
            return;
        }
        console.log(json_data.content);
        if(json_data.content.update_type == "game_result_message") {
            console.log("Game Over");
            // console.log("Writing to file");
            var winner = getWinner(json_data.content.event_html);
            console.log("Winner is: " + winner);
            writeToFile(winner.trim());
            console.log("closing connection");
            ws.close();
        }
        // if (json_data.message_type == "update_game") {} 
    });
    ws.on('close', async function() {
        // Handle connection close
        console.log("Connection closed");
        console.log("Stopping container");
        await stopContainer().then(() => { ws.terminate(); });
      });
}
var retry = 0;
// Start the Docker container using docker-compose up
async function startContainer() {
        await exec('docker-compose  up -d', async(err, stdout, stderr) => {
        if (err) {
            console.error(`Error starting container: ${stderr}`);
            console.log("Retrying to start container");
            // loginToDocker();
            if (retry < 3) {
                retry++;
                await stopContainer().then(() => {  
                    startContainer();
                });
            } else {
                console.error(`Error starting container: ${stderr}`);
                return;
            }
        }
        }).then(() => { return true;} );
}
// function to stop the container using docker-compose down
async function stopContainer() {
        await exec('docker-compose down', (err, stdout, stderr) => {
            if (err) {
                console.error(`Error stopping container: ${stderr}`);
                return;
            }
            console.log(`Container stopped: ${stdout}`);
        }).then(() => { return true;} );
}

async function StartPokerGame(){
    await startContainer().then(() => {
        // console.log("Container started");
        //checkLocalHost()
        ws = new WebSocket('ws://localhost:8000/pokersocket', {
            headers: {
                'Cookie': burp0_cookie
            }
        });

        console.log("Interacting with game");
        InteractWithGame();

    }).catch((err) => {
        console.error(`Error starting container: ${err}`);
    });
    
    // .then((isRunning) => {
    //     if (isRunning) {
    //         InteractWithGame();
    //     } else {
    //         console.error(`Poker game is not running`);
    //     }
    // })
};


async function main(){ 
    var count = 0;
    while(count <= MAX_GAMES){
        await StartPokerGame();
        count++;
    }
    console.log(TEAM_NAME + " has a win rate of :" +getWinPercentage(TEAM_NAME));
    
} 

main();

module.exports = { loginToDocker, startContainer, stopContainer };