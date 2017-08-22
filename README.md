# RECONN
RECONN (short for reconnaissance) is a surveying/observatory tool on a
given file. It monitors file continuously to look out for defined patterns.

RECONN will REad CONtinuously a file, as and when the contents are written
to it, by another process(es). For defined set of regular expressions, RECONN
tool will log for every match.

This is useful for to monitor any log file for a set of events.

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
