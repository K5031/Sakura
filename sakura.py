#!/usr/bin/env python3

import argparse
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time


PETAL_CHARS = ["*", "•", "o", ".", "❀", "✿"]

DEFAULT_PETAL_COLOR = [255, 105, 180]

PETAL_COLORS = [
    [255, 172, 212],  # #FFACD4
    [255, 141, 196],  # #FF8DC4
    [246, 123, 182],  # #F67BB6
    [241,  99, 168],  # #F163A8
    [237,  77, 154],  # #ED4D9A
]

TREE_SPAWN_PROBABILITY = 0.85

REFERENCE_COLS = 80
REFERENCE_ROWS = 24
REFERENCE_LEAVES = 1

ANSI_SGR_RE = re.compile(r"\x1b\[[0-9;]*m")
TRUECOLOR_FG_RE = re.compile(
    r"\x1b\[38;2;(\d+);(\d+);(\d+)m"
)


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


def parse_tree_scale(value):
    try:
        scale = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "tree scale must be a number between 0 and 1"
        ) from exc

    if not 0 < scale <= 1:
        raise argparse.ArgumentTypeError(
            "tree scale must be greater than 0 and at most 1"
        )

    return scale


def lighten_ansi_color(style, amount=60):
    match = TRUECOLOR_FG_RE.search(style)

    if not match:
        return style

    r, g, b = map(int, match.groups())

    return (
        f"\033[38;2;"
        f"{min(255, r + amount)};"
        f"{min(255, g + amount)};"
        f"{min(255, b + amount)}m"
    )


def automatic_leaf_count(cols, rows):
    reference_area = REFERENCE_COLS * REFERENCE_ROWS
    area = max(1, cols * rows)

    return max(
        1,
        round(
            REFERENCE_LEAVES
            * area
            / reference_area
        ),
    )


