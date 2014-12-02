zerosap
=======

Library to call SAP pyRFC from NodeJs

Dispatcher API
--------------
Using this module, NodeJS can dispatch RFC calls to a SAP backend system.

More API Documentation coming soon. Meanwhile, look at app.js .

Worker
------
Zerosap uses the official SAP pyRFC python library, and wraps it as the "Zerosap Worker".  
As a first-class library fully supported by SAP, pyRFC ensures that Zerosap has great stability and full capabilities (e.g. RFC server scenario).

We support two ways of running this worker:

### A. Embedded into NodeJs
- NodeJs automatically manages the Python worker process via a zerorpc bridge.
- This scenario is great for getting started.

### B. Remote Daemon
- A "Zerosap Worker" runs as a daemon on a Python-capable host within the internal network/LAN.  
- The host can be the UNIX/Windows server that also hosts SAP Netweaver itself (or another host that have access to the RFC Ports of the target SAP system).

- The Worker connects back to the NodeJS Dispatcher to receive instructions via a secure zerorpc channel.  
- Multiple Worker instances enable NodeJS to act as a reverse proxy and load balancer, as RFC requests are fanned out from NodeJS to multiple target SAP backend systems.  
- Elliptic-curve cryptography is used.  
- This scenario is great where security and performance is paramount.

### Dependencies
- libzmq.so >= 4.0.5 (with libsodium support)
- zerorpc >= 0.4.4
- pyrfc >= 1.9.4
- daemonize >= 2.3.1

### Installation
#### ZeroRPC Installation
##### Libsodium
- [Reference](http://doc.libsodium.org/installation/README.html)
- [Tarball](https://github.com/jedisct1/libsodium/releases)

```bash
	wget https://github.com/jedisct1/libsodium/releases/download/1.0.1/libsodium-1.0.1.tar.gz
	dig +dnssec +short txt libsodium-1.0.1.tar.gz.download.libsodium.org
	cat libsodium-1.0.1.tar.gz | openssl dgst -sha256  # If the output is not the same as from the previous command, abort as the downloaded file has been tampered with.
	tar -xvf libsodium-1.0.1.tar.gz
	cd libsodium-1.0.1
	./configure
	make && make check  # Ensure all tests pass.
	sudo make install
	ls /usr/local/lib/
```

##### ZeroMQ
- [Reference](http://zeromq.org/intro:get-the-software)

```bash
	wget http://download.zeromq.org/zeromq-4.0.5.tar.gz
	tar -xvf zeromq-4.0.5.tar.gz
	cd zeromq-4.0.5
	sudo yum install gcc-c++
	./configure
	make && make check  # Ensure all tests pass.
	sudo make install
	ls /usr/local/lib/
```

##### ZeroRPC for Python
- ZeroRPC cannot be installed directly via pip / easy_install due to pyzmq that is pinned to an outdated version (version 14.1.1 & above has solved the issue).
- These instructions will install directly from their GitHub master (for libsodium cryptographic support):

```bash
	wget https://github.com/dotcloud/zerorpc-python/archive/master.zip
	unzip master.zip
	cd zerorpc-python-master/
	nano setup.py   # Change to pyzmq>=14.1.1
	PKG_CONFIG_PATH=/usr/local/lib/pkgconfig python setup.py install
```

#### pyRFC Installation
- Installing pyrfc requires the SAP NW RFC SDK that is distributed on the SAP Support Portal.
- Further instructions [here](http://sap.github.io/PyRFC/install.html).
- [Downloads](https://github.com/SAP/PyRFC/tree/master/dist)

```bash
	wget https://raw.githubusercontent.com/SAP/PyRFC/master/dist/pyrfc-1.9.4-py2.7-linux-x86_64.egg
	easy_install pyrfc-1.9.4-py2.7-linux-x86_64.egg
```

#### Daemonize Instalation
- The easiest to install.

```bash
	pip install daemonize
```

### Configuration
The zerosap worker reads environmental variables for configuration:

#### start.sh
```bash
	#!/bin/bash
	DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
	cd "${DIR}"

	# source /opt/rh/python27/enable
	scl enable python27 - << \EOF

	source bin/activate

	export USER=zerosap
	export GROUP=zerosap 
	export ZEROSAP_ZMQ_HUB=tcp://<ipaddress of nodejs zerosap-dispatcher>:4801

	cd zerosap/
	ZEROSAP_RFC_CLIENT=100 ZEROSAP_RFC_USER=<username> ZEROSAP_RFC_PASSWD=<password> python bin/zerosap.py "$@"

	EOF
```

### Startup
- Starting the zerosap worker daemon is simple:

```bash
	sudo useradd -r zerosap
	sudo usermod -a -G zerosap prdadm
	
	chmod +x /usr/sap/PythonVE/py27-pyrfc/start.sh
	sudo /usr/sap/PythonVE/py27-pyrfc/start.sh
	tail -f /tmp/zerosap.log
```
