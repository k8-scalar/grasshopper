from flask import Flask, request
import subprocess
import os

app = Flask(__name__)


@app.route("/")
def hello():
    return "Vulnerable App says: Hello!"

@app.route("/vulnerable_endpoint")
def ping():
    cmd = request.args.get('cmd', '')
    result = subprocess.check_output(cmd, shell=True)
    return result

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080) # allow kubernetes to route traffic to app.
