<div align="center">

# ⛏️ ARG Mining

**A one-command, self-tuning miner for [Argonmine](https://argonmine.com) (ARG).**

Downloads the official node, verifies it, finds the fastest setting for your hardware, and mines around the clock.

![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Linux%20x86--64%20%7C%20ARM64-informational)
![Dependencies](https://img.shields.io/badge/dependencies-none-success)
![Node](https://img.shields.io/badge/argonmined-1.1.0-orange)

</div>

---

## Contents

- [What is Argonmine](#what-is-argonmine)
- [How mining works](#how-mining-works)
- [Features](#features)
- [Quick start](#quick-start)
- [Usage](#usage)
- [Auto-tuning](#auto-tuning)
- [Rewards](#rewards)
- [Security](#security)
- [FAQ](#faq)

---

## What is Argonmine

Argonmine is a standalone proof-of-work blockchain with its own coin, **ARG**. New ARG is created only by mining. There is no premine and no sale.

| | |
|---|---|
| **Proof of work** | Argon2id, 8 MiB of memory per attempt |
| **Block time** | 10 minutes |
| **Block reward** | 50 ARG, halving every 210,000 blocks |
| **Supply cap** | 21,000,000 ARG |
| **Difficulty** | ASERT, one-day half-life |
| **Reward maturity** | 100 blocks (about 17 hours) |
| **Addresses** | bech32m, starting with `arg1` |

Every attempt needs 8 MiB of memory, so speed is limited by memory bandwidth rather than raw compute. Ordinary CPUs stay competitive and **no GPU is needed**.

---

## How mining works

```
 ┌──────────────┐   template   ┌──────────────┐   attempts   ┌──────────────┐
 │  Argonmine   │ ───────────▶ │  argonmined  │ ───────────▶ │ Argon2id x N │
 │   network    │ ◀─────────── │  (your node) │ ◀─────────── │   threads    │
 └──────────────┘  valid block └──────────────┘   solution   └──────────────┘
                                      │
                                      ▼
                         49.5 ARG paid to your address
```

1. Your node syncs the chain and builds a block that pays **your address**.
2. Each thread hashes the block header with Argon2id, trying nonce after nonce.
3. When a hash lands below the network target, the block is valid and broadcast.
4. The reward is written into the block itself and paid straight to your address.

Your chance of finding the next block equals your share of the network hashrate.

---

## Features

- 🔐 **Verified binary** — uses the official `argonmined` release and checks it against the published `SHA256SUMS`. A mismatch aborts the run.
- ⚡ **Auto-tuning** — benchmarks realistic thread counts on the live network and keeps the fastest.
- 🧠 **Container-aware** — reads cgroup CPU and memory limits, not just what the OS reports.
- ♻️ **Self-healing** — restarts the miner automatically if it exits.
- 📊 **Clean output** — one line per minute: height, hashrate, blocks found.
- 📦 **Zero dependencies** — Python standard library only.
- 🎯 **Nothing hard-coded** — the payout address is given at run time.

---

## Quick start

### 1. Create a wallet

Open the Argonmine app and create a wallet:

**👉 [app.argonmine.com](https://app.argonmine.com/?ref=arg1qx7qy47eetvlr86j88g6c2e9jgddrtm3h6dq4043zxwsscua5kj5q2npenc)**

Write down your **24 words** and keep them offline. They are the only backup of your wallet.

### 2. Copy your address

In the app go to **Wallet → Receive** and copy your address. It starts with `arg1`.

### 3. Run the miner

```bash
git clone https://github.com/mosfick21/ARG-mining.git
cd ARG-mining
python3 argon_mine.py arg1q...your_address
```

That's it. The first run downloads the node, syncs the chain, tunes itself, then starts mining.

---

## Usage

```bash
python3 argon_mine.py [ADDRESS] [OPTIONS]
```

The address can be passed as an argument, through the `ARG_ADDRESS` environment variable, or typed when prompted:

```bash
export ARG_ADDRESS=arg1q...your_address
python3 argon_mine.py
```

| Option | Description |
|---|---|
| `--threads N` | Use a fixed thread count and skip auto-tuning |
| `--retune` | Ignore the saved tuning and benchmark again |
| `--tag TEXT` | Optional public label written into blocks you find |
| `--dry-run` | Download, verify and print the plan without mining |

Stop at any time with `Ctrl+C`.

### Run in the background

```bash
nohup python3 argon_mine.py arg1q...your_address > miner.log 2>&1 &
tail -f miner.log
```

### Example output

```
[12:00:00] CPU: AMD EPYC 7B13 | threads: 8 | cores: 4 | free RAM: 30000 MiB
[12:00:00] Payout: arg1qx7qy4...q2npenc
[12:00:05] Chain synced at block 793
[12:00:05] Auto-tuning: testing [8, 7, 4] threads (~4 min, once per machine)
[12:01:05]     8 threads -> 118.4 H/s
[12:02:05]     7 threads -> 121.9 H/s
[12:03:05]     4 threads -> 97.2 H/s
[12:03:05] Best setting: 7 threads
[12:03:05] Mining with 7 threads. Report every 60s. Stop with Ctrl+C.
[12:04:05] Block 795 | 121.3 H/s | blocks found: 0
```

---

## Auto-tuning

Argon2id is memory-hard. More threads is **not** always faster: on hyper-threaded or shared CPUs, using every logical thread can saturate memory bandwidth and lower the total hashrate.

So instead of guessing, the launcher measures:

| Step | What happens |
|---|---|
| **Detect** | Usable CPUs (affinity + cgroup quota), physical cores, free memory |
| **Candidates** | All threads, all minus one, physical cores — each capped by free memory |
| **Benchmark** | Mines with each candidate for one minute and reads the real hashrate from the node over RPC |
| **Save** | Keeps the fastest in `argonmine/tune.json` |

Later runs on the same machine skip the benchmark and start mining immediately. Use `--retune` after a hardware change.

---

## Rewards

| | |
|---|---|
| **Per block** | 49.5 ARG (1% of the subsidy goes to the project treasury) |
| **Blocks per day** | ~144 network-wide |
| **Spendable after** | 100 blocks (~17 hours) |

**Expected time to a block:**

```
average wait = 10 minutes × network hashrate ÷ your hashrate
```

As a rough guide, a modern desktop core makes about 25 attempts per second. Finding a block is random: two in one hour and then nothing for days is normal. Live network figures are on the [explorer](https://explorer.argonmine.com).

---

## Security

- The miner only needs your **address**. Your 24 words never touch the machine.
- The node binary is downloaded from the official source and verified by checksum before it runs.
- The RPC interface listens on `127.0.0.1` only, with a random token per run.
- P2P listening is disabled; the node only connects outward.

---

## FAQ

<details>
<summary><b>Do I need a GPU?</b></summary>

No. Argon2id is memory-bound, so a GPU gives little advantage. CPU cores and memory bandwidth are what count.
</details>

<details>
<summary><b>How much memory does it use?</b></summary>

About 8 MiB per mining thread plus the node itself. The launcher caps the thread count to what free memory allows.
</details>

<details>
<summary><b>Where do my rewards show up?</b></summary>

In the Argonmine app under your 24 words. New rewards appear as <i>Maturing</i> and unlock after 100 blocks.
</details>

<details>
<summary><b>Can I mine on several machines?</b></summary>

Yes. Run the launcher on each machine with the same address. Every block any of them finds pays the same wallet.
</details>

<details>
<summary><b>Where are the files kept?</b></summary>

In <code>./argonmine/</code> next to where you run the script: the official release, the chain data and <code>tune.json</code>.
</details>

---

## Requirements

- Linux, x86-64 or ARM64
- Python 3.8+
- Internet access

## Links

- Website: [argonmine.com](https://argonmine.com)
- Wallet app: [app.argonmine.com](https://app.argonmine.com/?ref=arg1qx7qy47eetvlr86j88g6c2e9jgddrtm3h6dq4043zxwsscua5kj5q2npenc)
- Explorer: [explorer.argonmine.com](https://explorer.argonmine.com)
- Documentation: [argonmine.com/docs](https://argonmine.com/docs)

---

<div align="center">
<sub>Unofficial community tool. Not affiliated with the Argonmine project.</sub>
</div>
