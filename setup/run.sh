sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.10
python3.10 --version
sudo apt install -y python3.10-distutils
curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py
sudo python3.10 get-pip.py
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 2
sudo update-alternatives --config python3
sudo update-alternatives --install /usr/bin/pip pip /usr/local/bin/pip3.10 1
sudo apt update
sudo apt install -y python3-dev build-essential
sudo apt install -y python3-apt
sudo apt-get install -y libffi-dev
sudo apt install -y pkg-config
sudo apt install -y cmake
sudo apt install -y libcairo2 libcairo2-dev
sudo apt install -y meson ninja-build
sudo apt install -y libgirepository1.0-dev gir1.2-gtk-4.0
pip install --upgrade pip setuptools wheel
sudo apt-get install -y libdbus-1-dev libdbus-glib-1-dev
pip install -r requirements.txt
echo "export PATH=\$PATH:\$HOME/.local/bin" >> ~/.bashrc