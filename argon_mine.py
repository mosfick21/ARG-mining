#!/usr/bin/env python3
"""
argon-miner: one-command launcher for the official Argonmine (ARG) node miner.

    python argon_mine.py                      # asks for the payout address
    python argon_mine.py arg1q...             # address as argument
    python argon_mine.py arg1q... --threads 4 # fixed threads, skip auto-tuning
    python argon_mine.py arg1q... --retune    # measure this machine again
    python argon_mine.py arg1q... --dry-run   # set up and print the plan only

Only the payout ADDRESS is used. Your 24 words never touch this machine.
"""
import argparse, hashlib, json, os, platform, re, secrets, shutil, signal, subprocess, sys, time, urllib.request, zipfile

VERSION = "1.1.0"
BASE = "https://docs.argonmine.com/downloads"
SAFE_MIB_PER_THREAD = 16      # Argon2id uses 8 MiB per attempt; keep headroom
RESERVED_MIB = 400            # node, OS and anything else running
RPC_PORT = 9332
TUNE_WARMUP_S = 20
TUNE_MEASURE_S = 40


def say(msg):
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


# ------------------------------------------------------------------ machine
def workdir():
    root = os.getcwd() if os.access(os.getcwd(), os.W_OK) else os.path.expanduser("~")
    d = os.path.join(root, "argonmine")
    os.makedirs(d, exist_ok=True)
    return d


