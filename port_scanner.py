from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
import socket
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

stop_flag = False

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Live Port Scanner</title>
<style>
    body { background: #000; color: #0f0; font-family: "Courier New", monospace; padding: 20px; }
    input, button { background: #111; color: #0f0; border: 1px solid #0f0; padding: 8px; }
    button:hover { background: #0f0; color: #000; cursor: pointer; font-weight: bold; }
    #output { background: #000; color: #0f0; padding: 15px; height: 350px; overflow-y: scroll; white-space: pre-line; border: 2px solid #0f0; margin-top: 20px; }
    .progress-container { width: 100%; background-color: #222; border-radius: 5px; margin-top: 10px; border: 1px solid #0f0; }
    .progress-bar { width: 0%; height: 25px; background-color: #0f0; text-align: center; color: #000; line-height: 25px; border-radius: 5px; font-weight: bold; transition: width 0.2s ease; }
</style>
</head>
<body>

<h1>Live Port Scanner</h1>

<form id="scanForm">
    <label>Target Host:</label><br>
    <input name="host" required><br><br>

    <label>Scan Mode:</label><br>
    <input type="radio" name="mode" value="single" checked> Single Port<br>
    <input type="radio" name="mode" value="range"> Port Range<br><br>

    <div id="singlePort">
        <label>Port:</label><br>
        <input type="number" name="port"><br><br>
    </div>

    <div id="rangePorts" style="display:none;">
        <label>Start Port:</label><br>
        <input type="number" name="start"><br><br>
        <label>End Port:</label><br>
        <input type="number" name="end"><br><br>
    </div>

    <button type="submit">Start Scan</button>
    <button type="button" id="stopBtn" style="margin-left:10px;">STOP SCAN</button>
</form>

<div class="progress-container">
    <div id="progressBar" class="progress-bar">0%</div>
</div>

<h2>Output:</h2>
<div id="output"></div>

<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
<script>
const socket = io();
let results = [];
const output = document.getElementById("output");
const progressBar = document.getElementById("progressBar");
const modeRadios = document.querySelectorAll("input[name='mode']");
const singleDiv = document.getElementById("singlePort");
const rangeDiv = document.getElementById("rangePorts");

modeRadios.forEach(r => {
    r.addEventListener("change", () => {
        singleDiv.style.display = r.value === "single" ? "block" : "none";
        rangeDiv.style.display = r.value === "range" ? "block" : "none";
    });
});

document.getElementById("scanForm").addEventListener("submit", e => {
    e.preventDefault();
    output.innerHTML = "";
    results = [];
    progressBar.style.width = "0%";
    progressBar.innerText = "0%";

    const formData = new FormData(e.target);
    const data = {};
    formData.forEach((value, key) => data[key] = value);
    socket.emit("start_scan", data);
});

document.getElementById("stopBtn").addEventListener("click", () => {
    socket.emit("stop_scan");
});

socket.on("scan_update", data => {
    // LIVE OUTPUT
    const line = document.createElement("div");
    line.innerHTML = `Port ${data.port}: <span style="color:${data.status==='OPEN'?'#f00':'#0f0'}">${data.status}</span>`;
    output.appendChild(line);
    output.scrollTop = output.scrollHeight;

    // store for sorted summary
    results.push(data);

    progressBar.style.width = data.progress + "%";
    progressBar.innerText = data.progress + "%";
});

socket.on("scan_complete", data => {
    const sep = document.createElement("div");
    sep.innerHTML = "<br><strong>--- Sorted Summary ---</strong><br>";
    output.appendChild(sep);

    // Sort OPEN ports on top
    results.sort((a, b) => {
        if(a.status==="OPEN" && b.status!=="OPEN") return -1;
        if(a.status!=="OPEN" && b.status==="OPEN") return 1;
        return a.port - b.port;
    });

    results.forEach(r => {
        const line = document.createElement("div");
        line.innerHTML = `Port ${r.port}: <span style="color:${r.status==='OPEN'?'#f00':'#0f0'}">${r.status}</span>`;
        output.appendChild(line);
    });

    const done = document.createElement("div");
    done.innerHTML = "<br>" + data.message;
    output.appendChild(done);
    output.scrollTop = output.scrollHeight;

    results = [];
});
</script>

</body>
</html>
"""

def scan_port(host, port, timeout=1):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port))==0
    except:
        return False

@app.route("/")
def index():
    return render_template_string(HTML)

@socketio.on("stop_scan")
def stop_scan():
    global stop_flag
    stop_flag = True

@socketio.on("start_scan")
def handle_start_scan(data):
    global stop_flag
    stop_flag = False

    host = data.get("host")
    mode = data.get("mode")

    if mode=="single":
        ports = [int(data.get("port"))]
    else:
        start = int(data.get("start"))
        end = int(data.get("end"))
        ports = list(range(start,end+1))

    total = len(ports)

    for idx, port in enumerate(ports, start=1):
        if stop_flag:
            emit("scan_complete", {"message":"SCAN STOPPED BY USER"})
            return

        status = "OPEN" if scan_port(host, port) else "CLOSED"
        color = "red" if status=="OPEN" else "green"

        emit("scan_update", {
            "port": port,
            "status": status,
            "color": color,
            "progress": int(idx/total*100)
        })

        time.sleep(0.005)

    emit("scan_complete", {"message":"Scan complete!"})

if __name__=="__main__":
    socketio.run(app, debug=True, use_reloader=False, host="0.0.0.0", port=5000)
