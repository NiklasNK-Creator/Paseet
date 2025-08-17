import string
import time
import numpy as np
import pyopencl as cl
import sys
from colorama import init, Fore, Style

init(autoreset=True)

# =====================
# Einstellungen
# =====================
target_password = "hello1"
charset = string.ascii_letters + string.digits
charset_np = np.array([ord(c) for c in charset], dtype=np.uint8)
charset_size = np.int32(len(charset))
max_len = len(target_password)

# =====================
# Tool Name & Startup Interface
# =====================
tool_name = "P@SS-BRUT3"

ascii_banner = f"""
{Fore.CYAN}██████╗  █████╗ ███████╗███████╗-███████╗████████╗
██╔══██╗██╔══██╗██╔════╝██╔════╝-██╔════╝╚══██╔══╝
██████╔╝███████║███████╗█████╗──█████╗─────██║───
██╔═══╝ ██╔══██║╚════██║██╔══╝──██╔══╝─────██║───
██║     ██║  ██║███████║███████╗███████╗───██║───
╚═╝     ╚═╝  ╚══════╝╚══════╝╚══════╝───╚═╝───
"""

menu_options = f"""
{Fore.YELLOW}[1] Passwort brute-forcen
[2] Einstellungen anzeigen
[3] Beenden{Style.RESET_ALL}
"""

def startup_interface():
    print(ascii_banner)
    print(menu_options)
    choice = input(Fore.GREEN + "Option wählen: " + Style.RESET_ALL)
    if choice == "1":
        print(Fore.MAGENTA + "🔑 Starte Brute-Force...\n")
    elif choice == "2":
        print(f"{Fore.CYAN}Target Passwort: {target_password}")
        print(f"Charset: {charset}")
        print(f"Maximale Länge: {max_len}")
        input(Fore.YELLOW + "\nDrücke Enter, um fortzufahren..." + Style.RESET_ALL)
    elif choice == "3":
        print(Fore.RED + "👋 Beende Programm...")
        exit()
    else:
        print(Fore.RED + "⚠️ Ungültige Option")
        startup_interface()

startup_interface()

# =====================
# OpenCL Kernel
# =====================
kernel_code = """
__kernel void brute_force(
    __global const uchar *charset,
    const int charset_size,
    __global const uchar *target,
    const int target_len,
    __global uchar *found,
    __global int *found_flag,
    const ulong start_index
) {
    ulong gid = (ulong)get_global_id(0) + start_index;

    uchar guess[16];
    ulong tmp = gid;
    for (int i = target_len-1; i >= 0; i--) {
        guess[i] = charset[tmp % charset_size];
        tmp /= charset_size;
    }

    int match = 1;
    for (int j = 0; j < target_len; j++) {
        if (guess[j] != target[j]) {
            match = 0;
            break;
        }
    }

    if (match == 1) {
        for (int k = 0; k < target_len; k++) {
            found[k] = guess[k];
        }
        *found_flag = 1;
    }
}
"""

# =====================
# OpenCL Setup
# =====================
ctx = cl.create_some_context()
queue = cl.CommandQueue(ctx)
mf = cl.mem_flags
program = cl.Program(ctx, kernel_code).build()

target_np = np.frombuffer(target_password.encode("utf-8"), dtype=np.uint8)

found = np.zeros(max_len, dtype=np.uint8)
found_flag = np.array([0], dtype=np.int32)

found_buf = cl.Buffer(ctx, mf.WRITE_ONLY, found.nbytes)
flag_buf = cl.Buffer(ctx, mf.WRITE_ONLY, found_flag.nbytes)
charset_buf = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=charset_np)
target_buf = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=target_np)

# =====================
# Brute Force starten
# =====================
start_time = time.time()
tested = 0
chunk_size = 1_000_000
log_interval = 100_000_000
next_log = log_interval

total_combinations = len(charset) ** max_len

while True:
    current_chunk = min(chunk_size, total_combinations - tested)
    if current_chunk <= 0:
        break

    event = program.brute_force(
        queue, (current_chunk,), None,
        charset_buf, charset_size,
        target_buf, np.int32(max_len),
        found_buf, flag_buf,
        np.uint64(tested)
    )
    event.wait()

    cl.enqueue_copy(queue, found, found_buf).wait()
    cl.enqueue_copy(queue, found_flag, flag_buf).wait()

    tested += current_chunk
    elapsed = time.time() - start_time
    speed = tested / elapsed

    # Dynamischer Fortschrittsbalken
    percent = tested / total_combinations * 100
    bar_len = 40
    filled_len = int(bar_len * percent / 100)
    bar = '█' * filled_len + '-' * (bar_len - filled_len)

    print(f"\r{Fore.CYAN}[{bar}] {percent:.2f}% | Versuche: {tested:,} | {speed:,.0f}/s | Zeit: {elapsed:.2f}s", end='')

    if found_flag[0] == 1:
        print(f"\n\n{Fore.GREEN}✅ Passwort gefunden: {found.tobytes().decode('utf-8')} in {elapsed:.2f} Sekunden nach {tested:,} Versuchen")
        break
