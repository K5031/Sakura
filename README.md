
# Sakura
A terminal cherry blossom animation.


## Demo
https://github.com/user-attachments/assets/7e3f06df-25c3-4b2f-a817-1479f1446447


## Usage/Examples

```bash
./sakura.py [OPTIONS]
```

Options:

```text
-n, --num-leaves NUM       Override the automatically calculated petal count
-d, --delay SECONDS        Animation delay in seconds (default: 0.08)
-p, --petal-color R,G,B    Override the default pink palette with one RGB color
-b, --bg-color R,G,B       Background RGB color (optional)
-D, --drift NUM            Fixed drift per frame (default: 1)
-w, --wind-factor NUM      Wind random wobble factor (default: 1)
-t, --tree                 Display the sakura tree
    --tree-scale SCALE     Tree height relative to terminal height (default: 0.6)
-h, --help                 Show this help message
```

RGB values range from `0-255` for each component.

Examples:

```bash
./sakura.py --tree
./sakura.py --tree --tree-scale 0.8
./sakura.py --tree -p 255,192,203
./sakura.py --tree -p 255,0,0 -b 0,0,0
./sakura.py --tree --wind-factor 3
./sakura.py --tree --num-leaves 100
```