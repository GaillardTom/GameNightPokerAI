const { exec } = require('child_process');

// Function to login to Docker
function loginToDocker() {
    exec("docker login", (err, stdout, stderr) => {
        if(err){ 
            console.error(`Error logging in: ${stderr}`);
            return;
        }    
    });
}
// Start the Docker container using docker-compose up
function startContainer() {
    exec('docker-compose -f ../../gameServer/docker-compose.yml up -d', (err, stdout, stderr) => {
        if (err) {
            console.error(`Error starting container: ${stderr}`);
            return;
        }
        console.log(`Container started: ${stdout}`);
    });
}
// function to stop the container using docker-compose down
function stopContainer() {
    exec('docker-compose down', (err, stdout, stderr) => {
        if (err) {
            console.error(`Error stopping container: ${stderr}`);
            return;
        }
        console.log(`Container stopped: ${stdout}`);
    });
}

//loginToDocker();
startContainer();
setTimeout(() => {
    stopContainer();
}, 5000);


module.exports = { loginToDocker, startContainer, stopContainer };