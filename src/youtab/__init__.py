from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("youtab")  # pyproject.toml の version
except PackageNotFoundError:  # 入れずにソースから動かしたとき
    __version__ = "0.0.0"
