#!/usr/bin/env python3
"""
47_di — FASTEST Proxy Checker (Fast + Stable)
Save as: proxy_checker_fastest_47di.py

Requirements:
    pip install aiohttp colorama pyfiglet
( pyfiglet optional; script runs without it )
"""
from __future__ import annotations
import asyncio
import aiohttp
import socket
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# optional niceties
try:
    import pyfiglet
    PYFIGLET = True
except Exception:
    PYFIGLET = False

try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
except Exception:
    class _C:
        RESET=""; RED=""; GREEN=""; YELLOW=""; CYAN=""; MAGENTA=""; WHITE=""
    Fore = _C(); Style = _C()

# Silence noisy loggers
import logging
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
logging.getLogger("aiohttp").setLevel(logging.CRITICAL)

# ---- Config (tweak for your environment) ----
TEST_HTTP_URL = "http://httpbin.org/ip"
TEST_HTTPS_URL = "https://httpbin.org/ip"
SOCKS_TEST_HOST = "httpbin.org"
SOCKS_TEST_PORT = 80
HTTP_TIMEOUT = 7.0
SOCKET_TIMEOUT = 4.0
RETRIES = 1
BACKOFF = 0.25
MAX_CONCURRENCY = 1000
RECOMMENDED = 200
BATCH_SIZE = 600           # keep memory & scheduling sane
STATS_INTERVAL = 1.0       # seconds
AUTOSAVE_INTERVAL = 2.0    # seconds
# ----------------------------------------------

def clear_screen():
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        pass

def print_header():
    clear_screen()
    title = "47_di - FASTEST TOOL"
    if PYFIGLET:
        try:
            art = pyfiglet.figlet_format("47_di", font="standard")
            print(Fore.CYAN + art + Style.RESET_ALL)
        except Exception:
            print(Fore.CYAN + "=== 47_di Proxy Checker ===" + Style.RESET_ALL)
    else:
        print(Fore.CYAN + "=== 47_di Proxy Checker ===" + Style.RESET_ALL)
    print(Fore.MAGENTA + "Made with " + Fore.RED + "❤️ " + Fore.MAGENTA + "by 47_di — Fastest Tool" + Style.RESET_ALL)
    print(Fore.YELLOW + "Support: DM on Discord -> 47_di" + Style.RESET_ALL)
    print(Fore.CYAN + "─" * 72 + Style.RESET_ALL)

def ask_threads() -> int:
    while True:
        try:
            s = input(Fore.CYAN + f"How many concurrent workers (1-{MAX_CONCURRENCY}, recommended {RECOMMENDED}): " + Style.RESET_ALL).strip()
            if s == "":
                return RECOMMENDED
            n = int(s)
            if 1 <= n <= MAX_CONCURRENCY:
                return n
            print(Fore.RED + f"Enter a number between 1 and {MAX_CONCURRENCY}." + Style.RESET_ALL)
        except Exception:
            print(Fore.RED + "Invalid input — enter an integer." + Style.RESET_ALL)

def choose_proxy_file() -> Optional[str]:
    # Try file dialog first (Tkinter) for convenience
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
        p = filedialog.askopenfilename(title="Select proxy list (ip:port per line)", filetypes=[("Text files","*.txt"),("All files","*.*")])
        try: root.destroy()
        except Exception: pass
        if p:
            return p
    except Exception:
        pass
    # fallback to typed path
    p = input(Fore.YELLOW + "Enter path to proxy file (ip:port per line): " + Style.RESET_ALL).strip()
    return p if p else None

def load_and_dedupe(path: str) -> List[str]:
    proxies: List[str] = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for ln in f:
                s = ln.strip()
                if not s or s.startswith("#"):
                    continue
                low = s.lower()
                for pref in ("http://","https://","socks4://","socks5://"):
                    if low.startswith(pref):
                        s = s.split("://",1)[1]
                        break
                proxies.append(s)
    except Exception:
        return []
    seen = set()
    uniq: List[str] = []
    for p in proxies:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq

# ---- HTTP(S) test using aiohttp (async) ----
async def aiohttp_test(session: aiohttp.ClientSession, proxy_addr: str, use_https: bool) -> Tuple[bool, Optional[float]]:
    url = TEST_HTTPS_URL if use_https else TEST_HTTP_URL
    proxy_url = f"http://{proxy_addr}"  # many HTTP proxies accept CONNECT for https
    attempt = 0
    while attempt <= RETRIES:
        attempt += 1
        try:
            start = time.perf_counter()
            async with session.get(url, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)) as resp:
                elapsed = time.perf_counter() - start
                if resp.status == 200:
                    return True, elapsed
                return False, None
        except Exception:
            if attempt <= RETRIES:
                await asyncio.sleep(BACKOFF * (2 ** (attempt-1)))
            else:
                return False, None
    return False, None

# ---- SOCKS checks (sync) executed in threads ----
def socks4_check(proxy_host: str, proxy_port: int, dest_host: str, dest_port: int, timeout: float) -> bool:
    try:
        dst_ip = socket.gethostbyname(dest_host)
    except Exception:
        return False
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((proxy_host, proxy_port))
        port_bytes = dest_port.to_bytes(2, 'big')
        ip_bytes = bytes(int(x) for x in dst_ip.split("."))
        req = b"\x04\x01" + port_bytes + ip_bytes + b"\x00"
        s.sendall(req)
        resp = s.recv(8)
        if len(resp) >= 2 and resp[1] == 0x5A:
            s.close()
            return True
    except Exception:
        pass
    try:
        if s: s.close()
    except Exception:
        pass
    return False

def socks5_check(proxy_host: str, proxy_port: int, dest_host: str, dest_port: int, timeout: float) -> bool:
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((proxy_host, proxy_port))
        s.sendall(b"\x05\x01\x00")
        h = s.recv(2)
        if len(h) < 2 or h[1] == 0xFF:
            s.close(); return False
        host_bytes = dest_host.encode()
        req = b"\x05\x01\x00\x03" + bytes([len(host_bytes)]) + host_bytes + dest_port.to_bytes(2, 'big')
        s.sendall(req)
        resp = s.recv(10)
        if len(resp) >= 2 and resp[1] == 0x00:
            s.close(); return True
    except Exception:
        pass
    try:
        if s: s.close()
    except Exception:
        pass
    return False

# ---- probe single proxy for all protocols (safe, catches exceptions) ----
async def probe_proxy(proxy: str, session: aiohttp.ClientSession, sem: asyncio.Semaphore,
                      stats: Dict, results: Dict, lock: asyncio.Lock):
    async with sem:
        if not proxy:
            return
        parts = proxy.split(":")
        if len(parts) < 2:
            return
        host = parts[0]; port_s = parts[1]
        try:
            port = int(port_s)
        except Exception:
            return

        found_any = False

        # HTTP
        try:
            ok, _ = await aiohttp_test(session, f"{host}:{port}", use_https=False)
            if ok:
                async with lock:
                    if proxy not in results["http"]:
                        results["http"].append(proxy)
                        stats["http_ok"] += 1
                found_any = True
        except Exception:
            pass

        # HTTPS
        try:
            ok, _ = await aiohttp_test(session, f"{host}:{port}", use_https=True)
            if ok:
                async with lock:
                    if proxy not in results["https"]:
                        results["https"].append(proxy)
                        stats["https_ok"] += 1
                found_any = True
        except Exception:
            pass

        # SOCKS4 (thread)
        try:
            ok4 = await asyncio.to_thread(socks4_check, host, port, SOCKS_TEST_HOST, SOCKS_TEST_PORT, SOCKET_TIMEOUT)
            if ok4:
                async with lock:
                    if proxy not in results["socks4"]:
                        results["socks4"].append(proxy)
                        stats["socks4_ok"] += 1
                found_any = True
        except Exception:
            pass

        # SOCKS5
        try:
            ok5 = await asyncio.to_thread(socks5_check, host, port, SOCKS_TEST_HOST, SOCKS_TEST_PORT, SOCKET_TIMEOUT)
            if ok5:
                async with lock:
                    if proxy not in results["socks5"]:
                        results["socks5"].append(proxy)
                        stats["socks5_ok"] += 1
                found_any = True
        except Exception:
            pass

        async with lock:
            stats["done"] += 1
            stats["last"] = proxy
            if found_any:
                stats["found"] += 1
            else:
                stats["failed"] += 1

