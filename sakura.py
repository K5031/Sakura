#!/usr/bin/env python3

import argparse
import os
import random
import shutil
import signal
import sys
import time


PETAL_CHARS = ["*", "•", "o", ".", "❀", "✿"]


def parse_rgb(value, label):
    try:
        parts = [int(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"{label} must be in R,G,B format"
        ) from exc

    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"{label} must be in R,G,B format"
        )

    if any(part < 0 or part > 255 for part in parts):
        raise argparse.ArgumentTypeError(
            f"{label} values must be between 0 and 255"
        )

    return parts


def build_parser():
    parser = argparse.ArgumentParser(
        description="A terminal cherry blossom animation.",
        add_help=True,
    )

    parser.add_argument(
        "-n",
        "--num-leaves",
        type=int,
        default=30,
        help="Number of falling leaves (default: 30)",
    )

    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=0.08,
        help="Animation delay in seconds (default: 0.08)",
    )

    parser.add_argument(
        "-p",
        "--petal-color",
        type=lambda v: parse_rgb(v, "petal color"),
        default=[255, 105, 180],
        metavar="R,G,B",
        help="Petal RGB color (default: 255,105,180 pink)",
    )

    parser.add_argument(
        "-b",
        "--bg-color",
        type=lambda v: parse_rgb(v, "background color"),
        default=None,
        metavar="R,G,B",
        help="Background RGB color (optional)",
    )

    parser.add_argument(
        "-D",
        "--drift",
        type=int,
        default=1,
        help="Fixed drift per frame (default: 1)",
    )

    parser.add_argument(
        "-w",
        "--wind-factor",
        type=int,
        default=1,
        help="Wind random wobble factor (default: 1)",
    )

    return parser


def ansi_rgb(code_type, rgb):
    return f"\033[{code_type};2;{rgb[0]};{rgb[1]};{rgb[2]}m"


