# Flush all iptables rules
sudo iptables -F
sudo iptables -t nat -F
sudo iptables -t mangle -F

# Delete all user-defined chains
sudo iptables -X

# Reset default policies
sudo iptables -P INPUT ACCEPT
sudo iptables -P FORWARD ACCEPT
sudo iptables -P OUTPUT ACCEPT