def build_parser():
    parser = argparse.ArgumentParser(
        description="A terminal cherry blossom animation."
    )

    parser.add_argument(
        "-n", "--num-leaves",
        type=int,
        default=None,
        help="Fixed number of petals; default scales with terminal area",
    )

    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=0.08,
        help="Animation delay in seconds (default: 0.08)",
    )

    parser.add_argument(
        "-p", "--petal-color",
        type=lambda v: parse_rgb(v, "petal color"),
        default=None,
        metavar="R,G,B",
        help="Override random pink shades with one RGB color",
    )

    parser.add_argument(
        "-b", "--bg-color",
        type=lambda v: parse_rgb(v, "background color"),
        default=None,
        metavar="R,G,B",
        help="Background RGB color (optional)",
    )

    parser.add_argument(
        "-D", "--drift",
        type=int,
        default=1,
        help="Fixed drift per frame (default: 1)",
    )

    parser.add_argument(
        "-w", "--wind-factor",
        type=int,
        default=1,
        help="Wind random wobble factor (default: 1)",
    )

    parser.add_argument(
        "-t", "--tree",
        action="store_true",
        help="Display sakura.png as ASCII art on the left",
    )

    parser.add_argument(
        "--tree-scale",
        type=parse_tree_scale,
        default=0.6,
        metavar="SCALE",
        help="Tree height as a fraction of terminal height (default: 0.6)",
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
        show_tree,
        tree_scale,
    ):
        self.cols, self.rows = shutil.get_terminal_size(
            fallback=(80, 24)
        )

        if num_leaves is None:
            self.num_leaves = automatic_leaf_count(
                self.cols,
                self.rows,
            )
        else:
            self.num_leaves = max(1, num_leaves)

        self.delay = max(0.0, delay)

        self.use_pink_palette = petal_color is None
        self.petal_color = (
            petal_color
            if petal_color is not None
            else DEFAULT_PETAL_COLOR
        )

        self.bg_color = (
            bg_color
            if bg_color is not None
            else [55, 58, 59]
        )

        self.fixed_drift = fixed_drift
        self.wind_factor = max(0, wind_factor)

        self.max_off_screen_y = 20
        self.max_off_screen_x = self.rows + self.max_off_screen_y

        self.show_tree = show_tree
        self.tree_scale = tree_scale

        self.tree_cells = {}
        self.canopy_spawn_points = []

        self.tree_height = 0
        self.tree_width = 0
        self.tree_top = 1
        self.ground_row = self.rows

        self.ground_pile = {}

        self.leaf_x = []
        self.leaf_y = []
        self.prev_x = []
        self.prev_y = []

        self.leaf_char = []
        self.leaf_color = []
        self.char_timer = []
        self.char_interval = []
        self.leaf_rest_row = []

        if self.show_tree:
            self.load_tree()

        self.reset_positions()

    def random_petal_color(self):
        if self.use_pink_palette:
            return random.choice(PETAL_COLORS).copy()

        return self.petal_color.copy()

    # --------------------------------------------------------
    # Tree
    # --------------------------------------------------------

    def load_tree(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(script_dir, "sakura.png")

        if not os.path.isfile(image_path):
            raise SystemExit(
                f"Tree image not found: {image_path}"
            )

        if shutil.which("ascii-image-converter") is None:
            raise SystemExit(
                "ascii-image-converter was not found in PATH.\n"
                "Install it before using --tree."
            )

        self.tree_height = max(
            1,
            int(self.rows * self.tree_scale),
        )

        self.tree_width = min(
            self.cols,
            round(self.tree_height * 2.8),
        )

        self.tree_top = 1

        self.ground_row = min(
            self.rows,
            self.tree_height + 1,
        )

        try:
            result = subprocess.run(
                [
                    "ascii-image-converter",
                    image_path,
                    "-C",
                    "-d",
                    f"{self.tree_width},{self.tree_height}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )

        except subprocess.CalledProcessError as exc:
            error = exc.stderr.strip() or "unknown converter error"

            raise SystemExit(
                f"ascii-image-converter failed: {error}"
            ) from exc

        self.parse_tree_output(
            result.stdout.splitlines()
        )

        self.remove_small_tree_components()
        self.build_canopy_spawn_points()

    def parse_tree_output(self, lines):
        self.tree_cells = {}

        for local_row, line in enumerate(lines):
            actual_row = self.tree_top + local_row

            if actual_row > self.rows:
                break

            col = 1
            pos = 0
            active_style = ""

            while pos < len(line):
                match = ANSI_SGR_RE.match(line, pos)

                if match:
                    sequence = match.group(0)

                    active_style = (
                        ""
                        if sequence in ("\033[0m", "\033[m")
                        else sequence
                    )

                    pos = match.end()
                    continue

                char = line[pos]
                pos += 1

                if col > self.cols:
                    break

                if char != " ":
                    style = active_style

                    if char in ".:;":
                        style = lighten_ansi_color(
                            style,
                            amount=60,
                        )

                    self.tree_cells[
                        (actual_row, col)
                    ] = style + char

                col += 1

    def remove_small_tree_components(
        self,
        minimum_size=18,
    ):
        positions = set(self.tree_cells)

        if not positions:
            return

        unvisited = set(positions)
        components = []

        while unvisited:
            start = unvisited.pop()
            component = {start}
            stack = [start]

            while stack:
                row, col = stack.pop()

                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue

                        neighbor = (
                            row + dy,
                            col + dx,
                        )

                        if neighbor in unvisited:
                            unvisited.remove(neighbor)
                            component.add(neighbor)
                            stack.append(neighbor)

            components.append(component)

        largest = max(
            components,
            key=len,
        )

        keep = set(largest)

        for component in components:
            if (
                component is not largest
                and len(component) >= minimum_size
            ):
                keep.update(component)

        self.tree_cells = {
            position: value
            for position, value in self.tree_cells.items()
            if position in keep
        }

    def build_canopy_spawn_points(self):
        self.canopy_spawn_points = []

        if not self.tree_cells:
            return

        direction = 1 if self.fixed_drift >= 0 else -1
        positions = set(self.tree_cells)

        for row, col in positions:
            outside_col = col + direction

            if not 1 <= outside_col <= self.cols:
                continue

            if (row, outside_col) not in positions:
                self.canopy_spawn_points.append(
                    (row, outside_col)
                )

    def tree_at(self, row, col):
        return self.tree_cells.get(
            (row, col)
        )

    def draw_tree(self):
        if not self.show_tree:
            return

        bg_code = ansi_rgb(
            "48",
            self.bg_color,
        )

        for (row, col), char in self.tree_cells.items():
            sys.stdout.write(
                f"\033[{row};{col}H"
                f"{char}"
                f"{bg_code}"
            )

    # --------------------------------------------------------
    # Ground
    # --------------------------------------------------------

    def draw_ground(self):
        if not self.show_tree:
            return

        bg_code = ansi_rgb(
            "48",
            self.bg_color,
        )

        ground_color = ansi_rgb(
            "38",
            [125, 108, 92],
        )

        sys.stdout.write(
            f"\033[{self.ground_row};1H"
            f"{ground_color}"
            f"{'_' * self.cols}"
            f"{bg_code}"
        )

    def choose_rest_row(self):
        return random.randint(
            self.ground_row,
            self.rows,
        )

    def draw_ground_pile(self):
        if not self.show_tree:
            return

        bg_code = ansi_rgb(
            "48",
            self.bg_color,
        )

        for (
            row,
            col,
        ), (
            petal,
            color,
        ) in self.ground_pile.items():

            if (
                self.ground_row <= row <= self.rows
                and 1 <= col <= self.cols
            ):
                sys.stdout.write(
                    f"\033[{row};{col}H"
                    f"{ansi_rgb('38', color)}"
                    f"{petal}"
                    f"{bg_code}"
                )

    # --------------------------------------------------------
    # Petals
    # --------------------------------------------------------

    def spawn_leaf(self, i):
        spawn_from_tree = (
            self.show_tree
            and self.canopy_spawn_points
            and random.random() < TREE_SPAWN_PROBABILITY
        )

        if spawn_from_tree:
            row, col = random.choice(
                self.canopy_spawn_points
            )

            row += random.randint(-1, 1)

            row = max(
                1,
                min(
                    row,
                    self.ground_row - 1,
                ),
            )

            self.leaf_y[i] = row
            self.leaf_x[i] = col

        else:
            self.leaf_y[i] = random.randint(
                -self.max_off_screen_y,
                -1,
            )

            if self.show_tree:
                self.leaf_x[i] = random.randint(
                    1,
                    self.cols,
                )
            else:
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

        self.leaf_color[i] = (
            self.random_petal_color()
        )

        self.char_timer[i] = 0

        self.char_interval[i] = random.randint(
            3,
            8,
        )

        self.leaf_rest_row[i] = (
            self.choose_rest_row()
            if self.show_tree
            else self.rows
        )

    def reset_positions(self):
        self.leaf_x = []
        self.leaf_y = []
        self.prev_x = []
        self.prev_y = []

        self.leaf_char = []
        self.leaf_color = []
        self.char_timer = []
        self.char_interval = []
        self.leaf_rest_row = []

        for _ in range(self.num_leaves):
            x = random.randint(
                -self.max_off_screen_x,
                self.cols
                + self.max_off_screen_x
                - 1,
            )

            max_y = (
                self.ground_row - 1
                if self.show_tree
                else self.rows
                + self.max_off_screen_y
                - 1
            )

            y = random.randint(
                -self.max_off_screen_y,
                max_y,
            )

            self.leaf_x.append(x)
            self.leaf_y.append(y)

            self.prev_x.append(x)
            self.prev_y.append(y)

            self.leaf_char.append(
                random.choice(
                    PETAL_CHARS
                )
            )

            self.leaf_color.append(
                self.random_petal_color()
            )

            self.char_timer.append(0)

            self.char_interval.append(
                random.randint(
                    3,
                    8,
                )
            )

            self.leaf_rest_row.append(
                self.choose_rest_row()
                if self.show_tree
                else self.rows
            )

    def respawn_leaf(self, i):
        self.spawn_leaf(i)

    # --------------------------------------------------------
    # Terminal
    # --------------------------------------------------------

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
        bg = ansi_rgb(
            "48",
            self.bg_color,
        )

        for row in range(self.rows):
            sys.stdout.write(
                f"\033[{row + 1};1H"
                f"{bg}"
                f"{' ' * self.cols}"
            )

        sys.stdout.flush()

    # --------------------------------------------------------
    # Animation
    # --------------------------------------------------------

    def run(self):
        self.draw_background()

        bg_code = ansi_rgb(
            "48",
            self.bg_color,
        )

        if self.show_tree:
            self.draw_ground()
            self.draw_ground_pile()
            self.draw_tree()

        sys.stdout.flush()

        while True:
            for i in range(self.num_leaves):
                prev_y = self.prev_y[i]
                prev_x = self.prev_x[i]

                if (
                    1 <= prev_y <= self.rows
                    and 1 <= prev_x <= self.cols
                ):
                    tree_char = self.tree_at(
                        prev_y,
                        prev_x,
                    )

                    if tree_char is not None:
                        sys.stdout.write(
                            f"\033[{prev_y};{prev_x}H"
                            f"{tree_char}"
                            f"{bg_code}"
                        )
                    else:
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

                self.leaf_x[i] += (
                    self.fixed_drift
                    + wobble
                )

                self.char_timer[i] += 1

                if (
                    self.char_timer[i]
                    >= self.char_interval[i]
                ):
                    self.leaf_char[i] = (
                        random.choice(
                            PETAL_CHARS
                        )
                    )

                    self.char_timer[i] = 0
                    self.char_interval[i] = (
                        random.randint(3, 8)
                    )

                if (
                    self.show_tree
                    and self.leaf_y[i]
                    >= self.leaf_rest_row[i]
                ):
                    row = self.leaf_rest_row[i]
                    col = self.leaf_x[i]

                    if 1 <= col <= self.cols:
                        self.ground_pile[
                            (row, col)
                        ] = (
                            self.leaf_char[i],
                            self.leaf_color[i],
                        )

                    self.respawn_leaf(i)
                    continue

                if (
                    1 <= self.leaf_y[i] <= self.rows
                    and 1 <= self.leaf_x[i] <= self.cols
                ):
                    row = self.leaf_y[i]
                    col = self.leaf_x[i]

                    if self.tree_at(row, col) is None:
                        sys.stdout.write(
                            f"\033[{row};{col}H"
                            f"{ansi_rgb('38', self.leaf_color[i])}"
                            f"{self.leaf_char[i]}"
                            f"{bg_code}"
                        )

                        if (
                            not self.show_tree
                            and row == self.rows
                        ):
                            pass
                        else:
                            self.prev_x[i] = col
                            self.prev_y[i] = row

                if (
                    not self.show_tree
                    and self.leaf_y[i] > self.rows
                ):
                    self.respawn_leaf(i)

                elif self.leaf_x[i] > self.cols:
                    self.respawn_leaf(i)

                elif (
                    self.leaf_x[i]
                    < -self.max_off_screen_x
                ):
                    self.respawn_leaf(i)

            if self.show_tree:
                self.draw_ground()
                self.draw_ground_pile()
                self.draw_tree()

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
        show_tree=args.tree,
        tree_scale=args.tree_scale,
    )

    def handle_signal(signum, frame):
        animator.cleanup()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        animator.run()

    except SystemExit:
        raise

    except KeyboardInterrupt:
        animator.cleanup()


if __name__ == "__main__":
    main()