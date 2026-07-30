# auto_arras

A tool for automating actions in the arras.io sandbox.

## Quick start

### Generate a template from an image

    python main.py generate image -r 52 52 *path-to-your-image*

### Or create a schematic

Open schematic_editor.py. To save it as a template use ctrl + E
or files > export

### Paste it into arras

Go into a sandbox.

#### Before you start check if

- You have at least ac
- You have spectator tank
- Default size of walls in arena is 64by64(2 world tiles) or size you gave using -r *your size of walls in arena size*
- You have tank spectator
- You have max level(45 or higher)
- Your arras window is in fullscreen
- You have force 16:9 enabled in secret options

To start pasting type

    python main.py paste -t *path-to-your-template*

It will firstly type warning in terminal, check if you meet written requirements and press enter to start pasting.
After this you have 5 seconds of time(by default) to go into arras tab, go into fullscreen, and position your mouse
correctly.