class SakuraAnimator:
    def __init__(
        self,
        num_leaves,
        delay,
        petal_color,
        bg_color,
        fixed_drift,
        wind_factor,
    ):
        self.num_leaves = max(1, num_leaves)
        self.delay = max(0.0, delay)

        self.petal_color = petal_color
        self.bg_color = (
            bg_color if bg_color is not None else [55, 58, 59]
        )

        self.fixed_drift = fixed_drift
        self.wind_factor = max(0, wind_factor)

        self.cols, self.rows = shutil.get_terminal_size(
            fallback=(80, 24)
        )

        self.max_off_screen_y = 20
        self.max_off_screen_x = (
            self.rows + self.max_off_screen_y
        )

        self.leaf_x = []
        self.leaf_y = []
        self.prev_x = []
        self.prev_y = []

        self.leaf_char = []
        self.char_timer = []
        self.char_interval = []

        self.reset_positions()

    def reset_positions(self):
        self.leaf_x = []
        self.leaf_y = []
        self.prev_x = []
        self.prev_y = []

        self.leaf_char = []
        self.char_timer = []
        self.char_interval = []

        for _ in range(self.num_leaves):
            x = random.randint(
                -self.max_off_screen_x,
                self.cols + self.max_off_screen_x - 1,
            )

            y = random.randint(
                -self.max_off_screen_y,
                self.rows + self.max_off_screen_y - 1,
            )

            self.leaf_x.append(x)
            self.leaf_y.append(y)

            self.prev_x.append(x)
            self.prev_y.append(y)

            self.leaf_char.append(
                random.choice(PETAL_CHARS)
            )

            self.char_timer.append(0)

            self.char_interval.append(
                random.randint(3, 8)
            )

    def cleanup(self):
        sys.stdout.write(
            "\033[?25h"
            "\033[0m"
            "\033[2J"
            "\033[H"
        )

        sys.stdout.flush()
        raise SystemExit(0)

    def draw_background(self):
        bg = ansi_rgb("48", self.bg_color)

        sys.stdout.write("\033[H")

        for row in range(self.rows):
            sys.stdout.write(
                f"\033[{row + 1};1H"
                f"{bg}"
                f"{' ' * self.cols}"
            )

        sys.stdout.flush()

    def run(self):
        self.draw_background()

        petal_code = ansi_rgb(
            "38",
            self.petal_color,
        )

        bg_code = ansi_rgb(
            "48",
            self.bg_color,
        )

        while True:
            sys.stdout.write("\033[H")

            for i in range(self.num_leaves):
                prev_y = self.prev_y[i]
                prev_x = self.prev_x[i]

                if (
                    1 <= prev_y <= self.rows
                    and 1 <= prev_x <= self.cols
                ):
                    sys.stdout.write(
                        f"\033[{prev_y};{prev_x}H"
                        f"{bg_code} "
                    )

                self.prev_x[i] = 0
                self.prev_y[i] = 0

                self.leaf_y[i] += 1

                wobble = random.randint(
                    -self.wind_factor,
                    self.wind_factor,
                )

                drift = (
                    self.fixed_drift
                    + wobble
                )

                self.leaf_x[i] += drift

                # Change petal symbol only every few frames.
                self.char_timer[i] += 1

                if self.char_timer[i] >= self.char_interval[i]:
                    self.leaf_char[i] = random.choice(
                        PETAL_CHARS
                    )

                    self.char_timer[i] = 0

                    self.char_interval[i] = random.randint(
                        3,
                        8,
                    )

                if (
                    1 <= self.leaf_y[i] <= self.rows
                    and 1 <= self.leaf_x[i] <= self.cols
                ):
                    petal = self.leaf_char[i]

                    sys.stdout.write(
                        f"\033[{self.leaf_y[i]};"
                        f"{self.leaf_x[i]}H"
                        f"{petal_code}"
                        f"{petal}"
                        f"{bg_code}"
                    )

                    if self.leaf_y[i] < self.rows:
                        self.prev_x[i] = (
                            self.leaf_x[i]
                        )

                        self.prev_y[i] = (
                            self.leaf_y[i]
                        )

                if self.leaf_y[i] > self.rows:
                    self.leaf_y[i] = random.randint(
                        -self.max_off_screen_y,
                        -1,
                    )

                    self.leaf_x[i] = random.randint(
                        -self.max_off_screen_x,
                        self.cols
                        + self.max_off_screen_x
                        - 1,
                    )

                    self.prev_x[i] = 0
                    self.prev_y[i] = 0

                    self.leaf_char[i] = random.choice(
                        PETAL_CHARS
                    )

                    self.char_timer[i] = 0
                    self.char_interval[i] = random.randint(
                        3,
                        8,
                    )

                elif self.leaf_x[i] > self.cols:
                    self.leaf_y[i] = random.randint(
                        -self.max_off_screen_y,
                        -1,
                    )

                    self.leaf_x[i] = random.randint(
                        -self.max_off_screen_x,
                        self.cols
                        + self.max_off_screen_x
                        - 1,
                    )

                    self.prev_x[i] = 0
                    self.prev_y[i] = 0

                    self.leaf_char[i] = random.choice(
                        PETAL_CHARS
                    )

                    self.char_timer[i] = 0
                    self.char_interval[i] = random.randint(
                        3,
                        8,
                    )

            sys.stdout.flush()
            time.sleep(self.delay)


def main():
    parser = build_parser()
    args = parser.parse_args()

    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    animator = SakuraAnimator(
        num_leaves=args.num_leaves,
        delay=args.delay,
        petal_color=args.petal_color,
        bg_color=args.bg_color,
        fixed_drift=args.drift,
        wind_factor=args.wind_factor,
    )

    def handle_signal(signum, frame):
        animator.cleanup()

    signal.signal(
        signal.SIGINT,
        handle_signal,
    )

    signal.signal(
        signal.SIGTERM,
        handle_signal,
    )

    try:
        animator.run()

    except SystemExit:
        raise

    except KeyboardInterrupt:
        animator.cleanup()


if __name__ == "__main__":
    main()