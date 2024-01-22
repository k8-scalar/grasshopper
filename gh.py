import subprocess
import signal

# Start kubernetes-api-watch as a separate process
process_w1 = subprocess.Popen(['python3', 'k8s-watch.py'])

# Start gh-watch-dog as a separate process
process_w2 = subprocess.Popen(['python3', 'watch-dog.py'])

# Define a signal handler function
def signal_handler(signum, frame):
    # Terminate the child processes if they are still running
    if process_w1.poll() is None:
        process_w1.terminate()
    if process_w2.poll() is None:
        process_w2.terminate()

    # Wait for the processes to complete
    try:
        process_w1.wait(timeout=0)  
        process_w2.wait(timeout=0)  
    except subprocess.TimeoutExpired:
        # If the processes don't finish within the timeout, force them to terminate
        process_w1.kill()
        process_w2.kill()

# Register the signal handler for the SIGINT signal (Ctrl+C)
signal.signal(signal.SIGINT, signal_handler)

# Wait for the processes to complete
process_w1.wait()
process_w2.wait()

