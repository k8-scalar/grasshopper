FROM ubuntu:24.04

WORKDIR /app

COPY setup/ ./setup

# Step 1: Pre-install needed tools to run run.sh
RUN apt update && apt install -y \
    curl wget git 

RUN chmod +x setup/run.sh && ./setup/run.sh

# Copy the code section.
COPY code/ ./code

# Use python3.10 to run the app
CMD ["python3.10", "main_operator.py"]
