# M3U8 Video downloader

Simple python command line tool to download m3u8 playlist videos.


## Requirements 

- Python ^3.9
    - opencv 2
    - tqdm
    - requests

## Installation

`pip install -r requirements.txt`


## Usage

### Command line
```
python3 m3u8_downloader.py --url https://someurl/playlist.m3u8 --out ./myvideo.mp4
```

### Python class
```python3
downloader = M3U8Downloader("https://someurl/playlist.m3u8")
downloader.start("./myvideo.mp4")
```

### Options

See all options:
`python3 m3u8_downloader.py -h`
