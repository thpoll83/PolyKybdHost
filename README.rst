PolyHost
--------

Simply do::
python -m polyhost


It is recommended to use a virtual environment and install the packages of requirements.txt

For debug logs run with --debug::
python -m polyhost --debug

To forward window info from a remote host run  with --host on the remote system::
python -m polyhost --host IP_ADDR_OF_HOST|HOST_NAME

And run without parameter on the computer with the PolyKybd connected & specify the
remote host in overlay-mapping.poly.yaml like this::
nxplayer:
  remote: IP_ADDR_OF_REMOTE|NAME_OF_REMOTE