# RECONN
RECONN (short for reconnaissance) is a surveying/observatory tool on a
given file, mainly log files. RECONN monitors file continuously, to look out
for defined patterns.

RECONN will REad CONtinuously a file, as and when the contents are written
to it, by another process(es). For defined set of regular expressions, RECONN
tool will log for every match. RECONN can also be configured to send out a set of
matched patterns to RMQ service.

RECONN is useful to monitor any log file for a set of patterns.

RECONN lives forever and monitors contents of a file. RECONN can be configured
with timeout after which it will self terminate. RECONN can also be configured
to match a defined pattern and terminate when the match is found.

RECONN uses watchdog module to register and receive callbacks for file updates.
This is how RECONN monitors file changes.

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


## Developing and testing RECONN
##### Unit test execution:
Unit tests are located under: reconn/reconn/tests/unit/
```
$ cd reconn
$ tox -epy27
```


##### Functional test execution:
Functional tests are located under: reconn/reconn/tests/functional/
```
$ cd reconn
$ tox -e functional
```
