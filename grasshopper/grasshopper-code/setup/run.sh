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

# apt install -y libcairo2 libcairo2-dev
# apt install -y meson ninja-build
# apt install -y libgirepository1.0-dev gir1.2-gtk-4.0

pip install --upgrade pip setuptools wheel
apt-get install -y wget libdbus-1-dev libdbus-glib-1-dev

# python3.10 -m venv /venv
# source /venv/bin/activate
# pip install --upgrade pip setuptools
pip install -r --ignore-installed setup/requirements.txt

# curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
# chmod 700 get_helm.sh
# wget https://get.helm.sh/helm-v3.16.2-linux-amd64.tar.gz
# ./get_helm.sh
# echo "export PATH=\$PATH:\$HOME/.local/bin" >> ~/.bashrc
