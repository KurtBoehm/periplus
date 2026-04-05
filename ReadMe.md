# <img src="https://raw.githubusercontent.com/KurtBoehm/periplus/main/src/periplus/static/favicon.svg" style="height: 1em;"/> Periplus

Periplus (from Latin _periplūs_ “account of a voyage” and Ancient Greek _περίπλους_ “voyage, naval manoeuvre, account of a voyage”) is a web file explorer built with Flask and Bulma.
It serves the current working directory over HTTP with a sortable, keyboard-friendly UI and on-the-fly ZIP downloads.

## ✨ Features

- Browse directories and view files from your filesystem
- Sort by name, size, or modification time (ascending/descending)
- Toggle visibility of hidden files
- Inline image previews and a full-page viewer with keyboard navigation
- Multi-select ZIP download (entire folders or arbitrary selections)
- File uploads with preserved modification time (when provided by the browser)
- Create new folders
- Send files/folders to the system wastebasket instead of deleting outright
- Responsive UI based on Bulma, no JavaScript framework
- No internet access required when run locally

### ⚙️ Minimal JavaScript

Periplus is designed to rely on JavaScript as little as possible; JavaScript only adds the following extras:

- Uploads keep file modification times
- Keyboard navigation in the viewer (← → Esc)
- “Select all” and checkbox-based multi-file ZIP downloads
- Smoother navigation (no extra history entries, in-place delete refresh)

## 📦 Installation

Periplus is [available on PyPI](https://pypi.org/project/periplus/) and can be installed as usual, for example:

```bash
pip install periplus
```

## 🚀 Usage

From the directory you want to expose:

```bash
# Run the Flask development server on http://127.0.0.1:5000/
periplus run

# Make it available to the local network on port 5000
periplus run --host=0.0.0.0
```

Flask provides many more options, including for production use, which are discussed in its [documentation](https://flask.palletsprojects.com/en/stable/).

Periplus is primarily designed for local use and light ad-hoc sharing on trusted networks.
Because it exposes the directory tree of the process’s working directory, it should not be used on an untrusted network without additional access controls or isolation.

### URL structure

Periplus uses the first URL segment to indicate the current mode:

- `GET /browse/...`: main UI (folder listings, or raw file responses)
  - `GET /` redirects to `GET /browse/`
- `GET /view/...`: full-page file viewer
- `GET /preview/...`: small thumbnail previews
- `GET /full-preview/...`: full-size previews (or suitable conversion)
- `GET /download/...`: file downloads and on-the-fly ZIP archives
- `GET /delete/...`: send a file/folder to the trash and redirect
- `GET /static/...`: built-in CSS and icons

Sorting and visibility state are preserved via query parameters:

- `sort=name|size|date`
- `reverse` (present for descending)
- `show-hidden` (present to show dotfiles)

## 📜 Licence

Periplus is licensed under the terms of the Mozilla Public Licence 2.0, provided in [`License`](https://github.com/KurtBoehm/periplus/blob/main/License).

The licences for Bulma (parts of which are included in [`src/periplus/css/user.css`](https://github.com/KurtBoehm/periplus/blob/main/src/periplus/css/user.css)) and for the Feather icons (two of which are included in
[`src/periplus/svg`](https://github.com/KurtBoehm/periplus/blob/main/src/periplus/svg))
are provided in the respective subdirectories.
