# argon-miner

One-command launcher for the official [Argonmine](https://argonmine.com) (ARG) node miner.
It downloads the official `argonmined` release, verifies it, picks the fastest thread count for the machine it runs on, and keeps mining.

## Features

- **No hard-coded address.** The payout address is given at run time.
- **Auto-tuning.** Detects usable CPUs (including container limits) and free memory, benchmarks the realistic thread counts once, and saves the best one for that machine.
- **Verified binary.** Uses the official `argonmined` 1.1.0 release and checks it against the published `SHA256SUMS`. A mismatch stops the run.
- **Self-healing.** Restarts the miner automatically if it exits.
- **Clean output.** One status line per minute: height, hashrate, blocks found.
- **Address only.** Your 24 words never touch the machine.

## Requirements

- Linux, x86-64 or ARM64
- Python 3.8+ (standard library only)
- Internet access

## Usage

```bash
python3 argon_mine.py arg1q...your_address
```

Run without an argument to be asked for the address, or set it in the environment:

```bash
export ARG_ADDRESS=arg1q...your_address
python3 argon_mine.py
```

### Options

| Option | Description |
|---|---|
| `--threads N` | Use a fixed thread count and skip auto-tuning |
| `--retune` | Ignore the saved tuning and measure again |
| `--tag TEXT` | Optional public label written into blocks you find |
| `--dry-run` | Download, verify and print the plan without mining |

Stop with `Ctrl+C`.

## How the tuning works

Argonmine uses Argon2id with 8 MiB of memory per attempt, so speed depends on cores **and** memory bandwidth. More threads is not always faster: on shared or hyper-threaded CPUs, using every logical thread can lower the total hashrate.

On first run the launcher:

1. Syncs the chain.
2. Builds a short candidate list: all usable threads, all minus one, and physical cores, each capped by free memory.
3. Mines with each candidate for one minute and reads the real hashrate from the node.
4. Keeps the fastest and saves it in `argonmine/tune.json`.

Later runs on the same machine start mining immediately with the saved value.

## Output

```
[12:00:00] CPU: AMD EPYC 7B13 | threads: 4 | cores: 2 | free RAM: 30000 MiB
[12:00:05] Chain synced at block 793
[12:00:05] Auto-tuning: testing [4, 3, 2] threads (~4 min, once per machine)
[12:01:05]     4 threads -> 61.2 H/s
...
[12:04:05] Mining with 4 threads. Report every 60s. Stop: Ctrl+C or interrupt the cell.
[12:05:05] Block 795 | 60.8 H/s | blocks found: 0
```

## Files

Everything is kept in `./argonmine/` next to where you run it:

| Path | Content |
|---|---|
| `argonmine-1.1.0-linux-*/` | Official release |
| `data/` | Chain data |
| `tune.json` | Saved thread setting |

## Expected rewards

Your share of blocks equals your share of the network hashrate. A block pays 49.5 ARG and arrives about every 10 minutes. Rewards unlock after 100 blocks (about 17 hours). See the [mining docs](https://argonmine.com/docs/mining).

## Disclaimer

Unofficial tool. Check the terms of the machine you run it on before mining.
