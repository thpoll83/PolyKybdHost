PolyHost
--------

Simply do::
python -m polyhost


It is recommended to use a virtual environment and install the packages of requirements.txt

Autostart
~~~~~~~~~

On the first normal run, PolyHost registers itself to start automatically when you log in.
On Windows this is a per-user **scheduled task** that triggers *at log on* (running the proven
venv launcher windowless via ``wscript``, so no console window flashes). A logon task starts
earlier than a Startup-folder shortcut, which Windows deliberately throttles. If creating the
task is refused (e.g. Task Scheduler locked down by company policy), PolyHost automatically
falls back to a Startup-folder shortcut, so it still autostarts without needing admin rights.
On Linux a ``.desktop`` autostart entry is used, on macOS a ``launchd`` agent.

The line ``Autostart in place: ...`` printed at startup tells you which mechanism is active.

Run with ``--portable`` to skip autostart registration; if an entry already exists from a
previous run it is removed, so a portable run leaves nothing behind::

  python -m polyhost --portable

For debug logs run with --debug::
python -m polyhost --debug

To forward window info from a remote host run  with --host on the remote system::
python -m polyhost --host IP_ADDR_OF_HOST|HOST_NAME

And run without parameter on the computer with the PolyKybd connected & specify the
remote host in overlay-mapping.poly.yaml like this::
nxplayer:
  remote: IP_ADDR_OF_REMOTE|NAME_OF_REMOTE