# ---- autosave partial results periodically ----
async def autosave_worker(results: Dict, out_dir: Path, lock: asyncio.Lock):
    while True:
        try:
            await asyncio.sleep(AUTOSAVE_INTERVAL)
            async with lock:
                for proto in ("http","https","socks4","socks5"):
                    p = out_dir / f"valid_{proto}.txt"
                    tmp = p.with_suffix(".tmp")
                    try:
                        with open(tmp, "w", encoding="utf-8") as f:
                            for item in results.get(proto, []):
                                f.write(item + "\n")
                        tmp.replace(p)
                    except Exception:
                        pass
                # all_valid
                try:
                    allp = out_dir / "all_valid.txt"
                    tmp = allp.with_suffix(".tmp")
                    all_list = []
                    for proto in ("http","https","socks4","socks5"):
                        all_list.extend(results.get(proto, []))
                    with open(tmp, "w", encoding="utf-8") as f:
                        f.write("\n".join(all_list))
                    tmp.replace(allp)
                except Exception:
                    pass
        except asyncio.CancelledError:
            break
        except Exception:
            pass

# ---- live stats printer (single-line update) ----
async def stats_printer(stats: Dict, start_time: float):
    prev_done = 0
    prev_time = start_time
    total = stats.get("total", 0)
    while True:
        try:
            await asyncio.sleep(STATS_INTERVAL)
            now = time.time()
            done = stats.get("done", 0)
            delta_done = done - prev_done
            delta_t = now - prev_time if now > prev_time else 1.0
            speed = delta_done / (delta_t if delta_t > 0 else 1.0)
            prev_done = done; prev_time = now
            ok = stats.get("found", 0)
            failed = stats.get("failed", 0)
            http_ok = stats.get("http_ok", 0); https_ok = stats.get("https_ok", 0)
            s4_ok = stats.get("socks4_ok", 0); s5_ok = stats.get("socks5_ok", 0)
            last = stats.get("last", "-")
            pct = (done * 100 / total) if total else 100.0
            eta = (total - done) / speed if speed > 0 else float('inf')
            eta_str = "--:--:--" if eta == float('inf') else time.strftime("%H:%M:%S", time.gmtime(eta))
            sys.stdout.write("\r" + Fore.CYAN + f"[{done}/{total}] {pct:5.2f}% " + Style.RESET_ALL)
            sys.stdout.write(Fore.GREEN + f"OK:{ok} " + Style.RESET_ALL)
            sys.stdout.write(Fore.RED + f"Fail:{failed} " + Style.RESET_ALL)
            sys.stdout.write(Fore.WHITE + f"(H:{http_ok} HS:{https_ok} S4:{s4_ok} S5:{s5_ok}) " + Style.RESET_ALL)
            sys.stdout.write(Fore.YELLOW + f"Speed:{speed:.1f} p/s " + Style.RESET_ALL)
            sys.stdout.write(Fore.MAGENTA + f"ETA:{eta_str} " + Style.RESET_ALL)
            sys.stdout.write(Fore.WHITE + f"Last:{last[:40]:40}" + Style.RESET_ALL)
            sys.stdout.flush()
        except asyncio.CancelledError:
            break
        except Exception:
            pass

# ---- scanning runner ----
async def run_scan(proxies: List[str], concurrency: int, out_dir: Path):
    total = len(proxies)
    stats = {"done":0, "total": total, "found":0, "failed":0, "http_ok":0, "https_ok":0, "socks4_ok":0, "socks5_ok":0, "last":""}
    results = {"http": [], "https": [], "socks4": [], "socks5": []}
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(concurrency)

    connector = aiohttp.TCPConnector(limit_per_host=max(10, min(concurrency,200)), limit=max(50, min(concurrency*2,1000)), ssl=False)

    autosave_task = None
    stats_task = None
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            autosave_task = asyncio.create_task(autosave_worker(results, out_dir, lock))
            stats_task = asyncio.create_task(stats_printer(stats, time.time()))
            for i in range(0, total, BATCH_SIZE):
                batch = proxies[i:i+BATCH_SIZE]
                # create tasks that catch exceptions internally (probe_proxy catches)
                tasks = [asyncio.create_task(probe_proxy(p, session, sem, stats, results, lock)) for p in batch]
                # await and swallow exceptions (probe_proxy should not raise)
                await asyncio.gather(*tasks, return_exceptions=True)
                # small yield to event loop
                await asyncio.sleep(0)
            # final wait for outstanding stats update
            await asyncio.sleep(0.05)
            if stats_task:
                stats_task.cancel()
                try:
                    await stats_task
                except Exception:
                    pass
    finally:
        if autosave_task:
            autosave_task.cancel()
            try:
                await autosave_task
            except Exception:
                pass

    # final write
    try:
        all_list = []
        for proto in ("http","https","socks4","socks5"):
            p = out_dir / f"valid_{proto}.txt"
            with open(p, "w", encoding="utf-8") as f:
                for item in results.get(proto, []):
                    f.write(item + "\n")
            all_list.extend(results.get(proto, []))
        allp = out_dir / "all_valid.txt"
        with open(allp, "w", encoding="utf-8") as f:
            f.write("\n".join(all_list))
    except Exception:
        pass

    return results, stats

