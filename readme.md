# PyQt Code Editor

__This code is under development and not ready for general use__

Fully featured code-editor widgets for PyQt

Copyright 2025 Sebastiaan Mathôt


## About

This is a set of code-editor widgets for PyQt. They are inspired by PyQode, and contain much of the same functionality, but in a cleaner and more modern codebase. All functionality can be used as standalone PyQt widgets. A full Python IDE is also available. This IDE is called Sigmund Analyst, and is primarily intended for data analysis in combination with [SigmundAI](https://sigmundai.eu).

Features:
    
- Code-editor widgets with syntax highlighting, code completion, AI integration, and more
- Project explorer (folder view)
- Editor panel with splittable tabs
- Jupyter console
- Workspace explorer (linked to Jupyter console)
- Settings panel

![](screenshot.png)


## Usage

First, install all dependencies using:

```
pip install .
```

Next, start one of the example scripts:

```
python examples/example_ide.py
```

On some systems, a segmentation fault occurs with the version of PyQt from PyPi. In that case, install PyQt from some other source, such as Anaconda.


## License

`PyQt Code Editor` is licensed under the [GNU General Public License
v3](http://www.gnu.org/licenses/gpl-3.0.en.html).
