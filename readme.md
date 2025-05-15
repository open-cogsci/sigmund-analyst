# PyQt Code Editor / Sigmund Analyst

Copyright 2025 Sebastiaan Mathôt


## About

Sigmund Analyst is a powerful code editor (also: Integrated Development Environment or IDE) focused on AI-assisted data analysis with Python

Features:
    
- AI integration [SigmundAI](https://sigmundai.eu) and [Mistral Codestral](https://docs.mistral.ai/capabilities/code_generation/)
- Syntax highlighting
- Code completion
- Code checking
- Project explorer
- Jupyter (IPython) console
- Workspace explorer
- Editor panel with splittable tabs
- Settings panel

![](screenshot.png)


## AI integration

### SigmundAI for collaborative code editing

You can work together with SigmundAI on the currently active document or selected text. To activate SigmundAI integration, simply log into <https://sigmundai.eu> (subscription required). Sigmund Analyst will then automatically connect to SigmundAI when you enable the Sigmund panel in the toolbar.


### Mistral Codestral for as-you-type suggestions

As-you-type code suggestions are provided by Mistral Codestral. To activate Mistral integration, you need to create an account with Mistral AI. Currently, a free Codestral API key is then provided through the Mistral console. Copy-paste this API key to Codestral API Key field in the settings panel of Sigmund Analyst.


## Installation

### Linux installer

The easiest way to install Sigmund Analyst on Linux is to download and run the installer script. This will create a Virtual Environment, pip install Sigmund Analyst and all dependencies into this environment, and add a Desktop file to your system to easily start Sigmund Analyst. To upgrade, simply run the script again.

```
bash <(curl -L https://raw.githubusercontent.com/open-cogsci/pyqt_code_editor/refs/heads/master/install_sigmund_analyst.sh)
```


### Other systems

Install with:

```
pip install pyqt_code_editor
```

Start Sigmund Analyst with:

```
sigmund-analyst
```


## License

`PyQt Code Editor` is licensed under the [GNU General Public License
v3](http://www.gnu.org/licenses/gpl-3.0.en.html).
