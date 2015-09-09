#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${DIR}"

# source /opt/rh/python27/enable
PARAMS=$@ scl enable python27 - << \EOF

source bin/activate

export USER=zerosap
export GROUP=zerosap
export ZEROSAP_ZMQ_HUB=tcp://10.0.0.5:4801
export PIDFILE=/var/run/zerosap.pid

echo "Starting Zerosap (connect: ${ZEROSAP_ZMQ_HUB}) ..."

cd zerosap/
ZEROSAP_RFC_CLIENT=100 ZEROSAP_RFC_USER=userid ZEROSAP_RFC_PASSWD=userpasswd python bin/zerosap.py ${PARAMS}

PID=$(cat ${PIDFILE})
if ps -p ${PID} > /dev/null; then
  echo "Zerosap (pid: ${PID}) has started."
else
  echo "Zerosap (pid: ${PID}) failed to start."
  exit 1
fi

EOF
