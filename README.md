
# Sakura
A terminal cherry blossom animation.


## Demo
https://github.com/user-attachments/assets/7e3f06df-25c3-4b2f-a817-1479f1446447


## Usage/Examples

```
./sakura.sh [OPTIONS]
Options:
  -n, --num-leaves NUM       Number of falling leaves (default: 30)
  -d, --delay SECONDS        Animation delay in seconds (default: 0.1)
  -p, --petal-color R,G,B    Petal RGB color (default: 255,105,180 pink)
  -b, --bg-color R,G,B       Background RGB color (optional)
  -D, --drift NUM            Fixed drift per frame (default: 1)
  -w, --wind-factor NUM      Wind random wobble factor (default: 1)
  -h, --help                 Show this help message

RGB values: 0-255 for each component (Red,Green,Blue)

Examples:
  ./sakura.sh -p 255,192,203           # Light pink petals
  ./sakura.sh -p 255,0,0 -b 0,0,0      # Red petals on black background
  ./sakura.sh -p 0,255,255             # Cyan petals

```


## License

[MIT](https://choosealicense.com/licenses/mit/)
