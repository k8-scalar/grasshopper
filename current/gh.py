import subprocess
import signal

# Start kubernetes-api-watch as a separate process
process_w1 = subprocess.Popen(['python3', 'k8s-watch.py'])

# Start gh-watch-dog as a separate process
process_w2 = subprocess.Popen(['python3', 'watch-dog.py'])

# Define a signal handler function
def signal_handler(signum, frame):
    # Terminate the child processes when the main script is closed
    process_w1.terminate()
    process_w2.terminate()

# Register the signal handler for the SIGINT signal (Ctrl+C)
signal.signal(signal.SIGINT, signal_handler)

# Wait for the processes to complete
process_w1.wait()
process_w2.wait()
