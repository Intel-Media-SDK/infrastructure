# Infrastructure of Intel® Media SDK
Repository has all things needed for deploying public infrastructure of Intel® Media SDK.  
  
Repository contains:  
- Buildbot configuration
- Build scripts
- Small set of smoke tests (called "ted")
- Test adapter (called "ted_adapter")


# How to deploy
### Deploy master Buildbot
Dependencies:
- CentOS 7.3
- python 3.6.x
- postgresql

```bash
sudo pip3 install buildbot==0.9.13 buildbot-console-view==0.9.13 buildbot-waterfall-view==0.9.13 buildbot-grid-view==0.9.13 buildbot-www==0.9.13
```
Hint:  
It can work with default DB (sqlite) for that it needs to change next value in `bb/master/config.py`:
```python
DATABASE_URL = "sqlite:///state.sqlite"
```

Deploy:
```bash
git clone https://github.com/Intel-Media-SDK/infrastructure.git
cd ./infrastructure/bb/
mv ./master ./tmp_master

buildbot create-master master

cp ./tmp_master/* ./master/
rm -rf ./tmp_master/

#Configure Github`s webhook in your repository in settings-webhooks and create Github`s token after that do:
cd master
cp ./secrets.py.example ./secrets.py
nano secrets.py #add your real values

#Start Master Buildbot
cd ..
buildbot start master

```
### Deploy build box Worker Buildbot
Dependencies:
- CentOS 7.3
- python 3.6.x
- Intel® Media Server Studio 2017 R3
  - Minimal needed rpms from MSS:
      ```bash
      intel-opencl-xxx-xxx.x86_64.rpm
      intel-opencl-cpu-xxx-.x86_64.rpm
      intel-opencl-devel-xxx-xxx.x86_64.rpm
      libdrm-xxx-xxx.el7.centos.x86_64.rpm
      libdrm-devel-xxx-xxx.el7.centos.x86_64.rpm
      libva-xxx-xxx.el7.centos.x86_64.rpm
      libva-devel-xxx-xxx.el7.centos.x86_64.rpm
      ```


```bash
sudo pip3 install buildbot-worker==0.9.13
sudo pip3 install gitpython==2.1.5 tenacity==4.5.0 txrequests txgithub service_identity

#Recommended list of packages
sudo yum groupinstall "Development Tools"
sudo yum install cmake git
sudo yum install libX11 libXext libXfixes libGL libGL-devel libX11-devel 
```
**Read more about the packages [here](docs/packages.md).**

Deploy:
```bash
buildbot-worker create-worker "<your_worker_name>" "<your_IP>:9000" "<your_worker_name>" "pass"

git clone https://github.com/Intel-Media-SDK/infrastructure.git ./worker-build/build-master-branch/infrastructure
git clone https://github.com/Intel-Media-SDK/product-configs.git ./worker-build/build-master-branch/product-configs

mkdir ./<your_worker_name>/build-other-branches
cp -r ./<your_worker_name>/build-master-branch/{infrastructure,product-configs} ./<your_worker_name>/build-other-branches/

#Start Worker Buildbot
buildbot-worker start <your_worker_name>
```

### Deploy test box Worker Buildbot
Dependencies:
- CentOS 7.3
- python 3.6.x
- Intel® Media Server Studio 2017 R3
  - Minimal needed rpms:
      ```bash
      intel-linux-media-xxx-xxx.el7.centos.x86_64.rpm  # Will install iHD_drv_video.so etc
      ```

```bash
#Install git lfs
sudo yum install curl epel-release
curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.rpm.sh | sudo bash
sudo yum install git-lfs
git lfs install

#After that do the same things as described in section "build box Worker"
```

Deploy:
```bash
buildbot-worker create-worker "<your_worker_name>" "<your_IP>:9000" "<your_worker_name>" "pass"

git clone https://github.com/Intel-Media-SDK/infrastructure.git ./<your_worker_name>/test/infrastructure

#Start Worker Buildbot
buildbot-worker start <your_worker_name>
```
Hint:  
To use graphical driver (from Media Server Studio) with tests as not root user do: 
```bash
usermod -a -G video <mediasdk_user>
#And restart session!
```

### Hint
You can update all configurations by simple executing `git pull` command!


# License
This project is licensed under MIT license. See [LICENSE](./LICENSE) for details.
