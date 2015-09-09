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

if [ ! -f ${PIDFILE} ]; then
  echo "Zerosap is not running (or PID file is missing)."
  exit 0
fi

PID=$(cat ${PIDFILE})
echo "Stopping Zerosap (pid: ${PID}) ..."

kill -TERM ${PID}
WAIT_TIMEOUT=20
while ps -p ${PID} > /dev/null && [ $WAIT_TIMEOUT > 0 ]; do sleep 0.1; ((WAIT_TIMEOUT--)); done

if ps -p ${PID} > /dev/null; then
  echo "Zerosap (pid: ${PID}) failed to stop."
  exit 1
else
  rm -f ${PIDFILE}
  echo "Zerosap (pid: ${PID}) has stopped."
fi

EOF