def usable_cpus():
    try:
        n = len(os.sched_getaffinity(0))
    except Exception:
        n = os.cpu_count() or 1
    try:  # cgroup v2 quota
        q, p = open("/sys/fs/cgroup/cpu.max").read().split()
        if q != "max":
            n = min(n, max(1, int(q) // int(p)))
    except Exception:
        try:  # cgroup v1 quota
            q = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
            p = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
            if q > 0:
                n = min(n, max(1, q // p))
        except Exception:
            pass
    return max(1, n)


def physical_cores(fallback):
    try:
        pairs, phys, core = set(), None, None
        for line in open("/proc/cpuinfo"):
            if line.startswith("physical id"):
                phys = line.split(":")[1].strip()
            elif line.startswith("core id"):
                core = line.split(":")[1].strip()
            elif not line.strip() and core is not None:
                pairs.add((phys, core))
                phys = core = None
        return max(1, min(len(pairs), fallback)) if pairs else fallback
    except Exception:
        return fallback


def free_mib():
    avail = None
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable:"):
                avail = int(line.split()[1]) // 1024
    except Exception:
        pass
    for f in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            v = open(f).read().strip()
            if v != "max" and int(v) < 1 << 60:
                lim = int(v) // (1024 * 1024)
                avail = min(avail, lim) if avail else lim
        except Exception:
            pass
    return avail or 1024


def cpu_model():
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or platform.machine()


# ------------------------------------------------------------------ install
def arch():
    m = platform.machine().lower()
    if m in ("x86_64", "amd64"):
        return "amd64"
    if m in ("aarch64", "arm64"):
        return "arm64"
    sys.exit(f"Unsupported CPU architecture: {m}")


def fetch(url, dst):
    req = urllib.request.Request(url, headers={"User-Agent": "argon-miner"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f)


def install(wd):
    name = f"argonmine-{VERSION}-linux-{arch()}"
    binp = os.path.join(wd, name, "argonmined")
    if os.path.isfile(binp):
        return binp
    z, sums = os.path.join(wd, name + ".zip"), os.path.join(wd, "SHA256SUMS")
    say(f"Downloading argonmined {VERSION}")
    fetch(f"{BASE}/{name}.zip", z)
    fetch(f"{BASE}/SHA256SUMS", sums)
    want = next((l.split()[0] for l in open(sums) if l.strip().endswith(name + ".zip")), None)
    got = hashlib.sha256(open(z, "rb").read()).hexdigest()
    if not want or want != got:
        os.remove(z)
        sys.exit("Checksum mismatch. Download refused.")
    say("Checksum verified")
    with zipfile.ZipFile(z) as zz:
        zz.extractall(wd)
    os.chmod(binp, 0o755)
    os.remove(z)
    return binp


# ------------------------------------------------------------------ node control
class Node:
    def __init__(self, binp, datadir, addr, threads, tag, quiet, mine=True):
        self.token = secrets.token_hex(16)
        cmd = [binp, "-network", "mainnet", "-datadir", datadir, "-listen", "none",
               "-rpc", f"127.0.0.1:{RPC_PORT}", "-rpctoken", self.token]
        if mine:
            cmd += ["-mine", addr, "-threads", str(threads)]
        if tag:
            cmd += ["-tag", tag]
        self.quiet = quiet
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        os.set_blocking(self.p.stdout.fileno(), False)

    def rpc(self, method, params=None):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{RPC_PORT}/", data=body,
                                     headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode()).get("result")

    def pump(self, seconds):
        """Drain the node log for `seconds`; print only useful lines."""
        end = time.time() + seconds
        while time.time() < end and self.p.poll() is None:
            line = self.p.stdout.readline()
            if not line:
                time.sleep(0.2)
                continue
            low = line.lower()
            if not self.quiet and any(k in low for k in ("error", "found", "mined", "warn")):
                print(line.rstrip(), flush=True)

    def mining(self):
        try:
            i = self.rpc("getmininginfo") or {}
            return float(i.get("hashrate") or 0), int(i.get("blocksfound") or 0)
        except Exception:
            return 0.0, 0

    def chain(self):
        """-> (our height, best known height). Synced when initialblockdownload is False."""
        try:
            i = self.rpc("getblockchaininfo") or {}
            h = int(i.get("blocks") or 0)
            peers = self.rpc("getpeerinfo") or []
            top = max([h] + [int(p.get("startheight") or 0) for p in peers])
            self.ibd = bool(i.get("initialblockdownload", True)) or not peers
            return h, top
        except Exception:
            self.ibd = True
            return 0, 0

    def stop(self):
        if self.p.poll() is None:
            self.p.terminate()
            try:
                self.p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.p.kill()


# ------------------------------------------------------------------ tuning
def machine_key(cpus):
    return f"{cpu_model()}|{cpus}|{arch()}"


def candidates(cpus, phys, mem_cap):
    c = {cpus, max(1, cpus - 1), phys}
    return sorted({min(x, mem_cap) for x in c}, reverse=True)


def sync(binp, datadir, addr):
    say("Syncing the chain (first start takes a few minutes)")
    n = Node(binp, datadir, addr, 0, "", quiet=True, mine=False)
    try:
        t0, last = time.time(), 0
        while time.time() - t0 < 900 and n.p.poll() is None:
            n.pump(5)
            h, top = n.chain()
            if h and not n.ibd and h >= top:
                say(f"Chain synced at block {h:,}")
                return
            if h - last >= 200:
                say(f"  block {h:,} / {top:,}")
                last = h
        say("Sync still running, continuing anyway")
    finally:
        n.stop()


def measure(binp, datadir, addr, threads):
    n = Node(binp, datadir, addr, threads, "", quiet=True)
    try:
        n.pump(TUNE_WARMUP_S)
        samples, end = [], time.time() + TUNE_MEASURE_S
        while time.time() < end and n.p.poll() is None:
            n.pump(5)
            hr, _ = n.mining()
            if hr > 0:
                samples.append(hr)
        return sum(samples) / len(samples) if samples else 0.0
    finally:
        n.stop()


def tune(binp, datadir, addr, cpus, phys, mem_cap, cache):
    cands = candidates(cpus, phys, mem_cap)
    if len(cands) == 1:
        best = cands[0]
    else:
        mins = len(cands) * (TUNE_WARMUP_S + TUNE_MEASURE_S) // 60 + 1
        say(f"Auto-tuning: testing {cands} threads (~{mins} min, once per machine)")
        res = {}
        for t in cands:
            res[t] = measure(binp, datadir, addr, t)
            say(f"  {t:>3} threads -> {res[t]:,.1f} H/s")
        best = max(res, key=lambda k: (res[k], -k))
        if res[best] <= 0:
            best = cands[0]
    json.dump({"key": machine_key(cpus), "threads": best}, open(cache, "w"))
    say(f"Best setting: {best} threads")
    return best


# ------------------------------------------------------------------ main
def get_address(cli):
    addr = (cli or os.environ.get("ARG_ADDRESS") or "").strip()
    while not re.fullmatch(r"arg1[02-9ac-hj-np-z]{20,90}", addr):
        if addr:
            print("Not a valid ARG address (it must start with arg1).")
        try:
            addr = input("ARG payout address: ").strip()
        except EOFError:
            sys.exit("No address given. Pass it as an argument or set ARG_ADDRESS.")
    return addr


def main():
    ap = argparse.ArgumentParser(description="Argonmine miner launcher")
    ap.add_argument("address", nargs="?", help="arg1... payout address (or env ARG_ADDRESS)")
    ap.add_argument("--threads", type=int, help="fixed thread count, skips auto-tuning")
    ap.add_argument("--retune", action="store_true", help="ignore the saved tuning and measure again")
    ap.add_argument("--tag", default="", help="optional public label written into blocks you find")
    ap.add_argument("--dry-run", action="store_true", help="set up and print the plan only")
    a = ap.parse_args()

    addr = get_address(a.address)
    wd = workdir()
    binp = install(wd)
    datadir, cache = os.path.join(wd, "data"), os.path.join(wd, "tune.json")

    cpus = usable_cpus()
    phys = physical_cores(cpus)
    mem = free_mib()
    mem_cap = max(1, (mem - RESERVED_MIB) // SAFE_MIB_PER_THREAD)
    say(f"CPU: {cpu_model()} | threads: {cpus} | cores: {phys} | free RAM: {mem} MiB")
    say(f"Payout: {addr[:10]}...{addr[-6:]}")
    if a.dry_run:
        say(f"Thread candidates: {candidates(cpus, phys, mem_cap)}")
        return

    stop = {"v": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("v", True))

    if a.threads:
        threads = max(1, min(a.threads, mem_cap))
    else:
        threads = None
        if not a.retune and os.path.isfile(cache):
            try:
                c = json.load(open(cache))
                if c.get("key") == machine_key(cpus):
                    threads = int(c["threads"])
                    say(f"Using saved tuning: {threads} threads")
            except Exception:
                pass
        if not threads:
            sync(binp, datadir, addr)
            threads = tune(binp, datadir, addr, cpus, phys, mem_cap, cache)

    say(f"Mining with {threads} threads. Report every 60s. Stop with Ctrl+C.")
    restarts = 0
    while not stop["v"]:
        n = Node(binp, datadir, addr, threads, a.tag, quiet=False)
        try:
            while n.p.poll() is None and not stop["v"]:
                n.pump(60)
                hr, found = n.mining()
                h, _ = n.chain()
                say(f"Block {h:,} | {hr:,.1f} H/s | blocks found: {found}")
        except KeyboardInterrupt:
            stop["v"] = True
        finally:
            n.stop()
        if stop["v"]:
            break
        restarts += 1
        say(f"Miner exited (code {n.p.returncode}), restarting in 5s (#{restarts})")
        time.sleep(5)
    say("Stopped")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        say("Stopped")
