"""Heavy plugin used for testing runner limits.

Supports `--sleep N` to sleep N seconds and `--alloc-mb N` to allocate N megabytes.
"""
import argparse
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sleep", type=float, default=0)
    parser.add_argument("--alloc-mb", type=int, default=0)
    args = parser.parse_args()

    if args.alloc_mb > 0:
        # allocate a bytearray of the requested size
        print(f"Allocating {args.alloc_mb} MB")
        a = bytearray(args.alloc_mb * 1024 * 1024)
        # touch memory
        for i in range(0, len(a), 1024 * 1024):
            a[i] = 1
        print("Allocation complete")

    if args.sleep > 0:
        time.sleep(args.sleep)

    print("heavy_plugin done")


if __name__ == "__main__":
    main()
