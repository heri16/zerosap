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
We support two ways of running this worker.

### A. Embedded into NodeJs
NodeJs automatically manages the Python worker process via a zerorpc bridge. This scenario is great for getting started.

### B. Remote Daemon
A "Zerosap Worker" runs as a daemon on a Python-capable host within the internal network/LAN.
The host can be the UNIX/Windows server that also hosts SAP Netweaver itself (or another host that have access to the RFC Ports of the target SAP system).

The Worker connects back to the NodeJS Dispatcher to receive instructions via a secure zerorpc channel.
Multiple Worker instances enable NodeJS to act as a reverse proxy and load balancer, as RFC requests are fanned out from NodeJS to multiple target SAP backend systems. 
Elliptic-curve cryptography is used.
This scenario is great where security and performance is paramount.

### Dependencies
- libzmq.so with libsodium support
- zerorpc==0.4.4
- pyrfc==1.9.4
- daemonize==2.3.1

### Configuration
The zerosap worker reads environmental variables for configuration:

#### start.sh
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
