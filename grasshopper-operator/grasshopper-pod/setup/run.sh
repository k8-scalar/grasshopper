apt update
apt install -y software-properties-common
add-apt-repository ppa:deadsnakes/ppa
apt update
apt install -y python3.10
python3.10 --version

apt install -y python3.10-distutils
curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3.10 get-pip.py
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
update-alternatives --config python3
update-alternatives --install /usr/bin/pip pip /usr/local/bin/pip3.10 1
pip install --upgrade pip setuptools wheel

apt update
apt install -y python3.10-dev build-essential
apt install -y python3-apt
apt-get install -y libffi-dev
apt install -y pkg-config
apt install -y cmake

pip install --upgrade pip setuptools wheel
apt-get install -y wget libdbus-1-dev libdbus-glib-1-dev

pip install --ignore-installed -r setup/requirements.txt