# ---- helper to save summary stats ----
def save_summary(out_dir: Path, stats: Dict, start_time: float, end_time: float, total_input: int, duplicates_removed: int):
    try:
        p = out_dir / "stats.txt"
        with open(p, "w", encoding="utf-8") as f:
            f.write("47_di - FASTEST Proxy Checker\n")
            f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total input lines: {total_input}\n")
            f.write(f"Duplicates removed: {duplicates_removed}\n")
            f.write(f"Checked: {stats.get('done',0)}\n")
            f.write(f"Found valid: {stats.get('found',0)}\n")
            f.write(f"HTTP: {stats.get('http_ok',0)}\n")
            f.write(f"HTTPS: {stats.get('https_ok',0)}\n")
            f.write(f"SOCKS4: {stats.get('socks4_ok',0)}\n")
            f.write(f"SOCKS5: {stats.get('socks5_ok',0)}\n")
            dur = end_time - start_time
            f.write(f"Duration: {dur:.2f}s\n")
            avg = stats.get('done',0)/dur if dur>0 else 0.0
            f.write(f"Average speed p/s: {avg:.2f}\n")
    except Exception:
        pass

# ---- main ----
def main():
    print_header()
    concurrency = ask_threads()
    file_path = choose_proxy_file()
    if not file_path or not os.path.isfile(file_path):
        print(Fore.RED + "No file selected or not found. Exiting." + Style.RESET_ALL)
        return

    print(Fore.YELLOW + "\nLoading proxy list and removing duplicates..." + Style.RESET_ALL)
    proxies = load_and_dedupe(file_path)
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            total_lines = sum(1 for _ in f)
    except Exception:
        total_lines = len(proxies)
    duplicates_removed = total_lines - len(proxies)
    print(Fore.GREEN + f"Loaded {len(proxies)} unique proxies (duplicates removed: {duplicates_removed})" + Style.RESET_ALL)

    out_dir = Path(file_path).resolve().parent / "results_47di"
    out_dir.mkdir(parents=True, exist_ok=True)

    start = time.time()
    try:
        results, stats = asyncio.run(run_scan(proxies, concurrency, out_dir))
    except KeyboardInterrupt:
        print("\n" + Fore.RED + "Interrupted by user." + Style.RESET_ALL)
        return
    end = time.time()
    # final summary
    print()  # newline after stats line
    print(Fore.MAGENTA + "────────────────────────────" + Style.RESET_ALL)
    print(Fore.GREEN + "✅ Scan complete!" + Style.RESET_ALL)
    print(Fore.CYAN + f"Total checked: {stats.get('done',0)}   Time: {end-start:.2f}s   Avg speed: { (stats.get('done',0)/(end-start)) if end>start else 0:.1f} p/s" + Style.RESET_ALL)
    print(Fore.GREEN + f"HTTP : {len(results.get('http',[]))}" + Style.RESET_ALL)
    print(Fore.GREEN + f"HTTPS: {len(results.get('https',[]))}" + Style.RESET_ALL)
    print(Fore.GREEN + f"SOCKS4: {len(results.get('socks4',[]))}" + Style.RESET_ALL)
    print(Fore.GREEN + f"SOCKS5: {len(results.get('socks5',[]))}" + Style.RESET_ALL)
    print(Fore.YELLOW + f"Files saved in: {out_dir}" + Style.RESET_ALL)
    save_summary(out_dir, stats, start, end, total_lines, duplicates_removed)
    print(Fore.MAGENTA + "Support: DM on Discord -> 47_di" + Style.RESET_ALL)
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
