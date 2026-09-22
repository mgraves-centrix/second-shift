# Switching the reasoner to its systemd unit

**Decided 22 Sep: do it now.** `deploy/spark/second-shift-reasoner.user.service`
was written on 2 Sep and has never been started. The container serving local
inference was started by hand, has no unit, and has been up for weeks.

**Status: never run.** Every step below is written from what the unit and the
running container actually say, not from having done it. The verification at
the end is how you find out which part of this is wrong.

Two things are being fixed, and they are not the same thing:

| | Now | After |
|---|---|---|
| Survives a reboot | No — the container was started with no unit behind it | Yes |
| Reachable from | Every interface: it publishes `0.0.0.0:8200` | Loopback only: the unit binds `127.0.0.1:8200:8000` |

The second is the one that is an airlock decision rather than an uptime one.
Principle 2 makes the machine's reachability a decision about privacy, and
everything the reasoner is asked is somebody's idea.

---

## The failure this procedure exists to avoid

**The unit removes a container that is not the one running.**

```
ExecStartPre=-/usr/bin/docker rm -f second-shift-reasoner   # what the unit removes
nemotron-lightning                                          # what is actually running
```

The leading `-` means removing a container that is not there succeeds. Then
`docker run -p 127.0.0.1:8200:8000` fails, because `nemotron-lightning` still
holds host port 8200. `Restart=always` with `RestartSec=15` turns that into a
unit failing every fifteen seconds.

**And nothing would look wrong.** The old container is still serving on the port
the probe checks, so `ops doctor` reports the reasoner healthy, the capability
probe reports it healthy, and a night runs normally. The only thing that would
be false is the thing the switch was for: a reboot would still end local
inference, and the port would still be open to the tailnet.

So step 2 removes it by its real name, and step 1 is how you find out what that
name is on the day rather than trusting this document.

---

## The procedure

### 1. Find out what is actually running and whether it is safe to touch

```bash
docker ps --format '{{.Names}}\t{{.Ports}}'
python -m secondshift.ops night-status
```

`night-status` exits **3** while a night holds the lock and **0** when it does
not. `docker rm -f` on the reasoner during a night kills that night — and the
night is the product, so this is not a formality. It reads the advisory lock the
night holds rather than an open run in the database, because an open run is also
what a night killed last week left behind.

If a night is in flight, stop and come back. There is no safe way to do this
underneath one.

### 2. Stop the hand-started container, by its real name

```bash
python -m secondshift.ops night-status && docker rm -f <the name from step 1>
```

The `&&` is the point: it is the difference between a check somebody read and a
check that held. Local inference is down from here until step 3 finishes.

### 3. Install and start the unit

```bash
systemctl --user daemon-reload
systemctl --user enable --now second-shift-reasoner
```

The user variant needs no sudo and no substitution — it uses `%h`. `loginctl
enable-linger` is already enabled on that machine, which is what makes a user
service start without a login.

Roughly **three minutes** from a warm HuggingFace cache; a cold cache pulls 52
shards first. The unit's `TimeoutStartSec=1800` is sized for that, and a
shorter deadline would be a boot loop.

```bash
journalctl --user -u second-shift-reasoner -f
```

### 4. Verify, and do not accept the probe alone

```bash
python -m secondshift.ops doctor --backups <the backup directory>
systemctl --user is-enabled second-shift-reasoner   # expect: enabled
ss -ltnp | grep 8200                                # expect: 127.0.0.1:8200, not 0.0.0.0
```

`doctor`'s `local reasoner` line checks the port `config/models.toml` allocates
and the name the probe expects. **It would have said the same thing before the
switch**, because the old container answered on the same port — which is why
`is-enabled` and the listening address are here too. Those two are the ones that
actually changed.

### 5. The test that is the whole point

```bash
sudo reboot
```

Then, once it is back:

```bash
python -m secondshift.ops doctor --backups <the backup directory>
systemctl --user list-units --type=service --all | grep second-shift
```

The API, the brain sync and the reasoner all serving, with nobody having logged
in. That is the claim; `systemctl status` before a reboot is not evidence for
it.

---

## If it goes wrong

The old container is gone by step 2, so a failed step 3 leaves the machine with
no reasoner. That is recoverable and the night degrades rather than lying —
`night/__main__.py` exits `EXIT_NO_REASONER` rather than running against a
placeholder, which is the behavior that exists precisely so a missing model is
visible instead of silently producing the prompt back as every artifact.

To get inference back immediately while working out what the unit is doing,
start the container by hand again with the unit's own flags — they are in
`deploy/spark/second-shift-reasoner.user.service` and were verified by Spike B.
Use `-p 127.0.0.1:8200:8000` even by hand; there is no reason to reopen the port
to the tailnet while debugging a unit.
