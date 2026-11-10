"""Merge snk's light and dark snake SVGs into one theme-aware file.

snk writes one palette per file. Both files share the same markup and differ
only in the CSS variables inside `:root{...}`, so this copies the dark file's
variables into the light file under `@media (prefers-color-scheme: dark)`.

Inside an <img>, an SVG's prefers-color-scheme follows the page's
`color-scheme`, which GitHub sets from the viewer's GitHub theme. A <picture>
element follows the OS theme instead, which is why separate light and dark
files could show the wrong colours.

Usage: python merge_snake.py <light.svg> <dark.svg> <output.svg>
"""
import re
import sys

ROOT = re.compile(r":root\{([^}]*)\}")


def main(light_path, dark_path, out_path):
    light = open(light_path, encoding="utf-8").read()
    dark = open(dark_path, encoding="utf-8").read()
    m_light, m_dark = ROOT.search(light), ROOT.search(dark)
    if not m_light or not m_dark:
        sys.exit("merge_snake: could not find :root variables in the snk output")
    block = f"@media (prefers-color-scheme:dark){{:root{{{m_dark.group(1)}}}}}"
    merged = light[: m_light.end()] + block + light[m_light.end():]
    open(out_path, "w", encoding="utf-8").write(merged)
    print(f"merge_snake: wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
