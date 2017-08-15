# RECONN
RECONN (short for reconnaissance) is a surveying/observatory tool of VM instance boot stages.

RECONN will REad CONtinuosly console.log file of a VM instance, as the contents are
written to it.

## Download, Setup and Installing RECONN
```
$ virtualenv -v -p python2.7 virtual_env
$ source virtual_env/bin/activate
$ cd reconn
$ pip -v install .
```

## Running reconn
```
$ reconn --config-file=./etc/reconn/reconn.conf --log-file=/var/log/reconn/reconn.log
```
